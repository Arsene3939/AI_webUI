"""
Unit tests for zombie-task recovery and history visibility (spec 2026-10-31 task 2):
 - startup reconciliation demotes tasks whose ComfyUI prompt vanished
 - sync_task_with_server reaps prompts missing from BOTH history and queue
 - failed/interrupted records become visible (and inspectable) in the user history gallery
 - delete_task cleans up archived input media
"""
import os

import pytest

import task_manager as tm_module
from task_manager import task_manager
from components.history_gallery import (
    get_history_dropdown_choices,
    on_select_history_item,
)


class FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def route_get(routes):
    """requests.get stand-in: matches URL fragments in order, returns the mapped FakeResp."""
    def fake_get(url, timeout=None):
        for frag, resp in routes:
            if frag in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise AssertionError(f"unexpected request URL: {url}")
    return fake_get


class TestReconcileOrphanedTasks:
    def test_demotes_running_task_when_backend_unreachable(self, monkeypatch):
        monkeypatch.setattr(
            tm_module.requests, "get",
            route_get([("http", ConnectionError("connection refused"))]),
        )
        tm = tm_module.TaskManager()
        t = tm.create_task("I2V", "killed mid-run", {}, device_id="dev_orph")
        t.status = "running"
        t.prompt_id = "pid-dead"

        assert tm.reconcile_orphaned_tasks(server_url="http://127.0.0.1:1") == 1
        assert t.status == "interrupted"
        assert t.stage == "interrupted"
        assert "重啟" in t.message
        assert tm.get_active_task_for_device("dev_orph") is None

    def test_keeps_task_still_running_in_backend_queue(self, monkeypatch):
        monkeypatch.setattr(tm_module.requests, "get", route_get([
            ("/history/", FakeResp({})),
            ("/queue", FakeResp({"queue_running": [[0, "pid-live", {}]], "queue_pending": []})),
        ]))
        tm = tm_module.TaskManager()
        t = tm.create_task("I2V", "backend still running it", {}, device_id="dev_live")
        t.status = "running"
        t.prompt_id = "pid-live"

        assert tm.reconcile_orphaned_tasks(server_url="http://srv") == 0
        assert t.status == "running"

    def test_keeps_task_with_completed_outputs_in_history(self, monkeypatch):
        outputs = {"12": {"videos": [{"filename": "done.mp4", "subfolder": "", "type": "output"}]}}
        monkeypatch.setattr(tm_module.requests, "get", route_get([
            ("/history/", FakeResp({"pid-done": {"outputs": outputs}})),
            ("/queue", FakeResp({"queue_running": [], "queue_pending": []})),
        ]))
        tm = tm_module.TaskManager()
        t = tm.create_task("I2V", "finished while webui down", {}, device_id="dev_done")
        t.status = "running"
        t.prompt_id = "pid-done"

        assert tm.reconcile_orphaned_tasks(server_url="http://srv") == 0
        assert t.status == "running"  # polling/sync path will download and complete it


class TestSyncReapsVanishedPrompts:
    def test_prompt_missing_from_history_and_queue_is_reaped(self, monkeypatch):
        monkeypatch.setattr(tm_module.requests, "get", route_get([
            ("/history/", FakeResp({})),
            ("/queue", FakeResp({"queue_running": [], "queue_pending": []})),
        ]))
        tm = tm_module.TaskManager()
        t = tm.create_task("UPSCALER", "vanished job", {}, device_id="dev_vanish")
        t.status = "running"
        t.prompt_id = "pid-vanished"

        tm.sync_task_with_server(t, server_url="http://srv")
        assert t.status == "interrupted"
        assert "佇列" in t.message

    def test_prompt_still_queued_is_not_reaped(self, monkeypatch):
        monkeypatch.setattr(tm_module.requests, "get", route_get([
            ("/history/", FakeResp({})),
            ("/queue", FakeResp({"queue_running": [], "queue_pending": [[0, "pid-waiting", {}]]})),
        ]))
        tm = tm_module.TaskManager()
        t = tm.create_task("UPSCALER", "still queued", {}, device_id="dev_wait")
        t.status = "queued"
        t.prompt_id = "pid-waiting"

        tm.sync_task_with_server(t, server_url="http://srv")
        assert t.status == "queued"


class TestUnfinishedHistoryVisibility:
    def _make_device_tasks(self, dev):
        t_done = task_manager.create_task("I2V", "good job", {}, device_id=dev)
        t_done.status = "completed"
        t_done.stage = "completed"
        vid = os.path.join(tm_module.OUTPUT_DIR, f"{t_done.task_id}_gallery.mp4")
        with open(vid, "wb") as f:
            f.write(b"\x00\x00\x00 ftypisom")
        t_done.video_path = vid

        t_stop = task_manager.create_task("I2V", "interrupted job", {}, device_id=dev)
        t_stop.status = "interrupted"
        t_stop.stage = "interrupted"
        t_stop.message = "⚠️ 後端模型已離線，任務已中止（請確認後端後重新提交）"
        t_stop.step, t_stop.total_steps = 7, 13

        t_fail = task_manager.create_task("T2V", "failed job", {}, device_id=dev)
        t_fail.status = "failed"
        t_fail.stage = "failed"
        t_fail.message = "❌ 生成失敗，請查看後端錯誤記錄。"
        return t_done, t_stop, t_fail

    def test_gallery_lists_interrupted_and_failed_with_markers(self):
        dev = "dev_visible"
        _, t_stop, t_fail = self._make_device_tasks(dev)
        labels = {tid: label for label, tid in get_history_dropdown_choices(dev, module="minimax") if tid}
        assert labels[t_stop.task_id].startswith("⚠️")
        assert labels[t_fail.task_id].startswith("❌")

    def test_selecting_interrupted_record_shows_status_not_missing_video(self):
        dev = "dev_visible_detail"
        _, t_stop, _ = self._make_device_tasks(dev)
        video, info = on_select_history_item(t_stop.task_id, dev)
        assert video is None
        assert "已中斷" in info
        assert "7/13" in info
        assert "後端模型已離線" in info

    def test_other_device_still_cannot_see_unfinished_records(self):
        dev = "dev_visible_iso"
        _, t_stop, _ = self._make_device_tasks(dev)
        labels = [tid for _, tid in get_history_dropdown_choices("dev_snooper", module="minimax") if tid]
        assert t_stop.task_id not in labels
        video, info = on_select_history_item(t_stop.task_id, "dev_snooper")
        assert video is None
        assert "找不到該影片檔案" in info

    def test_device_with_only_interrupted_record_still_shows_history(self):
        """「讓歷史紀錄也包含未完成任務」: a device whose only record is unfinished must
        NOT render the empty 暫無歷史紀錄 placeholder."""
        dev = "dev_only_interrupted"
        t = task_manager.create_task("I2V", "killed mid-step", {"prompt": "k", "steps": 13}, device_id=dev)
        t.status = "interrupted"
        t.stage = "interrupted"
        t.message = "⚠️ 後端模型已離線，任務已中止（請確認後端後重新提交）"

        choices = get_history_dropdown_choices(dev, module="minimax")
        placeholder = len(choices) == 1 and choices[0][1] == ""
        assert not placeholder, "僅有未完成紀錄的裝置被當作無歷史紀錄"
        assert any(tid == t.task_id for _, tid in choices)

    def test_unfinished_task_archived_inputs_stay_restorable(self, dummy_image_file):
        """「恢復上次輸入」_reads task params + archived uploads; both must survive while the
        (unfinished) record exists — the restore path never depends on task completion."""
        t = task_manager.create_task(
            "I2V", "restore me", {"first_frame": dummy_image_file, "prompt": "restore me", "steps": 13},
            device_id="dev_restore_src",
        )
        t.status = "interrupted"
        t.stage = "interrupted"

        archived = [f for f in os.listdir(tm_module.INPUTS_ARCHIVE_DIR) if f.startswith(t.task_id)]
        assert archived, "upload was not archived for later restore"

        rec = task_manager.get_task(t.task_id, device_id="dev_restore_src")
        assert rec is not None and rec.status == "interrupted"
        assert rec.params.get("first_frame") and os.path.exists(rec.params["first_frame"]), \
            "archived input lost — 恢復上次輸入 would silently fail"

    def test_delete_task_removes_archived_input_media(self, dummy_image_file):
        t = task_manager.create_task("I2V", "with input", {"first_frame": dummy_image_file}, device_id="dev_arch")
        archives = [f for f in os.listdir(tm_module.INPUTS_ARCHIVE_DIR) if f.startswith(t.task_id)]
        assert archives, "uploaded input was not archived"

        assert task_manager.delete_task(t.task_id, is_admin=True) is True
        leftovers = [f for f in os.listdir(tm_module.INPUTS_ARCHIVE_DIR) if f.startswith(t.task_id)]
        assert leftovers == [], f"delete_task left archived inputs behind: {leftovers}"

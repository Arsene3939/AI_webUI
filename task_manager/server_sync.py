"""
ComfyUI-side reconciliation of task records (Spec 2026-10-31 task 2):
- sync_task_with_server: pull a task's real state from /history (downloads finished
  videos; reaps prompts that vanished from BOTH history and queue after a backend restart)
- reconcile_orphaned_tasks: WebUI-startup pass demoting queued/running records whose
  prompt no longer exists on the backend
- prompt_alive_on_server: single liveness/existence probe used by both

All state mutations call the `save` callback (TaskManager._save_history) so history
persists through the manager's lock, and requests/paths stay patchable via the
task_manager facade / the requests module itself.
"""
import time
from typing import Callable, Dict, Optional

import requests

import task_manager as _pkg
from config import COMFY_SERVER_URL
from logger import get_logger

from .models import Task

logger = get_logger("TaskManager")


def prompt_alive_on_server(prompt_id: str, server_url: str = COMFY_SERVER_URL) -> bool:
    """True if the prompt still exists in ComfyUI (history outputs or queue entries). False on any
    connection failure — a dead/unreachable backend means the in-flight job is gone."""
    try:
        h_resp = requests.get(f"{server_url}/history/{prompt_id}", timeout=2)
        if h_resp.status_code == 200:
            history = h_resp.json().get(prompt_id, {})
            if history.get("outputs"):
                return True
        q_resp = requests.get(f"{server_url}/queue", timeout=2)
        if q_resp.status_code == 200:
            q_data = q_resp.json()
            running = [item[1] for item in q_data.get("queue_running", [])]
            pending = [item[1] for item in q_data.get("queue_pending", [])]
            if prompt_id in running or prompt_id in pending:
                return True
    except Exception:
        return False
    return False


def sync_task_with_server(
    task: Optional[Task],
    server_url: str = COMFY_SERVER_URL,
    save: Optional[Callable[[], None]] = None,
) -> Optional[Task]:
    """
    Synchronizes a task's state with ComfyUI.
    If the task finished in the background or during standby/restart,
    automatically downloads the completed video and updates task status.
    """
    if not task or not task.prompt_id:
        return task

    # Already completed, interrupted or file exists locally
    if task.status in ("completed", "interrupted"):
        return task

    def _persist():
        if save is not None:
            save()

    try:
        h_resp = requests.get(f"{server_url}/history/{task.prompt_id}", timeout=5)
        if h_resp.status_code == 200:
            history = h_resp.json().get(task.prompt_id, {})
            outputs = history.get("outputs", {})
            if outputs:
                for nid, nout in outputs.items():
                    items = nout.get("videos") or nout.get("gifs") or nout.get("images") or []
                    for it in items:
                        fn = it.get("filename")
                        if fn and (fn.endswith(".mp4") or fn.endswith(".webm") or fn.endswith(".mkv")):
                            subfolder = it.get("subfolder", "")
                            folder_type = it.get("type", "output")
                            local_path = _pkg.download_output_file(fn, subfolder, folder_type, server_url)
                            task.video_path = local_path
                            task.status = "completed"
                            task.progress = 1.0
                            task.completed_at = time.time()
                            task.message = f"✅ 影片生成完成！耗時 {task.elapsed} 秒"
                            _persist()
                            return task

            status_info = history.get("status", {})
            if status_info.get("status_str") == "error":
                task.status = "failed"
                task.message = "❌ 生成失敗，請查看後端錯誤記錄。"
                _persist()
                return task

            # Prompt missing from history AND from the ComfyUI queue => the job vanished
            # (backend restarted mid-flight). Reap the zombie so the device UI frees up.
            if task.status in ("queued", "running"):
                try:
                    q_resp = requests.get(f"{server_url}/queue", timeout=5)
                    if q_resp.status_code == 200:
                        q_data = q_resp.json()
                        in_queue = [
                            item[1]
                            for item in q_data.get("queue_running", []) + q_data.get("queue_pending", [])
                        ]
                        if task.prompt_id not in in_queue:
                            task.status = "interrupted"
                            task.stage = "interrupted"
                            task.message = "⚠️ 此工作已不在後端佇列中（後端可能重啟過），請重新提交"
                            _persist()
                            return task
                except Exception:
                    pass
    except Exception:
        pass

    return task


def reconcile_orphaned_tasks(
    tasks: Dict[str, Task],
    lock,
    server_url: Optional[str] = None,
    save: Optional[Callable[[], None]] = None,
) -> int:
    """
    WebUI-startup reconciliation (Spec 2026-10-31 task 2): tasks reloaded as queued/running were
    tracked by a monitor worker that no longer exists. Verify each one against ComfyUI once:
    still queued/running there, or outputs already produced -> keep (polling sync will finish it);
    otherwise the job died with the backend -> demote to interrupted so the device UI frees up
    and the record becomes visible in history. Returns the number of demoted tasks.
    """
    server_url = server_url or COMFY_SERVER_URL
    demoted = 0
    with lock:
        orphans = [t for t in tasks.values() if t.status in ("queued", "running")]
    for t in orphans:
        if t.prompt_id and prompt_alive_on_server(t.prompt_id, server_url):
            continue
        with lock:
            if t.status not in ("queued", "running"):
                continue
            t.cancel_event.set()
            t.status = "interrupted"
            t.stage = "interrupted"
            t.message = "⚠️ 工作已在伺服器重啟時遺失，請重新提交"
        demoted += 1
    if demoted:
        if save is not None:
            save()
        logger.warning("Reconciled %d orphaned queued/running task(s) to interrupted at startup.", demoted)
    return demoted

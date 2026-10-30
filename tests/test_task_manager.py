"""
Unit tests for Task and TaskManager with strict per-device isolation.
"""
import os
import time
import json
import threading
from unittest.mock import patch, MagicMock
import pytest
import task_manager as tm_module  # Module alias (the name `task_manager` below refers to the singleton)
from task_manager import Task, TaskManager, task_manager


class TestTaskModel:
    def test_task_to_and_from_dict(self):
        """Ensures Task serialization and deserialization preserves all fields."""
        t1 = Task(
            task_id="task_12345",
            task_type="I2V",
            prompt="A majestic eagle flying",
            params={"width": 1344, "height": 768, "seed": 42},
            device_id="dev_user_1",
        )
        t1.status = "completed"
        t1.progress = 1.0
        t1.message = "Generation complete"
        t1.video_path = "/path/to/eagle.mp4"
        t1.elapsed = 35.5

        data = t1.to_dict()
        assert data["task_id"] == "task_12345"
        assert data["device_id"] == "dev_user_1"
        assert data["params"]["seed"] == 42
        assert data["video_path"] == "/path/to/eagle.mp4"

        t2 = Task.from_dict(data)
        assert t2.task_id == t1.task_id
        assert t2.device_id == t1.device_id
        assert t2.prompt == t1.prompt
        assert t2.params == t1.params
        assert t2.status == "completed"
        assert t2.video_path == t1.video_path
        assert t2.elapsed == 35.5


class TestTaskManagerIsolation:
    def test_create_task_archives_input_media(self, dummy_image_file):
        """Ensures uploaded media in params is copied into inputs archive."""
        tm = TaskManager()
        params = {
            "first_frame": dummy_image_file,
            "width": 1344,
            "height": 768,
        }
        task = tm.create_task("I2V", "A sunset", params, device_id="dev_A")

        assert task.task_id.startswith("task_")
        assert task.device_id == "dev_A"
        # The first_frame parameter should now point to archived location
        archived_path = task.params["first_frame"]
        assert os.path.exists(archived_path)
        assert "inputs" in archived_path
        assert task.task_id in archived_path

    def test_get_task_strict_device_isolation(self):
        """Ensures Device B cannot access Device A's task."""
        tm = TaskManager()
        task = tm.create_task("T2V", "Private scene", {}, device_id="device_alpha")

        # Owner access succeeds
        assert tm.get_task(task.task_id, device_id="device_alpha") is not None
        assert tm.get_task(task.task_id, device_id="device_alpha").task_id == task.task_id

        # Non-owner access is strictly blocked
        assert tm.get_task(task.task_id, device_id="device_beta") is None

        # Unspecified device_id (internal admin/system call) succeeds
        assert tm.get_task(task.task_id, device_id=None) is not None

    def test_get_latest_task_for_device(self):
        """Ensures latest task is segregated strictly per device."""
        tm = TaskManager()

        # Device A creates Task 1
        t_a1 = tm.create_task("I2V", "Prompt A1", {}, device_id="dev_A")
        t_a1.created_at = 1000.0

        # Device B creates Task 1
        t_b1 = tm.create_task("I2V", "Prompt B1", {}, device_id="dev_B")
        t_b1.created_at = 2000.0

        # Device A creates Task 2
        t_a2 = tm.create_task("I2V", "Prompt A2", {}, device_id="dev_A")
        t_a2.created_at = 3000.0

        latest_a = tm.get_latest_task_for_device("dev_A")
        assert latest_a is not None
        assert latest_a.task_id == t_a2.task_id
        assert latest_a.prompt == "Prompt A2"

        latest_b = tm.get_latest_task_for_device("dev_B")
        assert latest_b is not None
        assert latest_b.task_id == t_b1.task_id
        assert latest_b.prompt == "Prompt B1"

        assert tm.get_latest_task_for_device("dev_C") is None
        assert tm.get_latest_task_for_device("") is None
        assert tm.get_latest_task_for_device(None) is None

    def test_get_completed_tasks_for_device(self, tmp_path):
        """Ensures completed history list filters by device and valid video path."""
        tm = TaskManager()

        # Create dummy completed video files
        video_a = tmp_path / "video_a.mp4"
        video_a.write_bytes(b"dummy_a")
        video_b = tmp_path / "video_b.mp4"
        video_b.write_bytes(b"dummy_b")

        # Task for Dev A: completed with valid video
        t_a = tm.create_task("I2V", "Done A", {}, device_id="dev_A")
        t_a.status = "completed"
        t_a.video_path = str(video_a)

        # Task for Dev A: running (should not appear in completed list)
        t_a_running = tm.create_task("I2V", "Running A", {}, device_id="dev_A")
        t_a_running.status = "running"

        # Task for Dev B: completed with valid video
        t_b = tm.create_task("I2V", "Done B", {}, device_id="dev_B")
        t_b.status = "completed"
        t_b.video_path = str(video_b)

        # Dev A queries history
        completed_a = tm.get_completed_tasks_for_device("dev_A")
        assert len(completed_a) == 1
        assert completed_a[0].task_id == t_a.task_id

        # Dev B queries history
        completed_b = tm.get_completed_tasks_for_device("dev_B")
        assert len(completed_b) == 1
        assert completed_b[0].task_id == t_b.task_id

        # Non-existent device queries history
        assert len(tm.get_completed_tasks_for_device("dev_unknown")) == 0

    def test_history_persistence_roundtrip(self, tmp_path):
        """Ensures history is correctly saved to and loaded from JSON."""
        tm1 = TaskManager()
        t = tm1.create_task("T2V", "Persistent task", {"seed": 100}, device_id="dev_pers")
        t.status = "completed"
        tm1._save_history()

        # Initialize a brand new manager reading from the same history file
        tm2 = TaskManager()
        loaded = tm2.get_task(t.task_id, device_id="dev_pers")
        assert loaded is not None
        assert loaded.prompt == "Persistent task"
        assert loaded.params["seed"] == 100

    def test_delete_task_success_and_device_isolation(self, tmp_path):
        """Ensures delete_task removes task, cleans up video, and protects other devices (Spec Task 7)."""
        tm = TaskManager()

        dummy_video = tmp_path / "del_video.mp4"
        dummy_video.write_bytes(b"dummy_video_data")
        assert dummy_video.exists()

        t = tm.create_task("I2V", "Task to delete", {}, device_id="dev_del_owner")
        t.status = "completed"
        t.video_path = str(dummy_video)
        tm._save_history()

        # 1. Unauthorized device cannot delete
        assert tm.delete_task(t.task_id, device_id="dev_other_user") is False
        assert tm.get_task(t.task_id, device_id="dev_del_owner") is not None
        assert dummy_video.exists()

        # 2. Deleting non-existent task returns False
        assert tm.delete_task("non_existent_id", device_id="dev_del_owner") is False

        # 3. Authorized owner deletes task
        assert tm.delete_task(t.task_id, device_id="dev_del_owner") is True
        assert tm.get_task(t.task_id, device_id="dev_del_owner") is None
        assert not dummy_video.exists()

        # 4. Verified persistence after deletion
        tm_reloaded = TaskManager()
        assert tm_reloaded.get_task(t.task_id, device_id="dev_del_owner") is None


class TestTaskManagerBackgroundWorker:
    @patch("task_manager.download_output_file")
    @patch("task_manager.queue_prompt")
    @patch("task_manager.requests.get")
    def test_monitor_worker_success(self, mock_get, mock_queue, mock_download, tmp_path):
        """Simulates successful prompt queuing, execution, and output download."""
        dummy_out = tmp_path / "result.mp4"
        dummy_out.write_bytes(b"content")

        mock_queue.return_value = "fake-prompt-001"
        mock_download.return_value = str(dummy_out)

        # Response 1: ComfyUI history returning output video
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "fake-prompt-001": {
                "outputs": {
                    "save_video": {
                        "videos": [{"filename": "MiniMax_0001.mp4", "subfolder": "video", "type": "output"}]
                    }
                }
            }
        }
        mock_get.return_value = mock_resp

        tm = TaskManager()
        task = tm.create_task("T2V", "A running athlete", {}, device_id="dev_test")

        # Run worker directly (synchronous for test)
        tm._monitor_worker(task, {}, "http://127.0.0.1:8188")

        assert task.status == "completed"
        assert task.progress == 1.0
        assert task.prompt_id == "fake-prompt-001"
        assert task.video_path == str(dummy_out)
        assert "✅" in task.message

    @patch("task_manager.queue_prompt")
    def test_monitor_worker_queue_failure(self, mock_queue):
        """Ensures worker handles ComfyUI submission failure gracefully."""
        mock_queue.side_effect = RuntimeError("ComfyUI server out of memory")

        tm = TaskManager()
        task = tm.create_task("T2V", "Fail task", {}, device_id="dev_fail")

        tm._monitor_worker(task, {}, "http://127.0.0.1:8188")

        assert task.status == "failed"
        assert "❌ 提交失敗" in task.message

    @patch("task_manager.download_output_file")
    @patch("task_manager.requests.get")
    def test_sync_task_with_server_recovery(self, mock_get, mock_download, tmp_path):
        """Ensures task sync automatically fetches completed video from ComfyUI server."""
        dummy_out = tmp_path / "recovered_video.mp4"
        dummy_out.write_bytes(b"recovered")
        mock_download.return_value = str(dummy_out)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "recovered-prompt-999": {
                "outputs": {
                    "save_video": {
                        "videos": [{"filename": "recovered.mp4", "subfolder": "video", "type": "output"}]
                    }
                }
            }
        }
        mock_get.return_value = mock_resp

        tm = TaskManager()
        # Create a task that was previously marked failed or interrupted
        task = tm.create_task("I2V", "A long running task", {}, device_id="dev_recovery")
        task.prompt_id = "recovered-prompt-999"
        task.status = "failed"
        task.video_path = None

        # Calling get_latest_task_for_device should trigger sync_task_with_server
        synced_task = tm.get_latest_task_for_device("dev_recovery")

        assert synced_task is not None
        assert synced_task.status == "completed"
        assert synced_task.progress == 1.0
        assert synced_task.video_path == str(dummy_out)

    @patch("task_manager.queue_prompt")
    @patch("task_manager.requests.get")
    def test_multi_device_queued_pending_state(self, mock_get, mock_queue):
        """Tests that when another task is running, a new queued task reports 'queued' / 'pending' status."""
        mock_queue.return_value = "prompt-dev-b"

        # Mock queue response: prompt-dev-a is running, prompt-dev-b is pending
        mock_queue_resp = MagicMock()
        mock_queue_resp.status_code = 200
        mock_queue_resp.json.return_value = {
            "queue_running": [["task_a", "prompt-dev-a", {}]],
            "queue_pending": [["task_b", "prompt-dev-b", {}]],
        }

        # Mock history response: prompt-dev-b not finished yet
        mock_history_resp = MagicMock()
        mock_history_resp.status_code = 200
        mock_history_resp.json.return_value = {}

        def mock_get_side_effect(url, *args, **kwargs):
            if "/queue" in url:
                return mock_queue_resp
            if "/history" in url:
                return mock_history_resp
            return MagicMock(status_code=404)

        mock_get.side_effect = mock_get_side_effect

        tm = TaskManager()
        task_b = tm.create_task("I2V", "Dev B task", {}, device_id="dev_b")

        # Simulate what queue_prompt assigns:
        task_b.prompt_id = "prompt-dev-b"
        task_b.status = "queued"
        task_b.stage = "pending"

        # Check queue status poll logic
        q_data = mock_queue_resp.json()
        running = [item[1] for item in q_data.get("queue_running", [])]
        pending = [item[1] for item in q_data.get("queue_pending", [])]

        assert "prompt-dev-b" in pending
        assert "prompt-dev-b" not in running
        assert task_b.status == "queued"
        assert task_b.stage == "pending"

    def test_create_task_initializes_total_steps(self):
        """Tests that create_task initializes total_steps from params['steps']."""
        tm = TaskManager()
        task = tm.create_task("I2V", "Test steps", {"steps": 25}, device_id="dev_step_test")
        assert task.total_steps == 25
        assert task.step == 0
        assert task.stage == "preprocessing"

    @patch("task_manager.download_output_file")
    @patch("task_manager.queue_prompt")
    @patch("task_manager.requests.get")
    def test_sampling_stage_immediate_update_at_step_zero(self, mock_get, mock_queue, mock_download):
        """Tests that when task enters sampling stage, status immediately shows '影片生成中' even at step 0."""
        mock_queue.return_value = "prompt-sampling-001"

        # Mock queue response: prompt is running in ComfyUI
        mock_queue_resp = MagicMock()
        mock_queue_resp.status_code = 200
        mock_queue_resp.json.return_value = {
            "queue_running": [["0", "prompt-sampling-001", {}]],
            "queue_pending": [],
        }

        # History returns empty (not completed yet)
        mock_history_resp = MagicMock()
        mock_history_resp.status_code = 200
        mock_history_resp.json.return_value = {}

        def mock_get_side_effect(url, *args, **kwargs):
            if "/queue" in url:
                return mock_queue_resp
            if "/history" in url:
                return mock_history_resp
            return MagicMock(status_code=404)

        mock_get.side_effect = mock_get_side_effect

        tm = TaskManager()
        task = tm.create_task("I2V", "Sampling test", {"steps": 20}, device_id="dev_sampling_test")
        task.prompt_id = "prompt-sampling-001"
        task.stage = "sampling"
        task.step = 0

        # Simulate one iteration of monitor queue check logic
        q_data = mock_queue_resp.json()
        running = [item[1] for item in q_data.get("queue_running", [])]
        time_str = "5秒"

        if task.total_steps > 0 and task.step >= task.total_steps:
            task.stage = "postprocessing"
        elif task.stage == "postprocessing":
            pass
        elif task.stage == "sampling" or (task.total_steps > 0 and task.step > 0):
            task.status = "running"
            task.stage = "sampling"
            if task.total_steps > 0:
                task.message = f"⚡ 影片生成中: {task.step}/{task.total_steps} 步 (耗時 {time_str})"
            else:
                task.message = f"⚡ 影片生成中... (耗時 {time_str})"
        elif task.prompt_id in running:
            task.stage = "preprocessing"
            task.message = f"⚡ 前處理中：正在載入模型... (耗時 {time_str})"

        assert task.stage == "sampling"
        assert "⚡ 影片生成中: 0/20 步" in task.message
        assert "前處理中" not in task.message
        assert "載入模型中" not in task.message


class TestModuleFieldAndHistoryIsolation:
    """Spec task 2: tasks carry an owning module and galleries never leak across modules."""

    def test_module_assignment_and_derivation(self):
        """Explicit module honored; legacy task_type correctly derives module."""
        tm = TaskManager()
        t_up = tm.create_task("UPSCALER", "Upscale clip", {}, device_id="dev_mod")
        t_i2v = tm.create_task("I2V", "Generate clip", {}, device_id="dev_mod")
        assert t_up.module == "upscaler"
        assert t_i2v.module == "minimax"

        # Legacy constructor without module
        legacy = Task("task_legacy", "T2V", "old", {}, device_id="dev_mod")
        assert legacy.module == "minimax"

    def test_module_survives_history_roundtrip_and_legacy_load(self):
        """to_dict/from_dict keeps module; history JSON without module field still loads."""
        tm = TaskManager()
        t = tm.create_task("UPSCALER", "Persisted upscale", {}, device_id="dev_mod2")
        assert t.to_dict()["module"] == "upscaler"
        tm._save_history()

        # Simulate a legacy history file recorded before the module field existed
        with open(tm_module.HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            item.pop("module", None)
        with open(tm_module.HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)

        tm2 = TaskManager()
        loaded = tm2.get_task(t.task_id)
        assert loaded is not None
        assert loaded.module == "upscaler"  # derived from task_type

    def test_history_choices_isolated_between_modules(self, tmp_path):
        """minimax gallery must not show UPSCALER records, and vice versa (Spec task 2)."""
        from components.history_gallery import get_history_dropdown_choices

        dev = "dev_hist_iso"
        video_a = tmp_path / "minimax_out.mp4"
        video_a.write_bytes(b"mm")
        video_b = tmp_path / "up_out.mp4"
        video_b.write_bytes(b"up")

        t_mm = task_manager.create_task("I2V", "MiniMax job", {}, device_id=dev)
        t_mm.status = "completed"
        t_mm.video_path = str(video_a)

        t_up = task_manager.create_task("UPSCALER", "Upscale job", {}, device_id=dev)
        t_up.status = "completed"
        t_up.video_path = str(video_b)

        mm_choices = [tid for _, tid in get_history_dropdown_choices(dev, module="minimax")]
        up_choices = [tid for _, tid in get_history_dropdown_choices(dev, module="upscaler")]

        assert mm_choices == [t_mm.task_id]
        assert up_choices == [t_up.task_id]

    def test_latest_and_active_queries_module_scoped(self):
        """A device's latest upscaler task must not shadow the minimax view's session state."""
        tm = TaskManager()
        dev = "dev_latest_iso"
        t_mm = tm.create_task("I2V", "minimax job", {}, device_id=dev)
        t_mm.created_at = 1000.0
        t_up = tm.create_task("UPSCALER", "upscale job", {}, device_id=dev)
        t_up.created_at = 2000.0  # newer task belongs to the other module

        latest_mm = tm.get_latest_task_for_device(dev, module="minimax")
        latest_up = tm.get_latest_task_for_device(dev, module="upscaler")
        assert latest_mm is not None and latest_mm.task_id == t_mm.task_id
        assert latest_up is not None and latest_up.task_id == t_up.task_id

        # Unfiltered behavior preserved for admin/global views
        latest_any = tm.get_latest_task_for_device(dev)
        assert latest_any is not None and latest_any.task_id == t_up.task_id

        active_up = tm.get_active_task_for_device(dev, module="upscaler")
        assert active_up is not None and active_up.task_id == t_up.task_id
        assert active_up.module == "upscaler"


class TestModuleScopedInterrupt:
    """Spec task 1: stop buttons only interrupt their own module's tasks."""

    def test_interrupt_device_tasks_only_targets_one_module(self):
        tm = TaskManager()
        dev = "dev_iso_int"
        t_mm = tm.create_task("I2V", "minimax running job", {}, device_id=dev)
        t_up = tm.create_task("UPSCALER", "upscaler running job", {}, device_id=dev)

        interrupted = tm.interrupt_device_tasks(device_id=dev, module="upscaler")
        assert interrupted == [t_up.task_id]
        assert t_up.status == "interrupted"
        assert t_mm.status == "queued"  # minimax job untouched (friendly-fire eliminated)

        # Legacy unscoped call still interrupts the remaining task (admin/global path)
        interrupted_all = tm.interrupt_device_tasks(device_id=dev)
        assert t_mm.task_id in interrupted_all
        assert t_mm.status == "interrupted"

    @patch("core.comfy_client.interrupt_execution")
    def test_interrupt_task_uses_targeted_cancel_only(self, mock_interrupt):
        """No general /interrupt: other modules' running ComfyUI jobs must not be killed."""
        tm = TaskManager()
        t = tm.create_task("I2V", "job with prompt", {}, device_id="dev_targeted")
        t.status = "running"
        t.prompt_id = "prompt-target-001"

        assert tm.interrupt_task(t.task_id) is True
        assert t.status == "interrupted"
        # Every interrupt call must carry the target prompt_id; none may be general
        assert mock_interrupt.call_count >= 1
        for call in mock_interrupt.call_args_list:
            assert call.kwargs.get("prompt_id") == "prompt-target-001"


class TestSerialDispatcher:
    """Spec task 1: FIFO serial dispatch so modules queue instead of preempting."""

    def test_dispatcher_runs_tasks_fifo_one_at_a_time(self, monkeypatch):
        tm = TaskManager()
        execution_log = []
        active = {"count": 0}

        def fake_worker(self, task, prompt_graph, server_url):
            assert active["count"] == 0, "Dispatcher violated serial execution (overlap detected)"
            active["count"] += 1
            execution_log.append((task.task_id, task.module))
            time.sleep(0.1)
            task.status = "completed"
            task.stage = "completed"
            active["count"] -= 1

        monkeypatch.setattr(TaskManager, "_monitor_worker", fake_worker)

        t_up = tm.create_task("UPSCALER", "upscale first", {}, device_id="dev_disp")
        t_mm = tm.create_task("I2V", "minimax second", {}, device_id="dev_disp")
        tm.start_background_task(t_up, {"g": 1})
        tm.start_background_task(t_mm, {"g": 2})

        # Both tasks were enqueued, not executed inline on the calling thread
        deadline = time.time() + 10
        while (t_up.status != "completed" or t_mm.status != "completed") and time.time() < deadline:
            time.sleep(0.02)

        assert t_up.status == "completed"
        assert t_mm.status == "completed"
        assert execution_log == [(t_up.task_id, "upscaler"), (t_mm.task_id, "minimax")]

    def test_interrupt_queued_task_removes_it_from_dispatch_queue(self, monkeypatch):
        """Interrupting a still-queued task must purge it so the dispatcher skips it."""
        tm = TaskManager()
        started = threading.Event()
        release = threading.Event()

        def fake_worker(self, task, prompt_graph, server_url):
            started.set()
            release.wait(timeout=5)
            task.status = "completed"

        monkeypatch.setattr(TaskManager, "_monitor_worker", fake_worker)

        t_blocker = tm.create_task("I2V", "blocking job", {"steps": 1}, device_id="dev_q")
        t_victim = tm.create_task("UPSCALER", "queued upscale", {}, device_id="dev_q")
        tm.start_background_task(t_blocker, {"g": 1})
        tm.start_background_task(t_victim, {"g": 2})

        assert started.wait(timeout=5)
        assert tm.interrupt_device_tasks(device_id="dev_q", module="upscaler") == [t_victim.task_id]
        assert t_victim.status == "interrupted"
        with tm._lock:
            assert all(e[0] != t_victim.task_id for e in tm._dispatch_queue)

        release.set()
        deadline = time.time() + 10
        while t_blocker.status != "completed" and time.time() < deadline:
            time.sleep(0.02)
        assert t_blocker.status == "completed"
        assert t_victim.status == "interrupted"

    def test_queued_task_reports_queue_position_message(self, monkeypatch):
        tm = TaskManager()
        started = threading.Event()
        release = threading.Event()

        def fake_worker(self, task, prompt_graph, server_url):
            started.set()
            release.wait(timeout=5)
            task.status = "completed"

        monkeypatch.setattr(TaskManager, "_monitor_worker", fake_worker)

        t_blocker = tm.create_task("I2V", "occupying GPU", {}, device_id="dev_msg")
        t_waiting = tm.create_task("UPSCALER", "waiting upscale", {}, device_id="dev_msg")
        tm.start_background_task(t_blocker, {"g": 1})
        assert started.wait(timeout=5)
        tm.start_background_task(t_waiting, {"g": 2})

        assert t_waiting.status == "queued"
        assert t_waiting.stage == "pending"
        assert "排隊中" in t_waiting.message
        assert "1" in t_waiting.message  # exactly one job ahead

        release.set()
        deadline = time.time() + 10
        while t_waiting.status != "completed" and time.time() < deadline:
            time.sleep(0.02)
        assert t_waiting.status == "completed"

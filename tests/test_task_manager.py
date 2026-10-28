"""
Unit tests for Task and TaskManager with strict per-device isolation.
"""
import os
import time
import json
from unittest.mock import patch, MagicMock
import pytest
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


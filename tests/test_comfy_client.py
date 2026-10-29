"""
Unit tests for comfy_client.py API functions and server communication.
"""
import os
import requests
from unittest.mock import patch, MagicMock
import pytest
from comfy_client import (
    check_server,
    start_comfyui_backend,
    stop_comfyui_backend,
    upload_media_file,
    queue_prompt,
    download_output_file,
    check_system_resources,
    interrupt_execution,
)


class TestComfyClientServerCheck:
    @patch("comfy_client.requests.get")
    def test_check_server_online(self, mock_get):
        """Tests check_server when ComfyUI responds with 200."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        ok, msg = check_server("http://127.0.0.1:8188")
        assert ok is True
        assert "運作中" in msg

    @patch("comfy_client.requests.get")
    def test_check_server_error_code(self, mock_get):
        """Tests check_server when ComfyUI responds with 500."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        ok, msg = check_server("http://127.0.0.1:8188")
        assert ok is False
        assert "500" in msg

    @patch("comfy_client.requests.get")
    def test_check_server_offline(self, mock_get):
        """Tests check_server when ComfyUI connection fails."""
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        ok, msg = check_server("http://127.0.0.1:8188")
        assert ok is False
        assert "離線中" in msg


class TestComfyClientUpload:
    def test_upload_media_file_not_found(self):
        """Nonexistent file must raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            upload_media_file("/non/existent/path/image.png")

    @patch("comfy_client.requests.post")
    def test_upload_media_file_success(self, mock_post, dummy_image_file):
        """Tests successful file upload to ComfyUI input directory."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"name": "uploaded_image.png"}
        mock_post.return_value = mock_resp

        result = upload_media_file(dummy_image_file, "http://127.0.0.1:8188")
        assert result == "uploaded_image.png"
        assert mock_post.called


class TestComfyClientQueuePrompt:
    @patch("comfy_client.requests.post")
    def test_queue_prompt_success(self, mock_post):
        """Tests successful prompt graph submission returning prompt_id."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"prompt_id": "test-prompt-id-999"}
        mock_post.return_value = mock_resp

        prompt_id = queue_prompt({"node": {}}, "client-123", "http://127.0.0.1:8188")
        assert prompt_id == "test-prompt-id-999"

    @patch("comfy_client.requests.post")
    def test_queue_prompt_rejected(self, mock_post):
        """Tests handling when ComfyUI rejects the graph submission."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "error": "Missing input node",
            "node_errors": {"minimax_node": "Invalid length"},
        }
        mock_post.return_value = mock_resp

        with pytest.raises(RuntimeError) as exc_info:
            queue_prompt({"node": {}}, "client-123", "http://127.0.0.1:8188")
        assert "ComfyUI 拒絕執行" in str(exc_info.value)


class TestComfyClientDownload:
    @patch("comfy_client.requests.get")
    def test_download_output_file(self, mock_get, tmp_path, monkeypatch):
        """Tests downloading generated video stream to local output directory."""
        temp_dir = tmp_path / "downloads"
        temp_dir.mkdir()
        import comfy_client
        monkeypatch.setattr(comfy_client, "OUTPUT_DIR", str(temp_dir))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_get.return_value = mock_resp

        saved_path = download_output_file("MiniMax_video.mp4", subfolder="video", server_url="http://127.0.0.1:8188")
        assert os.path.exists(saved_path)
        with open(saved_path, "rb") as f:
            content = f.read()
        assert content == b"chunk1chunk2"


class TestComfyClientBackendStartup:
    @patch("comfy_client.check_server")
    def test_start_comfyui_backend_already_running(self, mock_check):
        """When ComfyUI is already online, do not launch again."""
        mock_check.return_value = (True, "🟢 ComfyUI 後端運作中")
        ok, msg = start_comfyui_backend("http://127.0.0.1:8188")
        assert ok is True
        assert "已經在運作中" in msg

    @patch("comfy_client.check_system_resources")
    @patch("comfy_client.check_server")
    @patch("os.path.exists")
    def test_start_comfyui_backend_missing_main(self, mock_exists, mock_check, mock_resources):
        """When main.py cannot be found, report clear error message."""
        mock_check.return_value = (False, "Offline")
        mock_resources.return_value = (True, "", {})
        # Pretend main.py does not exist
        mock_exists.return_value = False

        ok, msg = start_comfyui_backend("http://127.0.0.1:8188")
        assert ok is False
        assert "找不到 ComfyUI 核心主程式" in msg


class TestComfyClientBackendStop:
    @patch("comfy_client.time.sleep")
    @patch("comfy_client.check_server")
    @patch("comfy_client.subprocess.check_output")
    def test_stop_comfyui_backend_success(self, mock_subprocess, mock_check, mock_sleep):
        """Tests stopping ComfyUI backend terminates process and port listener."""
        mock_check.side_effect = [(True, "Online"), (False, "Offline")]
        mock_subprocess.return_value = b"1234\n"

        ok, msg = stop_comfyui_backend("http://127.0.0.1:8188")
        assert ok is True
        assert "成功關閉" in msg

    @patch("comfy_client.check_server")
    def test_stop_comfyui_backend_already_offline(self, mock_check):
        """When ComfyUI is not running, stop returns immediately."""
        mock_check.return_value = (False, "Offline")

        ok, msg = stop_comfyui_backend("http://127.0.0.1:8188")
        assert ok is False
        assert "本來就未在運作" in msg

    @patch("comfy_client.time.sleep")
    @patch("comfy_client.check_server")
    @patch("comfy_client.subprocess.check_output")
    def test_stop_comfyui_backend_failure(self, mock_subprocess, mock_check, mock_sleep):
        """Tests handling when process refuses to terminate."""
        mock_check.side_effect = [(True, "Online"), (True, "Still Online")]
        mock_subprocess.return_value = b""

        ok, msg = stop_comfyui_backend("http://127.0.0.1:8188")
        assert ok is False
        assert "失敗" in msg


class TestSystemResourceChecking:
    @patch("comfy_client.subprocess.check_output")
    @patch("comfy_client.psutil.virtual_memory")
    def test_check_system_resources_all_sufficient(self, mock_vm, mock_subprocess):
        """When RAM > 50GB, GPU util < 20%, and free VRAM > 10GB, check passes."""
        vm = MagicMock()
        vm.available = 64 * (1024 ** 3)  # 64 GB
        mock_vm.return_value = vm

        mock_subprocess.return_value = "10.0, 16384.0\n"  # 10% util, 16 GB free VRAM

        ok, msg, stats = check_system_resources(min_ram_gb=50.0, max_gpu_util=20.0, min_vram_gb=10.0)
        assert ok is True
        assert msg == ""
        assert stats["ram_available_gb"] == 64.0
        assert stats["gpu_util_pct"] == 10.0
        assert stats["gpu_free_vram_gb"] == 16.0

    @patch("comfy_client.subprocess.check_output")
    @patch("comfy_client.psutil.virtual_memory")
    def test_check_system_resources_insufficient(self, mock_vm, mock_subprocess):
        """When resources do not meet the thresholds, check fails with warning."""
        vm = MagicMock()
        vm.available = 32 * (1024 ** 3)  # 32 GB (< 50 GB)
        mock_vm.return_value = vm

        mock_subprocess.return_value = "35.0, 8192.0\n"  # 35% util (>= 20%), 8 GB VRAM (<= 10 GB)

        ok, msg, stats = check_system_resources(min_ram_gb=50.0, max_gpu_util=20.0, min_vram_gb=10.0)
        assert ok is False
        assert "運算資源不足" in msg
        assert "記憶體" in msg
        assert "GPU 佔用率" in msg
        assert "顯存" in msg

    @patch("comfy_client.check_system_resources")
    @patch("comfy_client.check_server")
    def test_start_backend_blocked_by_resources(self, mock_check, mock_resources):
        """Backend startup is blocked when system resources are insufficient (Spec 2)."""
        mock_check.return_value = (False, "Offline")
        mock_resources.return_value = (False, "⚠️ 伺服器運算資源不足：可用記憶體 30 GB", {})

        ok, msg = start_comfyui_backend("http://127.0.0.1:8188")
        assert ok is False
        assert "運算資源不足" in msg


class TestInterruptExecution:
    @patch("comfy_client.requests.post")
    def test_interrupt_targeted_prompt(self, mock_post):
        """Targeted interrupt deletes from queue and cancels prompt without general kill."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        success = interrupt_execution(prompt_id="test_prompt_123")
        assert success is True
        # Verify /queue was called with delete
        delete_call_found = any(
            "/queue" in str(c) and "delete" in str(kwargs.get("json", {}))
            for _, c, kwargs in mock_post.mock_calls if len(c) > 0 or kwargs
        )
        assert delete_call_found


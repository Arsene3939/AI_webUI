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
    upload_media_file,
    queue_prompt,
    download_output_file,
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

    @patch("comfy_client.check_server")
    @patch("os.path.exists")
    def test_start_comfyui_backend_missing_main(self, mock_exists, mock_check):
        """When main.py cannot be found, report clear error message."""
        mock_check.return_value = (False, "Offline")
        # Pretend main.py does not exist
        mock_exists.return_value = False

        ok, msg = start_comfyui_backend("http://127.0.0.1:8188")
        assert ok is False
        assert "找不到 ComfyUI 核心主程式" in msg

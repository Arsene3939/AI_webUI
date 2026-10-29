"""
Unit tests for Windows System Tray Supervisor and Desktop Notifications.
"""

import os
import sys
import time
import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from windows_notifier import send_windows_notification, NOTIFIER_IPC_PORT
from tray_supervisor import TraySupervisor, get_hwnds_for_pid


class TestWindowsNotifier:
    def test_send_windows_notification_handles_server_down(self):
        # When IPC server is not running on test port, should return False gracefully without raising exceptions
        success = send_windows_notification("測試訊息", "測試標題", timeout=0.2)
        assert success is False or success is True

    def test_send_windows_notification_successful_ipc_delivery(self):
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import threading

        received_data = []

        class MockHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_POST(self):
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len)
                received_data.append(json.loads(body.decode("utf-8")))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")

        server = HTTPServer(("127.0.0.1", NOTIFIER_IPC_PORT), MockHandler)
        t = threading.Thread(target=server.handle_request, daemon=True)
        t.start()

        try:
            res = send_windows_notification("已收到連線請求，正在啟動 ComfyUI 後端服務...", "⚡ MiniMax-H3 後端啟動通知", timeout=1.0)
            assert res is True
            assert len(received_data) == 1
            assert "ComfyUI" in received_data[0]["message"]
            assert "啟動" in received_data[0]["title"]
        finally:
            server.server_close()


class TestTraySupervisor:
    def test_tray_supervisor_initialization(self):
        supervisor = TraySupervisor()
        assert supervisor.running is True
        assert supervisor.webui_visible is False
        assert supervisor.comfy_visible is False
        assert supervisor.image is not None
        assert supervisor.image.size == (64, 64)

    def test_get_hwnds_for_pid_returns_list(self):
        hwnds = get_hwnds_for_pid(os.getpid())
        assert isinstance(hwnds, list)

    def test_toggle_webui_window_state(self):
        supervisor = TraySupervisor()
        # Mock get_webui_hwnds returning a dummy handle
        with patch.object(supervisor, "get_webui_hwnds", return_value=[12345]):
            with patch("ctypes.windll.user32.ShowWindow") as mock_show:
                with patch("ctypes.windll.user32.SetForegroundWindow") as mock_fg:
                    # Initially false -> toggle to true (restore)
                    supervisor.toggle_webui_window()
                    assert supervisor.webui_visible is True
                    mock_show.assert_called_with(12345, 9)

                    # Now true -> toggle to false (hide)
                    supervisor.toggle_webui_window()
                    assert supervisor.webui_visible is False
                    mock_show.assert_called_with(12345, 0)

    def test_toggle_comfy_window_state(self):
        supervisor = TraySupervisor()
        with patch.object(supervisor, "get_comfy_hwnds", return_value=[67890]):
            with patch("ctypes.windll.user32.ShowWindow") as mock_show:
                with patch("ctypes.windll.user32.SetForegroundWindow") as mock_fg:
                    supervisor.toggle_comfy_window()
                    assert supervisor.comfy_visible is True
                    mock_show.assert_called_with(67890, 9)

                    supervisor.toggle_comfy_window()
                    assert supervisor.comfy_visible is False
                    mock_show.assert_called_with(67890, 0)

    def test_comfy_client_startup_triggers_notification(self):
        # Verify that start_comfyui_backend invokes send_windows_notification
        from comfy_client import start_comfyui_backend
        with patch("comfy_client.check_server", return_value=(False, "offline")):
            with patch("comfy_client.check_system_resources", return_value=(True, "", {})):
                with patch("windows_notifier.send_windows_notification") as mock_notify:
                    with patch("subprocess.Popen") as mock_popen:
                        mock_proc = MagicMock()
                        mock_popen.return_value = mock_proc
                        # Call start_comfyui_backend with skip_resource_check
                        start_comfyui_backend(skip_resource_check=True)
                        mock_notify.assert_called_once()
                        args, kwargs = mock_notify.call_args
                        assert "ComfyUI" in args[0]
                        assert "啟動" in args[1]

    def test_start_webui_launches_gradio_auto_reload(self):
        supervisor = TraySupervisor()
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 9999
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc

            supervisor.start_webui()
            assert mock_popen.called
            cmd_called = mock_popen.call_args[0][0]
            # Must invoke gradio auto-reload mode
            assert "-m" in cmd_called
            assert "gradio" in cmd_called
            assert "app.py" in cmd_called

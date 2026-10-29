"""
Tray Supervisor for MiniMax-H3 Server.
Unified Windows System Tray manager that:
  1. Sets Windows Application User Model ID (MiniMaxH3.AIWebUI.Server) with custom icon.
  2. Spawns frontend WebUI and monitors backend ComfyUI in background without popping up consoles.
  3. Provides an integrated System Tray icon with dedicated controls for WebUI and ComfyUI:
     - 顯示 / 隱藏 WebUI 終端機 (Toggle)
     - 顯示 / 隱藏 ComfyUI 終端機 (Toggle)
     - 🌐 開啟 WebUI 網頁 (Browser)
     - ⚡ 啟動 / 重啟 ComfyUI 後端
     - 🛑 停止 ComfyUI 後端
     - ❌ 結束並關閉所有服務 (Graceful exit)
  4. Intercepts terminal minimize events so windows retract into tray rather than taskbar.
  5. Listens on local IPC port for backend startup requests and displays Windows native notifications.
"""

import os
import sys
import time
import json
import ctypes
import socket
import webbrowser
import threading
import subprocess
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, List, Dict, Any

from PIL import Image
import pystray
from pystray import MenuItem as item, Menu

# Windows Win32 API Definitions
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOW = 5
SW_RESTORE = 9

# Set Application User Model ID
APP_ID = "MiniMaxH3.AIWebUI.Server"
try:
    shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
except Exception:
    pass

PROJECT_ROOT = Path(__file__).parent.resolve()
PYTHON_EXE = r"F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
COMFY_ROOT = r"F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
ICON_PATH = PROJECT_ROOT / "assets" / "app_icon.png"
NOTIFIER_IPC_PORT = 29177


def get_hwnds_for_pid(pid: int) -> List[int]:
    """Finds all top-level window handles (HWNDs) associated with a process and its children."""
    hwnds: List[int] = []
    if not pid:
        return hwnds

    # Collect target PID and any child process PIDs (e.g. conhost.exe)
    pids = {pid}
    try:
        import psutil
        proc = psutil.Process(pid)
        for child in proc.children(recursive=True):
            pids.add(child.pid)
    except Exception:
        pass

    from ctypes import wintypes
    def enum_cb(hwnd, lparam):
        lpdw = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw))
        if lpdw.value in pids:
            hwnds.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return hwnds


class TraySupervisor:
    def __init__(self):
        self.webui_process: Optional[subprocess.Popen] = None
        self.webui_visible = False
        self.comfy_visible = False
        self.running = True
        self.icon: Optional[pystray.Icon] = None

        # Load or generate icon
        if ICON_PATH.exists():
            self.image = Image.open(ICON_PATH)
        else:
            self.image = Image.new("RGB", (64, 64), color=(37, 99, 235))

    def start_webui(self):
        """Starts the frontend WebUI in the background without popping up a console."""
        app_script = str(PROJECT_ROOT / "app.py")
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = SW_HIDE

        # Launch in Auto-Reload Mode (equivalent to gradio app.py with file watcher)
        cmd = [PYTHON_EXE, "-m", "gradio", "app.py"]
        self.webui_process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            startupinfo=si,
        )

    def get_webui_hwnds(self) -> List[int]:
        if self.webui_process and self.webui_process.poll() is None:
            return get_hwnds_for_pid(self.webui_process.pid)
        return []

    def get_comfy_hwnds(self) -> List[int]:
        """Discovers any running ComfyUI process HWNDs (e.g. main.py on port 8188)."""
        import psutil
        comfy_pids = set()
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = p.info.get("cmdline") or []
                cmd_str = " ".join(cmdline)
                if "main.py" in cmd_str and ("8188" in cmd_str or "ComfyUI" in cmd_str):
                    comfy_pids.add(p.info["pid"])
                    for child in p.children(recursive=True):
                        comfy_pids.add(child.pid)
            except Exception:
                continue

        hwnds = []
        if comfy_pids:
            from ctypes import wintypes
            def enum_cb(hwnd, lparam):
                lpdw = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw))
                if lpdw.value in comfy_pids:
                    hwnds.append(hwnd)
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return hwnds

    def toggle_webui_window(self):
        hwnds = self.get_webui_hwnds()
        if not hwnds:
            # If not started or crashed, attempt restart
            self.start_webui()
            self.webui_visible = False
            return

        if self.webui_visible:
            for h in hwnds:
                user32.ShowWindow(h, SW_HIDE)
            self.webui_visible = False
        else:
            for h in hwnds:
                user32.ShowWindow(h, SW_RESTORE)
                user32.SetForegroundWindow(h)
            self.webui_visible = True

    def toggle_comfy_window(self):
        hwnds = self.get_comfy_hwnds()
        if not hwnds:
            if self.icon:
                self.icon.notify("ComfyUI 後端目前未在運作中，請自選單點擊啟動", "MiniMax-H3 伺服器")
            return

        if self.comfy_visible:
            for h in hwnds:
                user32.ShowWindow(h, SW_HIDE)
            self.comfy_visible = False
        else:
            for h in hwnds:
                user32.ShowWindow(h, SW_RESTORE)
                user32.SetForegroundWindow(h)
            self.comfy_visible = True

    def trigger_start_comfy(self):
        def _start():
            try:
                sys.path.insert(0, str(PROJECT_ROOT))
                from comfy_client import start_comfyui_backend
                ok, msg = start_comfyui_backend(skip_resource_check=True)
                if self.icon:
                    self.icon.notify(msg, "ComfyUI 後端狀態")
            except Exception as e:
                if self.icon:
                    self.icon.notify(f"啟動失敗: {e}", "ComfyUI 後端狀態")
        threading.Thread(target=_start, daemon=True).start()

    def trigger_stop_comfy(self):
        def _stop():
            try:
                sys.path.insert(0, str(PROJECT_ROOT))
                from comfy_client import stop_comfyui_backend
                ok, msg = stop_comfyui_backend()
                if self.icon:
                    self.icon.notify(msg, "ComfyUI 後端狀態")
            except Exception as e:
                if self.icon:
                    self.icon.notify(f"停止失敗: {e}", "ComfyUI 後端狀態")
        threading.Thread(target=_stop, daemon=True).start()

    def open_browser(self):
        webbrowser.open("http://127.0.0.1:7860")

    def exit_all(self):
        self.running = False
        # Stop WebUI process
        if self.webui_process and self.webui_process.poll() is None:
            try:
                import psutil
                parent = psutil.Process(self.webui_process.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except Exception:
                self.webui_process.kill()

        # Stop ComfyUI backend
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from comfy_client import stop_comfyui_backend
            stop_comfyui_backend()
        except Exception:
            pass

        if self.icon:
            self.icon.stop()

    def monitor_minimize_loop(self):
        """
        Background daemon thread:
        Inspects visible windows. If the user clicks the minimize button ('-'),
        Windows flags the window with IsIconic(hwnd) == True.
        We immediately catch this and call ShowWindow(hwnd, SW_HIDE) so the terminal
        is tucked neatly into the Windows System Tray rather than lingering on the taskbar.
        """
        while self.running:
            time.sleep(0.15)
            # Check WebUI window
            if self.webui_visible:
                hwnds = self.get_webui_hwnds()
                for h in hwnds:
                    if user32.IsIconic(h):
                        user32.ShowWindow(h, SW_HIDE)
                        self.webui_visible = False

            # Check ComfyUI window
            if self.comfy_visible:
                hwnds = self.get_comfy_hwnds()
                for h in hwnds:
                    if user32.IsIconic(h):
                        user32.ShowWindow(h, SW_HIDE)
                        self.comfy_visible = False

    def start_ipc_notification_server(self):
        """Listens on local IPC port for notifications sent by WebUI / ComfyUI client."""
        supervisor = self

        class NotificationHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_POST(self):
                try:
                    content_len = int(self.headers.get("Content-Length", 0))
                    data = self.rfile.read(content_len)
                    payload = json.loads(data.decode("utf-8"))
                    title = payload.get("title", "MiniMax-H3 系統通知")
                    message = payload.get("message", "")
                    if supervisor.icon:
                        supervisor.icon.notify(message, title)
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"OK")
                except Exception:
                    self.send_response(500)
                    self.end_headers()

        def _run_server():
            try:
                server = HTTPServer(("127.0.0.1", NOTIFIER_IPC_PORT), NotificationHandler)
                while supervisor.running:
                    server.handle_request()
                server.server_close()
            except Exception:
                pass

        threading.Thread(target=_run_server, daemon=True).start()

    def run(self):
        # 1. Start WebUI in background
        self.start_webui()

        # 2. Start IPC Notification server
        self.start_ipc_notification_server()

        # 3. Start Window Minimize Watcher
        threading.Thread(target=self.monitor_minimize_loop, daemon=True).start()

        # 4. Build System Tray Menu
        menu = Menu(
            item(
                "🎬 WebUI 前端終端機 (顯示 / 隱藏)",
                lambda icon, item: self.toggle_webui_window(),
                default=True,
            ),
            item(
                "⚡ ComfyUI 後端終端機 (顯示 / 隱藏)",
                lambda icon, item: self.toggle_comfy_window(),
            ),
            Menu.SEPARATOR,
            item(
                "🌐 開啟 WebUI 網頁",
                lambda icon, item: self.open_browser(),
            ),
            Menu.SEPARATOR,
            item(
                "▶️ 啟動 ComfyUI 後端",
                lambda icon, item: self.trigger_start_comfy(),
            ),
            item(
                "⏹️ 停止 ComfyUI 後端",
                lambda icon, item: self.trigger_stop_comfy(),
            ),
            Menu.SEPARATOR,
            item(
                "❌ 退出並關閉所有服務",
                lambda icon, item: self.exit_all(),
            ),
        )

        self.icon = pystray.Icon(
            "MiniMaxH3_Supervisor",
            self.image,
            "MiniMax-H3 AI 影片生成系統",
            menu=menu,
        )

        # Notify user that server has started in tray
        def _startup_notify():
            time.sleep(1.5)
            if self.icon:
                self.icon.notify("MiniMax-H3 伺服器已在 Windows 系統匣常駐執行", "MiniMax-H3 伺服器啟動完成")
        threading.Thread(target=_startup_notify, daemon=True).start()

        self.icon.run()


if __name__ == "__main__":
    supervisor = TraySupervisor()
    supervisor.run()

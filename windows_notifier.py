"""
Windows Notification Helper for MiniMax-H3 Server.
Dispatches desktop notifications to the Windows System Tray supervisor via IPC,
or falls back gracefully to logging if the tray supervisor is not active.
"""
import os
import json
import socket
import urllib.request
from typing import Optional

NOTIFIER_IPC_PORT = int(os.environ.get("TRAY_NOTIFIER_PORT", "29177"))


def send_windows_notification(message: str, title: str = "MiniMax-H3 系統通知", timeout: float = 1.0) -> bool:
    """
    Sends a desktop notification to the Tray supervisor process via local IPC.
    Returns True if successfully received by tray supervisor, False otherwise.
    """
    try:
        url = f"http://127.0.0.1:{NOTIFIER_IPC_PORT}/notify"
        payload = json.dumps({"title": title, "message": message}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

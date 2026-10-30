"""
Thread-safe Task Manager for MiniMax-H3 WebUI with per-device isolation.
Ensures generation jobs continue running in the background while keeping different devices strictly isolated.

Spec 2026-10-31（taskmanager 模組化）：實作已拆至子模組，本 package 是**穩定外部介面**——
app / components / core / views / e2e / tests 的 import 完全不用改。
    from task_manager import task_manager, Task, TaskManager

拆分地圖（子模組只能經本 package 延遲讀取下方常數與 comfy_client 名稱，
測試的 monkeypatch（task_manager.HISTORY_FILE / task_manager.queue_prompt /
task_manager.requests.get）才會在呼叫點生效）：
    models.py         Task 資料模型 + 裝置比對
    history_store.py  JSON 歷史持久化（top-100、原子寫入、重啟降格殭屍佇列）
    media_archive.py  上傳媒體歸檔與清除（恢復上次輸入的來源）
    server_sync.py    ComfyUI /history + /queue 同步、開機 orphan 核對、prompt 存活探測
    comfy_progress.py 提交工作流 + WebSocket 進度監聽 + 輪詢/看門狗
    manager.py        TaskManager（任務註冊表、裝置查詢、FIFO 串列調度器、單例）
"""
import os

import requests  # noqa: F401  (tests patch task_manager.requests.get through this name)

from config import COMFY_SERVER_URL, OUTPUT_DIR
from comfy_client import (
    queue_prompt,
    download_output_file,
    check_server,
)

HISTORY_FILE = os.path.join(OUTPUT_DIR, "task_history.json")
INPUTS_ARCHIVE_DIR = os.path.join(OUTPUT_DIR, "inputs")
os.makedirs(INPUTS_ARCHIVE_DIR, exist_ok=True)

# 必須在上述常數之後匯入：manager 在匯入時即建立單例並載入歷史，
# 載入流程會经 _pkg 讀取 HISTORY_FILE。
from .models import Task, _is_same_device  # noqa: E402
from .manager import TaskManager, task_manager  # noqa: E402

__all__ = [
    "Task", "TaskManager", "task_manager",
    "HISTORY_FILE", "INPUTS_ARCHIVE_DIR", "OUTPUT_DIR", "COMFY_SERVER_URL",
    "queue_prompt", "download_output_file", "check_server", "requests",
]

"""
Thread-safe Task Manager for MiniMax-H3 WebUI.
Ensures generation jobs continue running in the background even if mobile phones sleep,
switch tabs, or drop network connection.
"""
import os
import json
import time
import uuid
import threading
from typing import Dict, Any, Optional, List
import requests
from config import COMFY_SERVER_URL, OUTPUT_DIR
from comfy_client import queue_prompt, download_output_file, check_server

HISTORY_FILE = os.path.join(OUTPUT_DIR, "task_history.json")


class Task:
    def __init__(
        self,
        task_id: str,
        task_type: str,
        prompt: str,
        params: Dict[str, Any],
    ):
        self.task_id = task_id
        self.task_type = task_type  # 'I2V', 'T2V', 'R2V'
        self.prompt = prompt
        self.params = params
        self.prompt_id: Optional[str] = None
        self.status = "queued"  # 'queued', 'running', 'completed', 'failed'
        self.progress = 0.05
        self.message = "⏳ 任務已排隊..."
        self.video_path: Optional[str] = None
        self.created_at = time.time()
        self.completed_at: Optional[float] = None
        self.elapsed: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "prompt_id": self.prompt_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "video_path": self.video_path,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "elapsed": self.elapsed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        t = cls(
            task_id=data["task_id"],
            task_type=data.get("task_type", "I2V"),
            prompt=data.get("prompt", ""),
            params={},
        )
        t.prompt_id = data.get("prompt_id")
        t.status = data.get("status", "completed")
        t.progress = data.get("progress", 1.0)
        t.message = data.get("message", "")
        t.video_path = data.get("video_path")
        t.created_at = data.get("created_at", time.time())
        t.completed_at = data.get("completed_at")
        t.elapsed = data.get("elapsed", 0.0)
        return t


class TaskManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: Dict[str, Task] = {}
        self._latest_task_id: Optional[str] = None
        self._load_history()

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        t = Task.from_dict(item)
                        self._tasks[t.task_id] = t
                        self._latest_task_id = t.task_id
            except Exception:
                pass

    def _save_history(self):
        try:
            items = []
            with self._lock:
                # Save latest 50 completed tasks
                for t in sorted(self._tasks.values(), key=lambda x: x.created_at, reverse=True)[:50]:
                    items.append(t.to_dict())
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def create_task(self, task_type: str, prompt: str, params: Dict[str, Any]) -> Task:
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        task = Task(task_id, task_type, prompt, params)
        with self._lock:
            self._tasks[task_id] = task
            self._latest_task_id = task_id
        return task

    def get_task(self, task_id: Optional[str]) -> Optional[Task]:
        if not task_id:
            return None
        with self._lock:
            return self._tasks.get(task_id)

    def get_latest_task(self) -> Optional[Task]:
        with self._lock:
            if self._latest_task_id:
                return self._tasks.get(self._latest_task_id)
            return None

    def get_all_completed_tasks(self) -> List[Task]:
        with self._lock:
            tasks = [t for t in self._tasks.values() if t.status == "completed" and t.video_path and os.path.exists(t.video_path)]
            return sorted(tasks, key=lambda x: x.created_at, reverse=True)

    def start_background_task(self, task: Task, prompt_graph: Dict[str, Any], server_url: str = COMFY_SERVER_URL):
        """Starts a detached thread to submit to ComfyUI and monitor progress."""
        thread = threading.Thread(
            target=self._monitor_worker,
            args=(task, prompt_graph, server_url),
            daemon=True,
        )
        thread.start()

    def _monitor_worker(self, task: Task, prompt_graph: Dict[str, Any], server_url: str):
        task.status = "running"
        task.message = "📤 正在向 ComfyUI 提交工作流..."
        task.progress = 0.08

        client_id = str(uuid.uuid4())
        try:
            prompt_id = queue_prompt(prompt_graph, client_id, server_url)
            task.prompt_id = prompt_id
            task.message = f"⏳ 已加入 ComfyUI 排程隊列 (ID: {prompt_id[:8]})..."
            task.progress = 0.15
        except Exception as e:
            task.status = "failed"
            task.message = f"❌ 提交失敗: {str(e)}"
            self._save_history()
            return

        start_time = time.time()
        while True:
            elapsed = round(time.time() - start_time, 1)
            task.elapsed = elapsed

            # 1. Check if finished in history
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
                                    task.message = "📥 影片生成完畢，正在儲存至伺服器..."
                                    task.progress = 0.95
                                    local_path = download_output_file(fn, subfolder, folder_type, server_url)
                                    task.video_path = local_path
                                    task.status = "completed"
                                    task.progress = 1.0
                                    task.completed_at = time.time()
                                    task.message = f"✅ 影片生成完成！總耗時 {elapsed} 秒"
                                    self._save_history()
                                    return
            except Exception:
                pass

            # 2. Check queue position / running state
            try:
                q_resp = requests.get(f"{server_url}/queue", timeout=5)
                if q_resp.status_code == 200:
                    q_data = q_resp.json()
                    running = [item[1] for item in q_data.get("queue_running", [])]
                    pending = [item[1] for item in q_data.get("queue_pending", [])]

                    if task.prompt_id in running:
                        task.progress = min(0.92, 0.25 + (elapsed / 180.0) * 0.65)
                        task.message = f"⚡ MiniMax-H3 音視訊運算中... (已耗時 {int(elapsed)}s - 手機可鎖屏待機)"
                    elif task.prompt_id in pending:
                        task.progress = 0.18
                        task.message = f"⏳ 排隊等待執行中... (已等待 {int(elapsed)}s)"
            except Exception:
                pass

            # 3. Timeout safeguard (15 minutes)
            if elapsed > 900:
                task.status = "failed"
                task.message = "⚠️ 任務超時 (超過 15 分鐘)，請檢查後端終端機。"
                self._save_history()
                return

            time.sleep(2)


# Global singleton instance
task_manager = TaskManager()

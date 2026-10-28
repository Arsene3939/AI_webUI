"""
Thread-safe Task Manager for MiniMax-H3 WebUI with per-device isolation.
Ensures generation jobs continue running in the background while keeping different devices strictly isolated.
"""
import os
import json
import time
import uuid
import shutil
import threading
import asyncio
import websockets
from typing import Dict, Any, Optional, List
import requests
from config import (
    COMFY_SERVER_URL,
    OUTPUT_DIR,
    normalize_quality_choice,
    normalize_aspect_ratio,
    normalize_sampler,
    normalize_scheduler,
)
from comfy_client import queue_prompt, download_output_file, check_server
from logger import get_logger

logger = get_logger("TaskManager")

HISTORY_FILE = os.path.join(OUTPUT_DIR, "task_history.json")
INPUTS_ARCHIVE_DIR = os.path.join(OUTPUT_DIR, "inputs")
os.makedirs(INPUTS_ARCHIVE_DIR, exist_ok=True)


class Task:
    def __init__(
        self,
        task_id: str,
        task_type: str,
        prompt: str,
        params: Dict[str, Any],
        device_id: str = "default",
    ):
        self.task_id = task_id
        self.task_type = task_type  # 'I2V', 'T2V', 'R2V'
        self.prompt = prompt
        self.params = params or {}
        self.device_id = device_id
        self.prompt_id: Optional[str] = None
        self.status = "queued"  # 'queued', 'running', 'completed', 'failed'
        self.progress = 0.05
        self.message = "⚡ 前處理中：任務已建立..."
        self.video_path: Optional[str] = None
        self.created_at = time.time()
        self.completed_at: Optional[float] = None
        self.elapsed: float = 0.0
        self.step: int = 0
        self.total_steps: int = 0
        self.stage: str = "preprocessing"
        self.current_node: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "params": self.params,
            "device_id": self.device_id,
            "prompt_id": self.prompt_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "video_path": self.video_path,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "elapsed": self.elapsed,
            "step": self.step,
            "total_steps": self.total_steps,
            "stage": self.stage,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        t = cls(
            task_id=data["task_id"],
            task_type=data.get("task_type", "I2V"),
            prompt=data.get("prompt", ""),
            params=data.get("params", {}),
            device_id=data.get("device_id", "default"),
        )
        t.prompt_id = data.get("prompt_id")
        t.status = data.get("status", "completed")
        t.progress = data.get("progress", 1.0)
        t.message = data.get("message", "")
        t.video_path = data.get("video_path")
        t.created_at = data.get("created_at", time.time())
        t.completed_at = data.get("completed_at")
        t.elapsed = data.get("elapsed", 0.0)
        t.step = data.get("step", 0)
        t.total_steps = data.get("total_steps", 0)
        t.stage = data.get("stage", "")
        return t


def _is_same_device(dev_a: Optional[str], dev_b: Optional[str]) -> bool:
    """Helper to check if two device IDs match, allowing for dev_ prefix variance."""
    if not dev_a or not dev_b:
        return False
    if dev_a == dev_b:
        return True
    if dev_a.startswith("dev_") and dev_a[4:] == dev_b:
        return True
    if dev_b.startswith("dev_") and dev_b[4:] == dev_a:
        return True
    return False


class TaskManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: Dict[str, Task] = {}
        self._load_history()

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        t = Task.from_dict(item)
                        if t.params:
                            if "quality_level" in t.params:
                                t.params["quality_level"] = normalize_quality_choice(t.params["quality_level"])
                            if "aspect_ratio" in t.params:
                                t.params["aspect_ratio"] = normalize_aspect_ratio(t.params["aspect_ratio"])
                            if "sampler" in t.params:
                                t.params["sampler"] = normalize_sampler(t.params["sampler"])
                            if "scheduler" in t.params:
                                t.params["scheduler"] = normalize_scheduler(t.params["scheduler"])
                        self._tasks[t.task_id] = t
                logger.info("Loaded %d task(s) from history file: %s", len(self._tasks), HISTORY_FILE)
            except Exception as e:
                logger.warning("Failed to load task history: %s", e)

    def _save_history(self):
        try:
            items = []
            with self._lock:
                for t in sorted(self._tasks.values(), key=lambda x: x.created_at, reverse=True)[:100]:
                    items.append(t.to_dict())
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _archive_file(self, file_path: Optional[str], task_id: str, prefix: str) -> Optional[str]:
        if not file_path or not os.path.exists(file_path):
            return None
        try:
            ext = os.path.splitext(file_path)[1]
            dest_name = f"{task_id}_{prefix}{ext}"
            dest_path = os.path.join(INPUTS_ARCHIVE_DIR, dest_name)
            shutil.copy2(file_path, dest_path)
            return dest_path
        except Exception:
            return file_path

    def create_task(
        self,
        task_type: str,
        prompt: str,
        params: Dict[str, Any],
        device_id: str = "default",
    ) -> Task:
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        
        # Archive media files so they persist for later restoration
        saved_params = dict(params)
        for k, v in list(saved_params.items()):
            if isinstance(v, str) and os.path.isfile(v):
                saved_params[k] = self._archive_file(v, task_id, k)

        task = Task(task_id, task_type, prompt, saved_params, device_id=device_id)
        task.stage = "preprocessing"
        task.message = "⚡ 前處理中：正在準備提交任務..."
        with self._lock:
            self._tasks[task_id] = task
        self._save_history()
        logger.info("[Task %s] Created [%s] for device '%s' (Prompt: '%s')", task_id, task_type, device_id, prompt[:50])
        return task

    def sync_task_with_server(self, task: Optional[Task], server_url: str = COMFY_SERVER_URL) -> Optional[Task]:
        """
        Synchronizes a task's state with ComfyUI.
        If the task finished in the background or during standby/restart,
        automatically downloads the completed video and updates task status.
        """
        if not task or not task.prompt_id:
            return task

        # Already completed and file exists locally
        if task.status == "completed" and task.video_path and os.path.exists(task.video_path):
            return task

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
                                local_path = download_output_file(fn, subfolder, folder_type, server_url)
                                task.video_path = local_path
                                task.status = "completed"
                                task.progress = 1.0
                                task.completed_at = time.time()
                                task.message = f"✅ 影片生成完成！耗時 {task.elapsed} 秒"
                                self._save_history()
                                return task

                status_info = history.get("status", {})
                if status_info.get("status_str") == "error":
                    task.status = "failed"
                    task.message = "❌ 生成失敗，請查看後端錯誤記錄。"
                    self._save_history()
                    return task
        except Exception:
            pass

        return task

    def get_task(self, task_id: Optional[str], device_id: Optional[str] = None) -> Optional[Task]:
        if not task_id:
            return None
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            if device_id and not _is_same_device(task.device_id, device_id):
                # Strictly isolate from other devices!
                return None

        # Synchronize with ComfyUI if task is missing video
        if task and task.prompt_id and (not task.video_path or not os.path.exists(task.video_path)):
            self.sync_task_with_server(task)

        return task

    def get_latest_task_for_device(self, device_id: Optional[str]) -> Optional[Task]:
        if not device_id:
            return None
        with self._lock:
            matching = [t for t in self._tasks.values() if _is_same_device(t.device_id, device_id)]
            if not matching:
                return None
            task = max(matching, key=lambda x: x.created_at)

        # Synchronize with ComfyUI if task is missing video
        if task and task.prompt_id and (not task.video_path or not os.path.exists(task.video_path)):
            self.sync_task_with_server(task)

        return task

    def get_completed_tasks_for_device(self, device_id: Optional[str]) -> List[Task]:
        if not device_id:
            return []
        with self._lock:
            candidates = [t for t in self._tasks.values() if _is_same_device(t.device_id, device_id)]

        for t in candidates:
            if t.prompt_id and (not t.video_path or not os.path.exists(t.video_path)):
                self.sync_task_with_server(t)

        with self._lock:
            tasks = [
                t for t in self._tasks.values()
                if _is_same_device(t.device_id, device_id) and t.status == "completed" and t.video_path and os.path.exists(t.video_path)
            ]
            return sorted(tasks, key=lambda x: x.created_at, reverse=True)

    def start_background_task(self, task: Task, prompt_graph: Dict[str, Any], server_url: Optional[str] = None):
        """Starts a detached thread to submit to ComfyUI and monitor progress."""
        server_url = server_url or COMFY_SERVER_URL
        logger.info("[Task %s] Dispatching to background worker thread...", task.task_id)
        thread = threading.Thread(
            target=self._monitor_worker,
            args=(task, prompt_graph, server_url),
            daemon=True,
        )
        thread.start()

    def _ws_listener(self, ws_url: str, client_id: str, prompt_id: str, task: Task, stop_event: threading.Event):
        """Listens to ComfyUI websocket for real-time progress steps and executing node names."""
        async def listen():
            full_ws = f"{ws_url}/ws?clientId={client_id}"
            try:
                async with websockets.connect(full_ws, ping_timeout=20, close_timeout=5) as ws:
                    logger.debug("[Task %s] WebSocket connected to %s", task.task_id, full_ws)
                    while not stop_event.is_set():
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue
                        if isinstance(msg, str):
                            event = json.loads(msg)
                            etype = event.get("type")
                            data = event.get("data", {})
                            if etype == "progress":
                                v = data.get("value", 0)
                                m = data.get("max", 1)
                                if m > 0:
                                    task.step = v
                                    task.total_steps = m
                                    task.progress = min(0.95, max(0.15, 0.15 + (v / m) * 0.77))
                                    if v < m:
                                        task.stage = "sampling"
                                    else:
                                        task.stage = "postprocessing"
                            elif etype == "executing":
                                node = data.get("node")
                                p_id = data.get("prompt_id")
                                if p_id == prompt_id:
                                    if node is None:
                                        task.stage = "completed"
                                    else:
                                        task.current_node = str(node)
                                        node_str = str(node).lower()
                                        if any(k in node_str for k in ["vae_decode", "create_video", "save_video"]):
                                            task.stage = "postprocessing"
                                        elif any(k in node_str for k in ["sampler", "sampling"]):
                                            task.stage = "sampling"
                                        elif task.stage not in ("sampling", "postprocessing"):
                                            task.stage = "preprocessing"
            except Exception as e:
                logger.debug("[Task %s] WebSocket closed or unreachable: %s", task.task_id, e)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(listen())
        except Exception:
            pass
        finally:
            loop.close()

    def _monitor_worker(self, task: Task, prompt_graph: Dict[str, Any], server_url: str):
        task.status = "running"
        task.stage = "preprocessing"
        task.message = "⚡ 前處理中：正在提交任務至後端..."
        task.progress = 0.08
        logger.info("[Task %s] Submitting workflow graph to ComfyUI (%s)...", task.task_id, server_url)

        client_id = str(uuid.uuid4())
        try:
            prompt_id = queue_prompt(prompt_graph, client_id, server_url)
            task.prompt_id = prompt_id
            task.message = f"⏳ 排隊中 (ID: {prompt_id[:8]})..."
            task.progress = 0.15
            logger.info("[Task %s] Prompt queued successfully! Assigned ComfyUI prompt_id: %s", task.task_id, prompt_id)
        except Exception as e:
            task.status = "failed"
            task.stage = "failed"
            task.message = f"❌ 提交失敗: {str(e)}"
            self._save_history()
            logger.error("[Task %s] Failed to queue prompt to ComfyUI: %s", task.task_id, e)
            return

        # Start WebSocket progress listener for real-time steps
        stop_ws = threading.Event()
        ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_thread = threading.Thread(
            target=self._ws_listener,
            args=(ws_url, client_id, task.prompt_id, task, stop_ws),
            daemon=True,
        )
        ws_thread.start()

        start_time = time.time()
        last_logged_step = -1
        last_logged_stage = task.stage

        while True:
            elapsed = round(time.time() - start_time, 1)
            task.elapsed = elapsed

            # Format human-readable elapsed time (seconds, minutes, or hours)
            hrs = int(elapsed // 3600)
            mins = int((elapsed % 3600) // 60)
            secs = int(elapsed % 60)
            if hrs > 0:
                time_str = f"{hrs}小時{mins}分{secs}秒"
            elif mins > 0:
                time_str = f"{mins}分{secs}秒"
            else:
                time_str = f"{secs}秒"

            # Log stage changes
            if task.stage != last_logged_stage:
                logger.info("[Task %s] Stage changed -> %s (%s)", task.task_id, task.stage, task.message)
                last_logged_stage = task.stage

            # Log step progress
            if task.stage == "sampling" and task.step != last_logged_step and task.total_steps > 0:
                logger.info("[Task %s] Sampling: %d/%d steps (%d%%, elapsed: %s)",
                            task.task_id, task.step, task.total_steps, int(task.progress * 100), time_str)
                last_logged_step = task.step

            # 1. Check if finished or failed in ComfyUI history
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
                                    task.stage = "postprocessing"
                                    task.message = f"⚡ 後處理中：正在儲存並下載影片... (耗時 {time_str})"
                                    task.progress = 0.95
                                    logger.info("[Task %s] Output detected in ComfyUI: %s. Downloading...", task.task_id, fn)
                                    local_path = download_output_file(fn, subfolder, folder_type, server_url)
                                    task.video_path = local_path
                                    task.status = "completed"
                                    task.stage = "completed"
                                    task.progress = 1.0
                                    task.completed_at = time.time()
                                    task.message = f"✅ 影片生成完成！耗時 {time_str}"
                                    stop_ws.set()
                                    self._save_history()
                                    logger.info("[Task %s] Completed! Saved to: %s (Total time: %s)", task.task_id, local_path, time_str)
                                    return

                    status_info = history.get("status", {})
                    if status_info.get("status_str") == "error":
                        task.status = "failed"
                        task.stage = "failed"
                        task.message = "❌ 生成失敗，請查看後端錯誤記錄。"
                        stop_ws.set()
                        self._save_history()
                        logger.error("[Task %s] ComfyUI reported execution error: %s", task.task_id, status_info)
                        return
            except Exception as e:
                logger.debug("[Task %s] History check exception: %s", task.task_id, e)

            # 2. Check queue position / running state
            try:
                q_resp = requests.get(f"{server_url}/queue", timeout=5)
                if q_resp.status_code == 200:
                    q_data = q_resp.json()
                    running = [item[1] for item in q_data.get("queue_running", [])]
                    pending = [item[1] for item in q_data.get("queue_pending", [])]

                    if task.total_steps > 0 and task.step >= task.total_steps:
                        task.stage = "postprocessing"
                        task.message = f"⚡ 後處理中 (解碼與合成影片)... (耗時 {time_str})"
                    elif task.stage == "postprocessing":
                        task.message = f"⚡ 後處理中 (解碼與合成影片)... (耗時 {time_str})"
                    elif task.total_steps > 0 and task.step > 0:
                        task.stage = "sampling"
                        task.message = f"⚡ 影片生成中: {task.step}/{task.total_steps} 步 (耗時 {time_str})"
                    elif task.prompt_id in running:
                        task.stage = "preprocessing"
                        task.progress = min(0.95, 0.25 + (elapsed / 1800.0) * 0.70)
                        task.message = f"⚡ 前處理中 (載入模型與特徵處理)... (耗時 {time_str})"
                    elif task.prompt_id in pending:
                        task.stage = "pending"
                        task.progress = 0.18
                        task.message = f"⏳ 排隊中... (已等待 {time_str})"
            except Exception as e:
                logger.debug("[Task %s] Queue poll exception: %s", task.task_id, e)

            time.sleep(0.5)

            time.sleep(0.5)


# Global singleton instance
task_manager = TaskManager()

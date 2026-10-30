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
from collections import deque
import websockets
from typing import Dict, Any, Optional, List, Tuple
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
    MODULE_UPSCALER = "upscaler"
    MODULE_STRATA = "strata"
    MODULE_MINIMAX = "minimax"

    @staticmethod
    def derive_module(task_type: Optional[str]) -> str:
        """Infers owning module from task_type for legacy history records without an explicit module."""
        t = (task_type or "").upper()
        if t == "UPSCALER":
            return Task.MODULE_UPSCALER
        if t == "STRATA":
            return Task.MODULE_STRATA
        return Task.MODULE_MINIMAX

    def __init__(
        self,
        task_id: str,
        task_type: str,
        prompt: str,
        params: Dict[str, Any],
        device_id: str = "default",
        module: Optional[str] = None,
    ):
        self.task_id = task_id
        self.task_type = task_type  # 'I2V', 'T2V', 'R2V', 'UPSCALER'
        self.module = module or Task.derive_module(task_type)  # 'minimax' | 'upscaler' | 'strata'
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
        self.cancel_event: threading.Event = threading.Event()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "module": self.module,
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
            module=data.get("module"),  # Legacy records without module are derived from task_type
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
        # --- Serial execution dispatcher (Spec: cross-module task queueing) ---
        # One GPU backend -> one workflow at a time. Tasks are held in a FIFO queue
        # and only submitted to ComfyUI by a single dispatcher thread when idle,
        # so minimax and upscaler jobs no longer preempt/step on each other.
        self._dispatch_cond = threading.Condition(self._lock)
        self._dispatch_queue: deque = deque()  # entries: (task_id, prompt_graph, server_url)
        self._dispatcher_started = False
        self._executing_task_id: Optional[str] = None
        self._load_history()

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    demoted = 0
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
                        # Zombie-queue guard: tasks marked queued/running that were never
                        # submitted to ComfyUI (prompt_id is None) were sitting in the WebUI
                        # dispatch queue when the server stopped. Nothing can resume them, and
                        # leaving them "active" would pin the device UI on 排隊中 forever.
                        if t.status in ("queued", "running") and not t.prompt_id:
                            t.status = "interrupted"
                            t.stage = "interrupted"
                            t.message = "⚠️ 工作已在排队时因伺服器重啟而遺失，請重新提交"
                            demoted += 1
                        self._tasks[t.task_id] = t
                logger.info("Loaded %d task(s) from history file: %s", len(self._tasks), HISTORY_FILE)
                if demoted:
                    logger.warning("Demoted %d never-submitted queued/running task(s) to interrupted after restart.", demoted)
                    self._save_history()
            except Exception as e:
                logger.warning("Failed to load task history: %s", e)

    def _save_history(self):
        try:
            items = []
            with self._lock:
                for t in sorted(self._tasks.values(), key=lambda x: x.created_at, reverse=True)[:100]:
                    items.append(t.to_dict())
            tmp_file = f"{HISTORY_FILE}.{uuid.uuid4().hex[:6]}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, HISTORY_FILE)
        except Exception:
            if "tmp_file" in locals() and os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
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
        module: Optional[str] = None,
    ) -> Task:
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        
        # Archive media files so they persist for later restoration
        saved_params = dict(params)
        for k, v in list(saved_params.items()):
            if isinstance(v, str) and os.path.isfile(v):
                saved_params[k] = self._archive_file(v, task_id, k)

        task = Task(task_id, task_type, prompt, saved_params, device_id=device_id, module=module)
        task.total_steps = int(saved_params.get("steps", 0))
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

        # Already completed, interrupted or file exists locally
        if task.status in ("completed", "interrupted"):
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

    def get_task(self, task_id: Optional[str], device_id: Optional[str] = None, module: Optional[str] = None) -> Optional[Task]:
        if not task_id:
            return None
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            if device_id and not _is_same_device(task.device_id, device_id):
                # Strictly isolate from other devices!
                return None
            if module and task.module != module:
                # Module-scoped views must never see other modules' tasks.
                return None

        # Synchronize with ComfyUI if task is missing video
        if task and task.prompt_id and (not task.video_path or not os.path.exists(task.video_path)):
            self.sync_task_with_server(task)

        return task

    def get_latest_task_for_device(self, device_id: Optional[str], module: Optional[str] = None) -> Optional[Task]:
        if not device_id:
            return None
        with self._lock:
            matching = [t for t in self._tasks.values() if _is_same_device(t.device_id, device_id)]
            if module:
                matching = [t for t in matching if t.module == module]
            if not matching:
                return None
            task = max(matching, key=lambda x: x.created_at)

        # Synchronize with ComfyUI if task is missing video
        if task and task.prompt_id and (not task.video_path or not os.path.exists(task.video_path)):
            self.sync_task_with_server(task)

        return task

    def get_completed_tasks_for_device(self, device_id: Optional[str], module: Optional[str] = None) -> List[Task]:
        if not device_id:
            return []
        with self._lock:
            candidates = [t for t in self._tasks.values() if _is_same_device(t.device_id, device_id)]
            if module:
                candidates = [t for t in candidates if t.module == module]

        for t in candidates:
            if t.prompt_id and (not t.video_path or not os.path.exists(t.video_path)):
                self.sync_task_with_server(t)

        with self._lock:
            tasks = [
                t for t in self._tasks.values()
                if _is_same_device(t.device_id, device_id) and t.status == "completed" and t.video_path and os.path.exists(t.video_path)
                and (not module or t.module == module)
            ]
            return sorted(tasks, key=lambda x: x.created_at, reverse=True)

    def get_active_task_for_device(self, device_id: Optional[str], module: Optional[str] = None) -> Optional[Task]:
        """Returns the active (queued or running) task for the specified device and module, if any."""
        if not device_id:
            return None
        with self._lock:
            for t in self._tasks.values():
                if _is_same_device(t.device_id, device_id) and t.status in ("queued", "running"):
                    if module and t.module != module:
                        continue
                    return t
            return None

    def get_active_tasks_overview(self) -> List[Task]:
        """Returns ALL queued/running tasks across every device and module (backend-shutdown guard)."""
        with self._lock:
            return [t for t in self._tasks.values() if t.status in ("queued", "running")]

    def get_active_task_count(self) -> int:
        """Number of generation jobs still queued or running anywhere (backend-shutdown guard)."""
        return len(self.get_active_tasks_overview())

    def _purge_dispatch_queue_locked(self, task_ids: List[str]):
        """Removes not-yet-dispatched queue entries for the given task ids. Caller must hold _lock."""
        if not self._dispatch_queue or not task_ids:
            return
        doomed = set(task_ids)
        self._dispatch_queue = deque([e for e in self._dispatch_queue if e[0] not in doomed])

    def interrupt_device_tasks(
        self,
        device_id: Optional[str] = None,
        server_url: Optional[str] = None,
        module: Optional[str] = None,
    ) -> List[str]:
        """
        Interrupts queued/running tasks for the specified device (or all devices if None).
        When `module` is provided ("minimax"/"upscaler"), ONLY that module's tasks are
        interrupted — other modules' tasks keep running/queued (no cross-module friendly fire).
        Immediately notifies ComfyUI to abort the running execution and remove pending prompts.
        Returns a list of interrupted task_ids.
        """
        from comfy_client import interrupt_execution
        interrupted_ids = []
        prompts_to_cancel = []
        with self._lock:
            for t in self._tasks.values():
                if t.status in ("queued", "running"):
                    if module and t.module != module:
                        continue
                    if not device_id or _is_same_device(t.device_id, device_id):
                        t.cancel_event.set()
                        t.status = "interrupted"
                        t.stage = "interrupted"
                        t.message = "⚠️ 任務已被手動中斷"
                        interrupted_ids.append(t.task_id)
                        if t.prompt_id:
                            prompts_to_cancel.append(t.prompt_id)
            # Drop interrupted tasks that were still waiting in the WebUI dispatch queue
            self._purge_dispatch_queue_locked(interrupted_ids)
            self._dispatch_cond.notify_all()

        # Signal ComfyUI to cancel targeted jobs
        for pid in prompts_to_cancel:
            interrupt_execution(prompt_id=pid, server_url=server_url)
        if not device_id:
            interrupt_execution(server_url=server_url)

        if interrupted_ids:
            self._save_history()
            logger.info("Interrupted %d active task(s) for device '%s': %s",
                        len(interrupted_ids), device_id or "all", interrupted_ids)
        return interrupted_ids

    def interrupt_task(self, task_id: str, server_url: Optional[str] = None) -> bool:
        """Interrupts a specific task by task_id."""
        from comfy_client import interrupt_execution
        prompt_id = None
        with self._lock:
            t = self._tasks.get(task_id)
            if not t or t.status not in ("queued", "running"):
                return False
            t.cancel_event.set()
            t.status = "interrupted"
            t.stage = "interrupted"
            t.message = "⚠️ 任務已被中斷"
            prompt_id = t.prompt_id
            # Remove from the WebUI dispatch queue if it never got dispatched yet
            self._purge_dispatch_queue_locked([task_id])
            self._dispatch_cond.notify_all()

        # Only cancel THIS task's job. Never fire a general /interrupt: under the serial
        # dispatcher the one running ComfyUI job is this task itself, and the targeted
        # cancel below handles it; a general interrupt would kill unrelated work.
        if prompt_id:
            interrupt_execution(prompt_id=prompt_id, server_url=server_url)
        self._save_history()
        logger.info("Task %s explicitly interrupted.", task_id)
        return True

    def delete_task(self, task_id: Optional[str], device_id: Optional[str] = None, is_admin: bool = False) -> bool:
        """
        Deletes a task from history, memory, and removes its output video from disk.
        Strictly verifies device ownership unless is_admin is True or device_id is omitted.
        Returns True if task was found and deleted, False otherwise.
        """
        if not task_id:
            return False

        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if not is_admin and device_id and not _is_same_device(task.device_id, device_id):
                logger.warning("[TaskManager] Unauthorized delete attempt for task %s (task device: %s, caller device: %s)",
                               task_id, task.device_id, device_id)
                return False

            # If task is currently running/queued, cancel it and drop it from
            # the WebUI dispatch queue so the dispatcher never picks it up.
            if task.status in ("queued", "running"):
                task.cancel_event.set()
                task.status = "interrupted"
                self._purge_dispatch_queue_locked([task_id])
                self._dispatch_cond.notify_all()

            # Remove video file from disk if present
            if task.video_path and os.path.exists(task.video_path):
                try:
                    os.remove(task.video_path)
                    logger.info("[TaskManager] Deleted video file: %s", task.video_path)
                except Exception as e:
                    logger.warning("[TaskManager] Failed to delete video file %s: %s", task.video_path, e)

            # Remove task from in-memory tracking
            del self._tasks[task_id]

        # Atomically persist updated task history
        self._save_history()
        logger.info("[TaskManager] Task '%s' successfully deleted (device: %s, is_admin: %s)", task_id, device_id, is_admin)
        return True

    def get_all_tasks(
        self,
        device_id_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[Task]:
        """
        Returns all tasks across all devices, sorted newest first.
        Supports optional filtering by device_id and status.
        """
        with self._lock:
            tasks = list(self._tasks.values())

        if device_id_filter and device_id_filter != "全部裝置":
            tasks = [t for t in tasks if t.device_id == device_id_filter]

        if status_filter and status_filter != "全部狀態":
            if status_filter == "已完成":
                tasks = [t for t in tasks if t.status == "completed"]
            elif status_filter == "生成中/排隊中":
                tasks = [t for t in tasks if t.status in ("running", "queued")]
            elif status_filter == "失敗/中斷":
                tasks = [t for t in tasks if t.status in ("failed", "interrupted")]

        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    def delete_failed_and_interrupted_tasks(self) -> int:
        """Deletes all tasks with failed or interrupted status across all devices."""
        with self._lock:
            target_ids = [tid for tid, t in self._tasks.items() if t.status in ("failed", "interrupted")]
        count = 0
        for tid in target_ids:
            if self.delete_task(tid, is_admin=True):
                count += 1
        return count

    def get_connected_devices_summary(self) -> List[Dict[str, Any]]:
        """Returns aggregated summary of all known devices from task history."""
        device_map: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            for t in self._tasks.values():
                d = t.device_id or "default"
                if d not in device_map:
                    device_map[d] = {
                        "device_id": d,
                        "short_id": d.split("_")[-1][:6] if "_" in d else d[:6],
                        "task_count": 0,
                        "completed_count": 0,
                        "last_active": t.created_at,
                    }
                device_map[d]["task_count"] += 1
                if t.status == "completed":
                    device_map[d]["completed_count"] += 1
                if t.created_at > device_map[d]["last_active"]:
                    device_map[d]["last_active"] = t.created_at

        summary_list = list(device_map.values())
        summary_list.sort(key=lambda x: x["last_active"], reverse=True)
        return summary_list


    def start_background_task(self, task: Task, prompt_graph: Dict[str, Any], server_url: Optional[str] = None):
        """
        Enqueues the task into the global FIFO dispatch queue (does NOT submit immediately).
        A single dispatcher thread submits workflows to ComfyUI strictly one-at-a-time,
        so tasks from different modules queue politely instead of preempting each other.
        """
        server_url = server_url or COMFY_SERVER_URL
        with self._dispatch_cond:
            if task.cancel_event.is_set() or task.status == "interrupted":
                logger.info("[Task %s] Interrupted before enqueueing; skipped.", task.task_id)
                return
            ahead = len(self._dispatch_queue) + (1 if self._executing_task_id else 0)
            task.status = "queued"
            task.stage = "pending"
            if ahead > 0:
                task.message = f"⏳ 排隊中...（前面還有 {ahead} 個工作）"
            else:
                task.message = "⏳ 排隊中...（即將提交）"
            self._dispatch_queue.append((task.task_id, prompt_graph, server_url))
            self._ensure_dispatcher_locked()
            self._dispatch_cond.notify_all()
        self._save_history()
        logger.info("[Task %s] Enqueued for serial dispatch (queue position: %d).", task.task_id, ahead + 1)

    def _ensure_dispatcher_locked(self):
        """Lazily starts the resident dispatcher thread. Caller must hold _lock/_dispatch_cond."""
        if self._dispatcher_started:
            return
        self._dispatcher_started = True
        threading.Thread(target=self._dispatcher_loop, daemon=True, name="TaskDispatcher").start()
        logger.info("Serial task dispatcher thread started.")

    def _dispatcher_loop(self):
        """Resident worker: pops the next non-cancelled task FIFO and runs its monitor worker serially."""
        while True:
            with self._dispatch_cond:
                entry = None
                while entry is None:
                    while not self._dispatch_queue:
                        self._dispatch_cond.wait()
                    candidate = self._dispatch_queue.popleft()
                    cand_task = self._tasks.get(candidate[0])
                    if cand_task and not cand_task.cancel_event.is_set() and cand_task.status in ("queued", "running"):
                        entry = candidate
                task = self._tasks[entry[0]]
                prompt_graph, server_url = entry[1], entry[2]
                self._executing_task_id = task.task_id
            logger.info("[Task %s] Dispatcher handing task to worker (serial slot acquired).", task.task_id)
            try:
                self._monitor_worker(task, prompt_graph, server_url)
            except Exception as e:
                logger.error("[Task %s] Dispatcher worker crashed: %s", task.task_id, e)
                task.status = "failed"
                task.stage = "failed"
                task.message = f"❌ 任務執行異常: {str(e)}"
                self._save_history()
            finally:
                with self._dispatch_cond:
                    self._executing_task_id = None
                    self._dispatch_cond.notify_all()

    def _ws_listener(self, ws_url: str, client_id: str, prompt_id: str, task: Task, prompt_graph: Optional[Dict[str, Any]], stop_event: threading.Event):
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
                                p_id = data.get("prompt_id")
                                if p_id and p_id != prompt_id:
                                    continue
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
                                        node_key = str(node)
                                        node_info = prompt_graph.get(node_key, {}) if prompt_graph else {}
                                        class_type = str(node_info.get("class_type", "")).lower()
                                        node_str = f"{node_key} {class_type}".lower()
                                        if any(k in node_str for k in ["vae_decode", "vaedecode", "create_video", "createvideo", "save_video", "savevideo"]):
                                            task.stage = "postprocessing"
                                        elif any(k in node_str for k in ["sampler", "sampling", "ksampler"]):
                                            task.stage = "sampling"
                                            if task.total_steps > 0:
                                                task.message = f"⚡ 影片生成中: {task.step}/{task.total_steps} 步"
                                            else:
                                                task.message = "⚡ 影片生成中..."
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
        if task.cancel_event.is_set() or task.status == "interrupted":
            logger.info("[Task %s] Interrupted before starting worker.", task.task_id)
            return

        task.status = "running"
        task.stage = "preprocessing"
        task.message = "⚡ 前處理中：正在提交任務至後端..."
        task.progress = 0.08
        logger.info("[Task %s] Submitting workflow graph to ComfyUI (%s)...", task.task_id, server_url)

        client_id = str(uuid.uuid4())
        try:
            if task.cancel_event.is_set() or task.status == "interrupted":
                logger.info("[Task %s] Interrupted before queueing prompt.", task.task_id)
                return
            prompt_id = queue_prompt(prompt_graph, client_id, server_url)
            task.prompt_id = prompt_id
            task.status = "queued"
            task.stage = "pending"
            task.message = "⏳ 排隊中..."
            task.progress = 0.15
            logger.info("[Task %s] Prompt queued successfully! Assigned ComfyUI prompt_id: %s", task.task_id, prompt_id)
        except Exception as e:
            if task.cancel_event.is_set() or task.status == "interrupted":
                logger.info("[Task %s] Interrupted during prompt submission: %s", task.task_id, e)
                return
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
            args=(ws_url, client_id, task.prompt_id, task, prompt_graph, stop_ws),
            daemon=True,
        )
        ws_thread.start()

        start_time = time.time()
        last_logged_step = -1
        last_logged_stage = task.stage

        while True:
            if task.cancel_event.is_set() or task.status == "interrupted":
                task.status = "interrupted"
                task.stage = "interrupted"
                task.message = "⚠️ 任務已中斷"
                stop_ws.set()
                self._save_history()
                logger.info("[Task %s] Interrupted.", task.task_id)
                return

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
                                    task.message = f"⚡ 後處理中：正在儲存影片... (耗時 {time_str})"
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
                        task.status = "running"
                        task.stage = "postprocessing"
                        task.message = f"⚡ 後處理中：正在合成影片... (耗時 {time_str})"
                    elif task.stage == "postprocessing":
                        task.status = "running"
                        task.message = f"⚡ 後處理中：正在合成影片... (耗時 {time_str})"
                    elif task.stage == "sampling" or (task.total_steps > 0 and task.step > 0):
                        task.status = "running"
                        task.stage = "sampling"
                        if task.total_steps > 0:
                            task.message = f"⚡ 影片生成中: {task.step}/{task.total_steps} 步 (耗時 {time_str})"
                        else:
                            task.message = f"⚡ 影片生成中... (耗時 {time_str})"
                    elif task.prompt_id in running:
                        task.status = "running"
                        task.stage = "preprocessing"
                        task.progress = min(0.95, 0.25 + (elapsed / 1800.0) * 0.70)
                        task.message = f"⚡ 前處理中：正在載入模型... (耗時 {time_str})"
                    elif task.prompt_id in pending:
                        task.status = "queued"
                        task.stage = "pending"
                        task.progress = 0.18
                        task.message = f"⏳ 排隊中... (已等待 {time_str})"
            except Exception as e:
                logger.debug("[Task %s] Queue poll exception: %s", task.task_id, e)

            time.sleep(0.5)


# Global singleton instance
task_manager = TaskManager()

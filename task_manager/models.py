"""
Task data model for the WebUI task system (Spec 2026-10-31 task-manager modularization).

Pure data + device-matching helper only: no I/O, no ComfyUI calls. Kept import-light
so every other submodule (and the tests) can depend on it without cycles.
"""
import threading
import time
from typing import Any, Dict, Optional


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

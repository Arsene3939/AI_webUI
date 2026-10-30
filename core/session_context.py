"""
Session and device context management for strict per-device isolation.
"""
import uuid
from typing import Optional, Dict, Any, List
import gradio as gr
from utils.logger import get_logger

logger = get_logger("SessionContext")

DEVICE_STORAGE_SECRET = "minimax_h3_device_secret_2026"


class SessionContext:
    """Encapsulates persistent browser-stored device ID and active task ID."""

    def __init__(self):
        self.device_id_state: Optional[gr.BrowserState] = None
        self.session_task_state: Optional[gr.BrowserState] = None

    def render(self) -> "SessionContext":
        self.device_id_state = gr.BrowserState(
            default_value="",
            storage_key="minimax_device_id",
            secret=DEVICE_STORAGE_SECRET,
        )
        self.session_task_state = gr.BrowserState(
            default_value="",
            storage_key="minimax_active_task_id",
            secret=DEVICE_STORAGE_SECRET,
        )
        return self

    @staticmethod
    def ensure_device_id(device_id: Optional[str]) -> str:
        """Guarantees a non-empty device ID string with dev_ prefix."""
        if not device_id or not str(device_id).strip():
            return f"dev_{uuid.uuid4().hex[:6]}"
        val = str(device_id).strip()
        if not val.startswith("dev_"):
            return f"dev_{val}"
        return val

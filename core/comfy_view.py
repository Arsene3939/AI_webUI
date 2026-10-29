"""
ComfyUI-based view abstract class providing shared ComfyUI workflow helpers and safeguards.
"""
from typing import Optional, Any
from core.base_view import BaseView
from config import SERVER_STATUS_UPDATING, get_server_status
from components.media_player import build_progress_html


class ComfyUIBaseView(BaseView):
    """
    Base view specialized for modules utilizing ComfyUI as the execution backend.
    Enforces server maintenance check and shared execution lifecycle.
    """

    def is_maintenance_mode(self) -> bool:
        """Checks if server is currently in updating/maintenance state."""
        return get_server_status() == SERVER_STATUS_UPDATING

    def get_maintenance_error_update(self, current_session_task: Any, device_id: str):
        """Standard generator yield tuple when server is in maintenance mode."""
        return (
            build_progress_html("⚠️ 伺服器維護/更新中，暫停提交生成任務"),
            None,
            current_session_task,
            device_id,
        )

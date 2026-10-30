"""
ComfyUI backend control toolbar component for starting, stopping, and polling backend status.
"""
from typing import Optional, Tuple
import gradio as gr
from config import (
    COMFY_SERVER_URL,
    SERVER_STATUS_UPDATING,
    get_server_status,
)
from core.comfy_client import (
    check_server,
    check_system_resources,
    start_comfyui_backend,
    stop_comfyui_backend,
)
from core.admin_manager import AdminManager
from task_manager import task_manager
from utils.logger import get_logger

logger = get_logger("ComfyToolbar")


class ComfyToolbarComponent:
    """Encapsulates backend status indicator and start/stop controls."""

    def __init__(self):
        self.start_btn: Optional[gr.Button] = None
        self.stop_btn: Optional[gr.Button] = None
        self.status_msg: Optional[gr.Markdown] = None
        self._is_backend_starting: bool = False

    def render(self) -> "ComfyToolbarComponent":
        with gr.Row():
            self.start_btn = gr.Button("⚡ 檢查後端模型狀態...", variant="secondary", scale=9)
            self.stop_btn = gr.Button("🛑", variant="stop", scale=1, min_width=50)

        self.status_msg = gr.Markdown("", elem_classes=["backend-status-box"])
        return self

    def poll_backend_status(self) -> dict:
        """Polls backend status dynamically to set button label and color."""
        if get_server_status() == SERVER_STATUS_UPDATING:
            return gr.update(value="🔧 伺服器維護/更新中", variant="stop")
        if self._is_backend_starting:
            return gr.update(value="🟡 正在啟動後端模型...", variant="secondary")
        ok, _ = check_server(COMFY_SERVER_URL)
        if ok:
            return gr.update(value="🟢 後端模型運作中", variant="primary")
        else:
            return gr.update(value="⚡ 啟動後端模型", variant="secondary")

    def on_start_backend(self):
        """Handler for clicking start backend button with system resource pre-check."""
        if get_server_status() == SERVER_STATUS_UPDATING:
            yield gr.update(value="🔧 伺服器維護/更新中", variant="stop"), "⚠️ 伺服器維護/更新中，暫停啟動後端"
            return

        ok, _ = check_server(COMFY_SERVER_URL)
        if ok:
            yield gr.update(value="🟢 後端模型運作中", variant="primary"), "🟢 後端模型已經在運作中，無須重複啟動"
            return

        res_ok, warning_msg, _ = check_system_resources()
        if not res_ok:
            yield gr.update(value="⚡ 啟動後端模型", variant="secondary"), warning_msg
            return

        self._is_backend_starting = True
        yield gr.update(value="🟡 正在啟動後端模型...", variant="secondary"), "🟡 正在啟動後端模型，請稍候..."

        try:
            ok, msg = start_comfyui_backend(COMFY_SERVER_URL, skip_resource_check=True)
        finally:
            self._is_backend_starting = False

        btn_update = self.poll_backend_status()
        yield btn_update, f"{msg}"

    def on_stop_backend(self, request: Optional[gr.Request] = None) -> Tuple[dict, str]:
        """Handler for stopping ComfyUI backend process.

        SAFEGUARD (regular users): while any generation job is still queued/running
        (any device, any module), the shutdown is refused — killing the backend mid-job
        would orphan the worker and lose that user's output.

        FORCE PATH (super user / admin, Spec 2026-10-31 task 1): the admin's stop button
        shuts the backend down unconditionally — every queued/running task is marked
        interrupted first (so history stays honest and device UIs free up), then the
        backend process is killed.
        """
        if AdminManager.is_super_user(request):
            active = task_manager.get_active_tasks_overview()
            if active:
                interrupted = task_manager.interrupt_device_tasks(device_id=None, module=None)
                logger.warning(
                    "[ComfyToolbar] Admin FORCE-stopped backend with %d active task(s): %s",
                    len(active), interrupted,
                )
            ok, msg = stop_comfyui_backend(COMFY_SERVER_URL)
            btn_update = self.poll_backend_status()
            if active:
                return btn_update, f"🛑 後端模型已強制關閉（已中斷 {len(active)} 個進行中的工作）"
            return btn_update, f"{msg}"

        active = task_manager.get_active_tasks_overview()
        if active:
            btn_update = self.poll_backend_status()
            return btn_update, (
                f"⚠️ 無法關閉後端模型：目前仍有 {len(active)} 個工作正在排队或生成中，"
                "請等待完成，或先到對應頁面按下停止按鈕"
            )

        ok, msg = stop_comfyui_backend(COMFY_SERVER_URL)
        btn_update = self.poll_backend_status()
        return btn_update, f"{msg}"

    def register_events(self, timer: Optional[gr.Timer] = None):
        """Binds click and timer tick listeners."""
        if self.start_btn and self.status_msg:
            self.start_btn.click(self.on_start_backend, outputs=[self.start_btn, self.status_msg])
        if self.stop_btn and self.status_msg:
            self.stop_btn.click(self.on_stop_backend, outputs=[self.start_btn, self.status_msg])
        if timer and self.start_btn:
            timer.tick(self.poll_backend_status, outputs=[self.start_btn])

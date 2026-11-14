"""
ComfyUI-specialized administrator tab providing backend management, VRAM purging, and execution queue control.
Inherits BaseAdminTab.
"""
from typing import Optional, Any
import gradio as gr
from core.base_admin_tab import BaseAdminTab
from core.admin_manager import AdminManager
from ui_text import (
    ADMIN_CLEAR_QUEUE_BTN,
    ADMIN_COMFY_BACKEND_SECTION_MD,
    ADMIN_COMFY_QUEUE_SECTION_MD,
    ADMIN_COMFY_TAB_TITLE,
    ADMIN_INTERRUPT_TASK_BTN,
    ADMIN_PURGE_VRAM_BTN,
    ADMIN_REFRESH_QUEUE_BTN,
    ADMIN_RESTART_BACKEND_BTN,
)


class ComfyUIAdminTab(BaseAdminTab):
    """
    Administrator tab for views backed by ComfyUI (MiniMax, Upscaler).
    Inherits BaseAdminTab and adds:
    - VRAM Purge & ComfyUI Process Restart controls
    - Real-time ComfyUI Queue monitor with Interrupt and Clear queue buttons
    """

    def __init__(self, tab_title: str = ADMIN_COMFY_TAB_TITLE):
        super().__init__(tab_title=tab_title)
        self.free_vram_btn: Optional[gr.Button] = None
        self.restart_backend_btn: Optional[gr.Button] = None
        self.queue_html: Optional[gr.HTML] = None
        self.cancel_current_btn: Optional[gr.Button] = None
        self.clear_queue_btn: Optional[gr.Button] = None
        self.refresh_queue_btn: Optional[gr.Button] = None

    def render_custom_content(self, session_ctx: Any) -> None:
        """Injects ComfyUI process & queue controls, then calls render_comfy_content hook."""
        gr.Markdown(ADMIN_COMFY_BACKEND_SECTION_MD)
        with gr.Row():
            self.free_vram_btn = gr.Button(ADMIN_PURGE_VRAM_BTN, variant="secondary", scale=1)
            self.restart_backend_btn = gr.Button(ADMIN_RESTART_BACKEND_BTN, variant="secondary", scale=1)

        gr.Markdown(ADMIN_COMFY_QUEUE_SECTION_MD)
        self.queue_html = gr.HTML(AdminManager.build_admin_queue_html())
        with gr.Row():
            self.cancel_current_btn = gr.Button(ADMIN_INTERRUPT_TASK_BTN, variant="stop", scale=2)
            self.clear_queue_btn = gr.Button(ADMIN_CLEAR_QUEUE_BTN, variant="secondary", scale=2)
            self.refresh_queue_btn = gr.Button(ADMIN_REFRESH_QUEUE_BTN, variant="secondary", scale=1)

        # Hook for further child customization (e.g. MiniMax task history, Upscaler cache)
        self.render_comfy_content(session_ctx)

    def render_comfy_content(self, session_ctx: Any) -> None:
        """Hook for child classes of ComfyUIAdminTab."""
        pass

    def register_custom_events(self, session_ctx: Any) -> None:
        """Registers ComfyUI controls events and invokes register_comfy_events hook."""
        self.free_vram_btn.click(
            AdminManager.on_free_vram,
            outputs=[self.op_msg],
        )
        self.restart_backend_btn.click(
            AdminManager.on_restart_backend,
            outputs=[self.op_msg],
        )
        self.cancel_current_btn.click(
            AdminManager.on_cancel_current_task,
            outputs=[self.queue_html, self.op_msg],
        )
        self.clear_queue_btn.click(
            AdminManager.on_clear_queue,
            outputs=[self.queue_html, self.op_msg],
        )
        self.refresh_queue_btn.click(
            AdminManager.build_admin_queue_html,
            outputs=[self.queue_html],
        )

        # Auto-refresh the ComfyUI queue panel on the shared 5s admin heartbeat
        # (one localhost /queue GET per tick: negligible next to the existing 0.5s probe).
        if getattr(self, "auto_refresh_timer", None) is not None:
            def auto_queue_refresh(req: gr.Request = None):
                if not AdminManager.is_super_user(req):
                    return gr.update()
                return AdminManager.build_admin_queue_html()

            self.auto_refresh_timer.tick(
                auto_queue_refresh,
                outputs=[self.queue_html],
            )

        self.register_comfy_events(session_ctx)

    def register_comfy_events(self, session_ctx: Any) -> None:
        """Hook for child classes of ComfyUIAdminTab."""
        pass

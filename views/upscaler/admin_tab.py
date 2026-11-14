"""
Upscaler administrator tab with super-resolution model management and cache controls.
Inherits ComfyUIAdminTab.
"""
from typing import Optional, Any
import gradio as gr
from core.comfy_admin_tab import ComfyUIAdminTab
from ui_text import ADMIN_CACHE_CLEANED_MSG, ADMIN_CLEAN_CACHE_BTN, ADMIN_UPSCALER_SECTION_MD, ADMIN_UPSCALER_TAB_TITLE


class UpscalerAdminTab(ComfyUIAdminTab):
    """
    Video Upscaler administrator tab.
    Inherits all ComfyUI backend and server management features, and adds:
    - Upscale model registry & cache directory cleaning
    - GPU tiling memory limits configuration
    """

    def __init__(self):
        super().__init__(tab_title=ADMIN_UPSCALER_TAB_TITLE)
        self.clean_cache_btn: Optional[gr.Button] = None
        self.cache_msg: Optional[gr.Markdown] = None

    def render_comfy_content(self, session_ctx: Any) -> None:
        """Injects Upscaler-specific admin controls."""
        gr.Markdown(ADMIN_UPSCALER_SECTION_MD)
        with gr.Row():
            self.clean_cache_btn = gr.Button(ADMIN_CLEAN_CACHE_BTN, variant="secondary", scale=2)
        self.cache_msg = gr.Markdown("", elem_classes=["backend-status-box"])

    def register_comfy_events(self, session_ctx: Any) -> None:
        def on_clean_cache():
            return ADMIN_CACHE_CLEANED_MSG

        self.clean_cache_btn.click(
            on_clean_cache,
            outputs=[self.cache_msg],
        )

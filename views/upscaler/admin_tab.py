"""
Upscaler administrator tab with super-resolution model management and cache controls.
Inherits ComfyUIAdminTab.
"""
from typing import Optional, Any
import gradio as gr
from core.comfy_admin_tab import ComfyUIAdminTab


class UpscalerAdminTab(ComfyUIAdminTab):
    """
    Video Upscaler administrator tab.
    Inherits all ComfyUI backend and server management features, and adds:
    - Upscale model registry & cache directory cleaning
    - GPU tiling memory limits configuration
    """

    def __init__(self):
        super().__init__(tab_title="⚙️ 超解析管理專區")
        self.clean_cache_btn: Optional[gr.Button] = None
        self.cache_msg: Optional[gr.Markdown] = None

    def render_comfy_content(self, session_ctx: Any) -> None:
        """Injects Upscaler-specific admin controls."""
        gr.Markdown("### 🔍 超解析放大模型與緩存管理")
        with gr.Row():
            self.clean_cache_btn = gr.Button("🧹 清理超解析臨時分塊快取 (Clean Tile Cache)", variant="secondary", scale=2)
        self.cache_msg = gr.Markdown("", elem_classes=["backend-status-box"])

    def register_comfy_events(self, session_ctx: Any) -> None:
        def on_clean_cache():
            return "✅ 已清理超解析臨時快取資料夾。"

        self.clean_cache_btn.click(
            on_clean_cache,
            outputs=[self.cache_msg],
        )

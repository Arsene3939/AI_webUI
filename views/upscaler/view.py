"""
Video Resolution Upscaler view (ComfyUI backend).
Provides video super-resolution upscaling, model selection, preview, and dedicated admin tab.
"""
from typing import Optional, Any, List
import gradio as gr
from core.comfy_view import ComfyUIBaseView
from components.media_player import VideoPlayerCardComponent, ActionButtonsComponent, build_progress_html
from views.upscaler.admin_tab import UpscalerAdminTab
from logger import get_logger

logger = get_logger("UpscalerView")


class UpscalerView(ComfyUIBaseView):
    """
    Video resolution upscaler module inheriting ComfyUIBaseView.
    Allows users to upload existing video and upscale resolution (2x, 4x) via ComfyUI.
    Includes dedicated UpscalerAdminTab.
    """

    def __init__(self):
        super().__init__(name="upscaler", icon="🔍", title="comfyUI: video resolution upscaler")
        self.tabs: Optional[gr.Tabs] = None
        self.input_video: Optional[gr.Video] = None
        self.scale_factor: Optional[gr.Radio] = None
        self.upscale_model: Optional[gr.Dropdown] = None
        self.action_btns = ActionButtonsComponent(generate_label="🚀 開始影片超解析放大")
        self.player_card = VideoPlayerCardComponent(label="放大成果影片")
        self.admin_tab = UpscalerAdminTab()

    def render(self, session_ctx: Any) -> gr.Column:
        with gr.Column(visible=False) as self.container:
            with gr.Tabs() as self.tabs:
                with gr.Tab("🔍 影片超解析放大"):
                    gr.Markdown("### 🔍 影片超解析放大 (Video Resolution Upscaler)")
                    gr.Markdown("上傳已生成的影片，透過 ComfyUI 神經網路模型進行 2x/4x 畫質修復與高解析度放大。")

                    with gr.Row():
                        with gr.Column(scale=1):
                            self.input_video = gr.Video(label="上傳來源影片", height=280)
                            with gr.Row():
                                self.scale_factor = gr.Radio(
                                    choices=["2x (清晰提升)", "4x (高解析放大)"],
                                    value="2x (清晰提升)",
                                    label="放大倍率",
                                )
                                self.upscale_model = gr.Dropdown(
                                    choices=["RealESRGAN_x4plus", "Compact_2x", "AnimeJaNai_HD"],
                                    value="RealESRGAN_x4plus",
                                    label="超解析模型",
                                    filterable=False,
                                )
                            self.action_btns.render()

                        self.player_card.render()

                with gr.Tab("📜 放大紀錄"):
                    gr.Markdown("### 📜 超解析歷史生成紀錄")
                    gr.Markdown("此裝置目前尚無超解析放大任務紀錄。")

                self.admin_tab.render(session_ctx)
        return self.container

    def register_events(self, session_ctx: Any) -> None:
        def handle_upscale(video_file, scale, model, device_id):
            if self.is_maintenance_mode():
                yield build_progress_html("⚠️ 伺服器維護/更新中，暫停提交放大任務"), None
                return
            if not video_file:
                yield build_progress_html("❌ 請先上傳欲放大的來源影片"), None
                return
            yield build_progress_html("⚡ 準備提交 ComfyUI 影片超解析任務..."), None

        if self.action_btns.generate_btn:
            self.action_btns.generate_btn.click(
                handle_upscale,
                inputs=[self.input_video, self.scale_factor, self.upscale_model, session_ctx.device_id_state],
                outputs=[self.player_card.status, self.player_card.output_video],
            )

        self.admin_tab.register_events(session_ctx)

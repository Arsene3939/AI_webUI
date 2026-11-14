"""
Video Resolution Upscaler view (ComfyUI backend).
Directly models: utility-gan_upscaler.json
Reads models dynamically from F:\\Comfy_models\\upscale_models.
"""
import os
import time
import uuid
from typing import Optional, Any, List
import gradio as gr
from core.comfy_view import ComfyUIBaseView
from components.media_player import build_progress_html
from components.history_gallery import HistoryGalleryComponent, get_history_dropdown_choices
from views.upscaler.admin_tab import UpscalerAdminTab
from views.upscaler.workflow_builder import build_upscale_workflow
from config import get_upscale_models, get_server_status, SERVER_STATUS_UPDATING
from core.comfy_client import upload_media_file, check_server
from task_manager import task_manager, Task
from utils.logger import get_logger
from ui_text import (
    UPSCALER_ADVANCED_ACCORDION,
    UPSCALER_BITDEPTH_10_LABEL,
    UPSCALER_BITDEPTH_8_LABEL,
    UPSCALER_BITDEPTH_INFO,
    UPSCALER_BITDEPTH_LABEL,
    UPSCALER_FORMAT_AUTO,
    UPSCALER_FORMAT_LABEL,
    UPSCALER_GENERATE_BTN,
    UPSCALER_HEADING,
    UPSCALER_INPUT_VIDEO_LABEL,
    UPSCALER_INTRO,
    UPSCALER_MODEL_LABEL,
    UPSCALER_MSG_NO_MODEL,
    UPSCALER_MSG_NO_VIDEO,
    UPSCALER_MSG_SERVER_OFFLINE,
    UPSCALER_MSG_SERVER_UPDATING,
    UPSCALER_MSG_STOPPED,
    UPSCALER_MSG_UPLOADING,
    UPSCALER_MSG_UPLOAD_FAILED,
    UPSCALER_OUTPUT_VIDEO_LABEL,
    UPSCALER_REFRESH_BTN,
    UPSCALER_SCALE_HALF,
    UPSCALER_SCALE_INFO,
    UPSCALER_SCALE_LABEL,
    UPSCALER_SCALE_ORIGINAL,
    UPSCALER_SCALE_QUARTER,
    UPSCALER_STOP_BTN,
    UPSCALER_TAB_HISTORY,
    UPSCALER_TAB_UPSCALE,
)

logger = get_logger("UpscalerView")


def handle_upscale_generate(
    video_file: Optional[str],
    model: str,
    output_format: str = "auto",
    post_scale: float = 0,
    bit_depth: int = 8,
    device_id: Optional[str] = None,
    current_session_task: Optional[str] = None,
):
    """
    Generator function that uploads input video, submits upscale workflow to ComfyUI,
    and streams progress HTML and output video until completion.
    """
    if not device_id:
        device_id = f"dev_{uuid.uuid4().hex[:6]}"

    if get_server_status() == SERVER_STATUS_UPDATING:
        yield build_progress_html(UPSCALER_MSG_SERVER_UPDATING), None, current_session_task, device_id
        return

    if not video_file:
        yield build_progress_html(UPSCALER_MSG_NO_VIDEO), None, current_session_task, device_id
        return

    if not model:
        yield build_progress_html(UPSCALER_MSG_NO_MODEL), None, current_session_task, device_id
        return

    # Check ComfyUI server online
    server_ok, msg = check_server()
    if not server_ok:
        yield build_progress_html(UPSCALER_MSG_SERVER_OFFLINE.format(msg)), None, current_session_task, device_id
        return

    # No preemption: tasks now queue politely through the serial dispatcher,
    # so submitting an upscale job no longer kills other devices' or modules' work.

    yield build_progress_html(UPSCALER_MSG_UPLOADING), None, current_session_task, device_id

    try:
        uploaded_fn = upload_media_file(video_file)
    except Exception as e:
        logger.error("Failed to upload video to ComfyUI: %s", e)
        yield build_progress_html(UPSCALER_MSG_UPLOAD_FAILED.format(str(e))), None, current_session_task, device_id
        return

    # 進階輸出參數（Spec 任務 6）：0/None 都代表不額外縮放
    prompt_graph = build_upscale_workflow(
        video_filename=uploaded_fn,
        model_name=model,
        output_format=output_format or "auto",
        bit_depth=int(bit_depth or 8),
        post_scale=float(post_scale) if post_scale else None,
    )

    task = task_manager.create_task(
        task_type="UPSCALER",
        prompt=f"Upscale video with {model}",
        params={
            "video": video_file,
            "model": model,
            "output_format": output_format or "auto",
            "bit_depth": int(bit_depth or 8),
            "post_scale": float(post_scale) if post_scale else 0,
        },
        device_id=device_id,
    )

    task_manager.start_background_task(task, prompt_graph)

    while True:
        t = task_manager.get_task(task.task_id, device_id=device_id)
        if not t:
            break
        yield build_progress_html(t), t.video_path, t.task_id, device_id
        if t.status in ["completed", "failed", "interrupted"]:
            break
        time.sleep(0.5)


class UpscalerView(ComfyUIBaseView):
    """
    Video resolution upscaler module inheriting ComfyUIBaseView.
    Allows users to upload video and upscale resolution via GAN models.
    Preserves original video FPS and audio tracks.
    """

    def __init__(self):
        super().__init__(name="upscaler", icon="🔍", title="comfyUI: video resolution upscaler")
        self.tabs: Optional[gr.Tabs] = None
        self.input_video: Optional[gr.Video] = None
        self.upscale_model: Optional[gr.Dropdown] = None
        self.output_format: Optional[gr.Radio] = None
        self.output_scale: Optional[gr.Dropdown] = None
        self.bit_depth: Optional[gr.Radio] = None
        self.refresh_model_btn: Optional[gr.Button] = None
        self.generate_btn: Optional[gr.Button] = None
        self.stop_btn: Optional[gr.Button] = None
        self.status: Optional[gr.HTML] = None
        self.output_video: Optional[gr.Video] = None
        self.history_gallery = HistoryGalleryComponent(module="upscaler")
        self.admin_tab = UpscalerAdminTab()

    def render(self, session_ctx: Any) -> gr.Column:
        model_choices = get_upscale_models()
        default_model = model_choices[0] if model_choices else "RealESRGAN_x4plus.safetensors"

        # Routing refactor: this view is the whole content of the /upscaler page,
        # so the container must be visible (the old single-page app hid it behind
        # the radio-switched minimax view).
        with gr.Column() as self.container:
            with gr.Tabs() as self.tabs:
                with gr.Tab(UPSCALER_TAB_UPSCALE):
                    gr.Markdown(UPSCALER_HEADING)
                    gr.Markdown(UPSCALER_INTRO)

                    with gr.Row():
                        with gr.Column(scale=1):
                            self.input_video = gr.Video(label=UPSCALER_INPUT_VIDEO_LABEL, height=280)

                            with gr.Row():
                                self.upscale_model = gr.Dropdown(
                                    choices=model_choices,
                                    value=default_model,
                                    label=UPSCALER_MODEL_LABEL,
                                    scale=4,
                                    filterable=False,
                                    allow_custom_value=False,
                                )
                                self.refresh_model_btn = gr.Button(
                                    UPSCALER_REFRESH_BTN,
                                    size="sm",
                                    scale=1,
                                    variant="secondary",
                                )

                            # 進階輸出設定（Spec 2026-10-31 任務 6；預設值＝舊版行為）
                            with gr.Accordion(UPSCALER_ADVANCED_ACCORDION, open=False):
                                with gr.Row():
                                    self.output_scale = gr.Dropdown(
                                        choices=[
                                            (UPSCALER_SCALE_ORIGINAL, 0),
                                            (UPSCALER_SCALE_HALF, 0.5),
                                            (UPSCALER_SCALE_QUARTER, 0.25),
                                        ],
                                        value=0,
                                        label=UPSCALER_SCALE_LABEL,
                                        info=UPSCALER_SCALE_INFO,
                                        filterable=False,
                                    )
                                with gr.Row():
                                    self.output_format = gr.Radio(
                                        choices=[(UPSCALER_FORMAT_AUTO, "auto"), ("MP4", "mp4")],
                                        value="auto",
                                        label=UPSCALER_FORMAT_LABEL,
                                    )
                                    self.bit_depth = gr.Radio(
                                        choices=[(UPSCALER_BITDEPTH_8_LABEL, 8), (UPSCALER_BITDEPTH_10_LABEL, 10)],
                                        value=8,
                                        label=UPSCALER_BITDEPTH_LABEL,
                                        info=UPSCALER_BITDEPTH_INFO,
                                    )

                            self.generate_btn = gr.Button(
                                UPSCALER_GENERATE_BTN,
                                variant="primary",
                                elem_classes=["primary-btn"],
                            )
                            self.stop_btn = gr.Button(
                                UPSCALER_STOP_BTN,
                                variant="stop",
                                visible=False,
                                elem_classes=["primary-btn"],
                            )

                        with gr.Column(scale=1):
                            self.status = gr.HTML(value=build_progress_html(None))
                            self.output_video = gr.Video(label=UPSCALER_OUTPUT_VIDEO_LABEL, height=340)

                with gr.Tab(UPSCALER_TAB_HISTORY):
                    self.history_gallery.render()

                self.admin_tab.render(session_ctx)
        return self.container

    def register_events(self, session_ctx: Any, poll_timer: Optional[gr.Timer] = None) -> None:
        def refresh_models():
            models = get_upscale_models()
            val = models[0] if models else ""
            return gr.update(choices=models, value=val)

        if self.refresh_model_btn and self.upscale_model:
            self.refresh_model_btn.click(
                refresh_models,
                outputs=[self.upscale_model],
            )

        def generate_wrapper(video_file, model, output_format, post_scale, bit_depth, session_task, device_id):
            for progress_html, video_out, task_id, dev_id in handle_upscale_generate(
                video_file=video_file,
                model=model,
                output_format=output_format,
                post_scale=post_scale,
                bit_depth=bit_depth,
                device_id=device_id,
                current_session_task=session_task,
            ):
                yield progress_html, video_out, task_id, dev_id

        if self.generate_btn:
            self.generate_btn.click(
                lambda: (gr.update(visible=False), gr.update(visible=True)),
                outputs=[self.generate_btn, self.stop_btn],
            ).then(
                generate_wrapper,
                inputs=[
                    self.input_video,
                    self.upscale_model,
                    self.output_format,
                    self.output_scale,
                    self.bit_depth,
                    session_ctx.session_task_state,
                    session_ctx.device_id_state,
                ],
                outputs=[
                    self.status,
                    self.output_video,
                    session_ctx.session_task_state,
                    session_ctx.device_id_state,
                ],
                api_name="handle_upscale_generate",
                concurrency_limit=None,
            ).then(
                lambda: (gr.update(visible=True), gr.update(visible=False)),
                outputs=[self.generate_btn, self.stop_btn],
            )

        def handle_stop(device_id):
            # Module-scoped: stopping an upscale job must not touch minimax tasks
            task_manager.interrupt_device_tasks(device_id, module="upscaler")
            return (
                build_progress_html(UPSCALER_MSG_STOPPED, 0.0),
                gr.update(visible=True),
                gr.update(visible=False),
            )

        if self.stop_btn:
            self.stop_btn.click(
                handle_stop,
                inputs=[session_ctx.device_id_state],
                outputs=[self.status, self.generate_btn, self.stop_btn],
                api_name="handle_stop_upscale",
            )

        # Polling progress
        def poll_progress(device_id, session_task_id):
            if not device_id:
                return gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

            # Module-scoped queries: minimax jobs never leak into the upscaler UI
            task = task_manager.get_active_task_for_device(device_id, module="upscaler")
            if not task:
                task = task_manager.get_task(session_task_id, device_id=device_id, module="upscaler")

            if not task:
                return gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

            if task.status == "completed":
                html = build_progress_html(task)
                history_choices = get_history_dropdown_choices(device_id, module="upscaler")
                return (
                    html,
                    task.video_path,
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(choices=history_choices),
                )
            elif task.status in ("running", "queued"):
                html = build_progress_html(task)
                return (
                    html,
                    gr.update(),
                    gr.update(visible=False),
                    gr.update(visible=True),
                    gr.update(),
                )
            elif task.status in ("failed", "interrupted"):
                html = build_progress_html(task)
                return (
                    html,
                    gr.update(),
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(),
                )
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

        if poll_timer:
            poll_timer.tick(
                poll_progress,
                inputs=[session_ctx.device_id_state, session_ctx.session_task_state],
                outputs=[
                    self.status,
                    self.output_video,
                    self.generate_btn,
                    self.stop_btn,
                    self.history_gallery.dropdown,
                ],
            )

        # Register history gallery & admin tab events
        self.history_gallery.register_events(session_ctx.device_id_state)
        self.admin_tab.register_events(session_ctx)

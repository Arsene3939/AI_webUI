"""
Image-to-Video (I2V) tab UI and generation logic for MiniMax-H3.
"""
import os
import time
import uuid
from typing import Optional, Dict, Any, List
from PIL import Image
import gradio as gr
from config import (
    ORIGINAL_RATIO_LABEL,
    I2V_ASPECT_RATIOS,
    DEFAULT_QUALITY_LEVEL,
    DEFAULT_MULTIPLE,
    MINIMAX_FIXED_FPS,
    DEFAULT_UNET,
    DEFAULT_CLIP,
    DEFAULT_VIDEO_VAE,
    DEFAULT_AUDIO_VAE,
    resolve_model_names,
    calculate_dimensions,
    calculate_dimensions_adaptive_ratio,
    normalize_aspect_ratio,
    normalize_quality_choice,
    normalize_sampler,
    normalize_scheduler,
    SERVER_STATUS_UPDATING,
    get_server_status,
)
from core.workflow_builder import build_i2v_workflow
from core.admin_manager import AdminManager
from core.comfy_client import upload_media_file
from task_manager import task_manager
from components.video_params import VideoParamsComponent
from components.media_player import VideoPlayerCardComponent, ActionButtonsComponent, build_progress_html
from components.director_block import DirectorBlockComponent
from ui_text import (
    MINIMAX_I2V_FIRST_FRAME_LABEL,
    MINIMAX_I2V_LAST_FRAME_LABEL,
    MINIMAX_I2V_PROMPT_PLACEHOLDER,
    MINIMAX_MSG_NEED_FIRST_FRAME,
    MINIMAX_MSG_NEED_PROMPT,
    MINIMAX_MSG_PREPARING,
    MINIMAX_MSG_RES_DETECT_FAILED,
    MINIMAX_MSG_SERVER_UPDATING,
    MINIMAX_MSG_UPLOAD_IMAGE_FAILED,
    MINIMAX_MSG_UPLOADING_IMAGE,
    MINIMAX_ORIG_SIZE_BADGE_FMT,
    MINIMAX_PROMPT_LABEL,
    MINIMAX_RES_INFO_FMT,
    MINIMAX_TAB_I2V,
    TASK_GENERATE_BTN_DEFAULT,
    TASK_MSG_INTERRUPTED_BY_USER,
    TASK_OUTPUT_VIDEO_LABEL,
)
from utils.logger import get_logger

logger = get_logger("I2VTab")


def on_first_frame_change(img_path: Optional[str], current_quality_str: str):
    """Detects uploaded image dimensions and automatically aligns to distortion-free original aspect ratio."""
    if not img_path or not os.path.exists(img_path):
        w, h = calculate_dimensions("16:9 (橫向風景)", current_quality_str, multiple=DEFAULT_MULTIPLE)
        actual_mp = round((w * h) / 1_000_000, 2)
        return gr.update(), MINIMAX_RES_INFO_FMT.format(w, h, actual_mp), ""
    try:
        current_quality_str = normalize_quality_choice(current_quality_str)
        with Image.open(img_path) as im:
            orig_w, orig_h = im.size
        w, h = calculate_dimensions_adaptive_ratio(orig_w, orig_h, current_quality_str, multiple=DEFAULT_MULTIPLE)
        actual_mp = round((w * h) / 1_000_000, 2)

        info_text = MINIMAX_RES_INFO_FMT.format(w, h, actual_mp)
        badge_text = MINIMAX_ORIG_SIZE_BADGE_FMT.format(orig_w, orig_h)
        return gr.update(value=ORIGINAL_RATIO_LABEL), info_text, badge_text
    except Exception as e:
        return gr.update(), gr.update(), MINIMAX_MSG_RES_DETECT_FAILED.format(str(e))


def handle_i2v_generate(
    first_frame,
    last_frame,
    prompt,
    aspect_ratio,
    quality_level,
    duration,
    seed,
    steps,
    denoise,
    sampler,
    scheduler,
    current_session_task,
    device_id,
    custom_w=None,
    custom_h=None,
    unet_name=DEFAULT_UNET,
    clip_name=DEFAULT_CLIP,
    video_vae=DEFAULT_VIDEO_VAE,
    audio_vae=DEFAULT_AUDIO_VAE,
    on_completed_cb=None,
    request: gr.Request = None,
):
    if not device_id:
        device_id = f"dev_{uuid.uuid4().hex[:6]}"

    if get_server_status() == SERVER_STATUS_UPDATING:
        yield build_progress_html(MINIMAX_MSG_SERVER_UPDATING), None, current_session_task, device_id
        return

    if not first_frame:
        yield build_progress_html(MINIMAX_MSG_NEED_FIRST_FRAME), None, current_session_task, device_id
        return

    if not prompt or not prompt.strip():
        yield build_progress_html(MINIMAX_MSG_NEED_PROMPT), None, current_session_task, device_id
        return

    aspect_ratio = normalize_aspect_ratio(aspect_ratio)
    quality_level = normalize_quality_choice(quality_level)
    sampler = normalize_sampler(sampler)
    scheduler = normalize_scheduler(scheduler)

    w, h = calculate_dimensions(aspect_ratio, quality_level, multiple=DEFAULT_MULTIPLE, image_input=first_frame)

    logger.info("[I2V] Request from device '%s': size=%dx%d, steps=%s, seed=%s, duration=%ss, prompt='%s'",
                device_id, w, h, steps, seed, duration, prompt[:50])
    yield build_progress_html(MINIMAX_MSG_UPLOADING_IMAGE), None, current_session_task, device_id
    try:
        first_frame_fn = upload_media_file(first_frame)
        last_frame_fn = upload_media_file(last_frame) if last_frame else None
    except Exception as e:
        yield build_progress_html(MINIMAX_MSG_UPLOAD_IMAGE_FAILED.format(str(e))), None, current_session_task, device_id
        return

    yield build_progress_html(MINIMAX_MSG_PREPARING), None, current_session_task, device_id

    # 模型選擇把關（Spec 2026-11-02）：只有管理員的合法選擇會生效，其餘一律退回預設模型
    models = resolve_model_names(unet_name, clip_name, video_vae, audio_vae,
                                 is_admin=AdminManager.is_super_user(request))
    if (models["unet"], models["clip"]) != (DEFAULT_UNET, DEFAULT_CLIP):
        logger.info("[I2V] Admin model override: unet=%s clip=%s vaes=%s/%s",
                    models["unet"], models["clip"], models["video_vae"], models["audio_vae"])

    prompt_graph = build_i2v_workflow(
        prompt=prompt,
        first_frame_filename=first_frame_fn,
        last_frame_filename=last_frame_fn,
        width=int(w),
        height=int(h),
        duration_seconds=float(duration),
        seed=int(seed),
        steps=int(steps),
        denoise=float(denoise),
        sampler_name=sampler,
        scheduler_name=scheduler,
        fps=float(MINIMAX_FIXED_FPS),  # 模型只支援 24fps（Spec 任務 5）
        unet_name=models["unet"],
        clip_name=models["clip"],
        video_vae_name=models["video_vae"],
        audio_vae_name=models["audio_vae"],
    )

    saved_params = {
        "first_frame": first_frame,
        "last_frame": last_frame,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "quality_level": quality_level,
        "duration": duration,
        "seed": seed,
        "steps": steps,
        "denoise": denoise,
        "sampler": sampler,
        "scheduler": scheduler,
        "fps": MINIMAX_FIXED_FPS,
        "width": w,
        "height": h,
    }

    task = task_manager.create_task("I2V", prompt, saved_params, device_id=device_id)
    task_manager.start_background_task(task, prompt_graph)

    while True:
        t = task_manager.get_task(task.task_id, device_id=device_id)
        if not t:
            break
        yield build_progress_html(t), t.video_path, t.task_id, device_id
        if t.status in ["completed", "failed", "interrupted"]:
            if t.status == "completed" and on_completed_cb:
                on_completed_cb(device_id, t.task_id)
            break
        time.sleep(0.5)


class I2VTab:
    """Encapsulates Image-to-Video tab layout, parameter cards, and generation lifecycle."""

    def __init__(self):
        self.first_frame: Optional[gr.Image] = None
        self.last_frame: Optional[gr.Image] = None
        self.img_badge: Optional[gr.Markdown] = None
        self.prompt: Optional[gr.Textbox] = None
        self.params_card = VideoParamsComponent(
            aspect_ratio_choices=I2V_ASPECT_RATIOS,
            default_aspect_ratio=ORIGINAL_RATIO_LABEL,
            default_quality=DEFAULT_QUALITY_LEVEL,
            default_duration=2.0,
            default_steps=20,
            include_director_model=True,  # 導演模型下拉進「⚙️ 進階參數」
            include_model_selectors=True,  # 管理員限定模型選擇（Spec 2026-11-02）
        )
        self.action_btns = ActionButtonsComponent(generate_label=TASK_GENERATE_BTN_DEFAULT)
        self.player_card = VideoPlayerCardComponent(label=TASK_OUTPUT_VIDEO_LABEL)
        self.director = DirectorBlockComponent()

    def render(self) -> "I2VTab":
        with gr.Tab(MINIMAX_TAB_I2V):
            with gr.Row():
                with gr.Column(scale=1):
                    with gr.Row():
                        self.first_frame = gr.Image(type="filepath", label=MINIMAX_I2V_FIRST_FRAME_LABEL, height=240)
                        self.last_frame = gr.Image(type="filepath", label=MINIMAX_I2V_LAST_FRAME_LABEL, height=240)

                    self.img_badge = gr.Markdown("")
                    self.prompt = gr.Textbox(
                        label=MINIMAX_PROMPT_LABEL,
                        placeholder=MINIMAX_I2V_PROMPT_PLACEHOLDER,
                        lines=5,
                        value="",
                    )
                    self.director.render()
                    self.params_card.render()
                    self.action_btns.render()

                self.player_card.render()
        return self

    def register_events(self, session_task_state: gr.BrowserState, device_id_state: gr.BrowserState, on_completed_cb=None):
        self.params_card.register_events(image_ref=self.first_frame)
        # 優化提示詞：吃本 tab 的首幀當參考圖，草稿與成品都進出本 tab 的提示詞欄；
        # 導演模型選單住在本 tab 參數卡的「⚙️ 進階參數」裡
        self.director.register_events(self.first_frame, self.prompt, self.params_card.director_model)
        self.first_frame.change(
            on_first_frame_change,
            inputs=[self.first_frame, self.params_card.quality_level],
            outputs=[self.params_card.aspect_ratio, self.params_card.res_info, self.img_badge],
        )

        def generate_wrapper(*args, request: gr.Request = None):
            yield from handle_i2v_generate(*args, on_completed_cb=on_completed_cb, request=request)

        def handle_stop(device_id):
            task_manager.interrupt_device_tasks(device_id=device_id, module="minimax")
            logger.info("[I2V] User stopped generation for device '%s'", device_id)
            return (
                build_progress_html(TASK_MSG_INTERRUPTED_BY_USER),
                gr.update(visible=True),
                gr.update(visible=False),
            )

        gen_event = self.action_btns.generate_btn.click(
            lambda: (gr.update(visible=False), gr.update(visible=True)),
            outputs=[self.action_btns.generate_btn, self.action_btns.stop_btn],
        ).then(
            generate_wrapper,
            inputs=[
                self.first_frame, self.last_frame, self.prompt,
                self.params_card.aspect_ratio, self.params_card.quality_level,
                self.params_card.duration, self.params_card.seed,
                self.params_card.steps, self.params_card.denoise,
                self.params_card.sampler, self.params_card.scheduler,
                session_task_state, device_id_state,
                # 管理員模型選擇下拉（一般使用者為 hidden+預設值，後端仍會退回預設模型）
                self.params_card.model_unet, self.params_card.model_clip,
                self.params_card.model_video_vae, self.params_card.model_audio_vae,
            ],
            outputs=[self.player_card.status, self.player_card.output_video, session_task_state, device_id_state],
            api_name="handle_i2v_generate",
            concurrency_limit=None,
        ).then(
            lambda: (gr.update(visible=True), gr.update(visible=False)),
            outputs=[self.action_btns.generate_btn, self.action_btns.stop_btn],
        )

        self.action_btns.stop_btn.click(
            handle_stop,
            inputs=[device_id_state],
            outputs=[self.player_card.status, self.action_btns.generate_btn, self.action_btns.stop_btn],
            cancels=[gen_event],
        )

    def get_components_for_restore(self) -> List[Any]:
        return [
            self.first_frame,
            self.last_frame,
            self.prompt,
            self.params_card.aspect_ratio,
            self.params_card.quality_level,
            self.params_card.duration,
            self.params_card.seed,
            self.params_card.steps,
            self.params_card.denoise,
            self.params_card.sampler,
            self.params_card.scheduler,
            self.player_card.status,
            self.player_card.output_video,
        ]

    def get_action_btns(self) -> List[Any]:
        return [self.action_btns.generate_btn, self.action_btns.stop_btn]

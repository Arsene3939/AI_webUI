"""
Reference-to-Video (R2V) tab UI and generation logic for MiniMax-H3.
"""
import os
import time
import uuid
from typing import Optional, Dict, Any, List
import gradio as gr
from config import (
    I2V_ASPECT_RATIOS,
    DEFAULT_QUALITY_LEVEL,
    DEFAULT_MULTIPLE,
    DEFAULT_UNET,
    DEFAULT_CLIP,
    DEFAULT_VIDEO_VAE,
    DEFAULT_AUDIO_VAE,
    calculate_dimensions,
    normalize_aspect_ratio,
    normalize_quality_choice,
    normalize_sampler,
    normalize_scheduler,
    SERVER_STATUS_UPDATING,
    get_server_status,
)
from core.workflow_builder import build_r2v_workflow
from core.comfy_client import upload_media_file
from task_manager import task_manager
from components.video_params import VideoParamsComponent
from components.media_player import VideoPlayerCardComponent, ActionButtonsComponent, build_progress_html
from utils.logger import get_logger

logger = get_logger("R2VTab")


def handle_r2v_generate(
    prompt,
    ref_img_1,
    ref_img_2,
    ref_img_3,
    ref_img_4,
    ref_video,
    ref_audio,
    ref_image_size,
    aspect_ratio,
    quality_level,
    duration,
    seed,
    steps,
    denoise,
    sampler,
    scheduler,
    fps,
    current_session_task,
    device_id,
    custom_w=None,
    custom_h=None,
    unet_name=DEFAULT_UNET,
    clip_name=DEFAULT_CLIP,
    video_vae=DEFAULT_VIDEO_VAE,
    audio_vae=DEFAULT_AUDIO_VAE,
    on_completed_cb=None,
):
    if not device_id:
        device_id = f"dev_{uuid.uuid4().hex[:6]}"

    if get_server_status() == SERVER_STATUS_UPDATING:
        yield build_progress_html("⚠️ 伺服器維護/更新中，暫停提交生成任務"), None, current_session_task, device_id
        return

    if not prompt or not prompt.strip():
        yield build_progress_html("❌ 請輸入提示詞"), None, current_session_task, device_id
        return

    aspect_ratio = normalize_aspect_ratio(aspect_ratio)
    quality_level = normalize_quality_choice(quality_level)
    sampler = normalize_sampler(sampler)
    scheduler = normalize_scheduler(scheduler)

    w, h = calculate_dimensions(aspect_ratio, quality_level, multiple=DEFAULT_MULTIPLE, image_input=ref_img_1)

    logger.info("[R2V] Request from device '%s': size=%dx%d, steps=%s, seed=%s, duration=%ss, prompt='%s'",
                device_id, w, h, steps, seed, duration, prompt[:50])

    yield build_progress_html("⚡ 前處理中：正在上傳參考素材..."), None, current_session_task, device_id

    ref_img_files = []
    for img in [ref_img_1, ref_img_2, ref_img_3, ref_img_4]:
        if img:
            try:
                fn = upload_media_file(img)
                ref_img_files.append(fn)
            except Exception as e:
                yield build_progress_html(f"❌ 上傳參考圖失敗: {str(e)}"), None, current_session_task, device_id
                return

    ref_video_fn = None
    if ref_video:
        try:
            ref_video_fn = upload_media_file(ref_video)
        except Exception as e:
            yield build_progress_html(f"❌ 上傳參考影片失敗: {str(e)}"), None, current_session_task, device_id
            return

    ref_audio_fn = None
    if ref_audio:
        try:
            ref_audio_fn = upload_media_file(ref_audio)
        except Exception as e:
            yield build_progress_html(f"❌ 上傳參考音訊失敗: {str(e)}"), None, current_session_task, device_id
            return

    yield build_progress_html("⚡ 前處理中：正在準備生成..."), None, current_session_task, device_id

    prompt_graph = build_r2v_workflow(
        prompt=prompt,
        ref_image_filenames=ref_img_files,
        ref_video_filename=ref_video_fn,
        ref_audio_filename=ref_audio_fn,
        ref_image_size=ref_image_size,
        width=int(w),
        height=int(h),
        duration_seconds=float(duration),
        seed=int(seed),
        steps=int(steps),
        denoise=float(denoise),
        sampler_name=sampler,
        scheduler_name=scheduler,
        fps=float(fps),
        unet_name=DEFAULT_UNET,
        clip_name=DEFAULT_CLIP,
        video_vae_name=DEFAULT_VIDEO_VAE,
        audio_vae_name=DEFAULT_AUDIO_VAE,
    )

    saved_params = {
        "prompt": prompt,
        "ref_img_1": ref_img_1,
        "ref_img_2": ref_img_2,
        "ref_img_3": ref_img_3,
        "ref_img_4": ref_img_4,
        "ref_video": ref_video,
        "ref_audio": ref_audio,
        "ref_image_size": ref_image_size,
        "aspect_ratio": aspect_ratio,
        "quality_level": quality_level,
        "duration": duration,
        "seed": seed,
        "steps": steps,
        "denoise": denoise,
        "sampler": sampler,
        "scheduler": scheduler,
        "fps": fps,
        "width": w,
        "height": h,
    }

    task = task_manager.create_task("R2V", prompt, saved_params, device_id=device_id)
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


class R2VTab:
    """Encapsulates Reference-to-Video tab layout, parameter cards, and generation lifecycle."""

    def __init__(self):
        self.prompt: Optional[gr.Textbox] = None
        self.ref_video: Optional[gr.Video] = None
        self.ref_audio: Optional[gr.Audio] = None
        self.ref_img_1: Optional[gr.Image] = None
        self.ref_img_2: Optional[gr.Image] = None
        self.ref_img_3: Optional[gr.Image] = None
        self.ref_img_4: Optional[gr.Image] = None
        self.ref_image_size: Optional[gr.Radio] = None
        self.params_card = VideoParamsComponent(
            aspect_ratio_choices=I2V_ASPECT_RATIOS,
            default_aspect_ratio="16:9 (橫向風景)",
            default_quality=DEFAULT_QUALITY_LEVEL,
            default_duration=3.0,
            default_steps=20,
            default_fps=24,
        )
        self.action_btns = ActionButtonsComponent(generate_label="🚀 開始生成影片")
        self.player_card = VideoPlayerCardComponent(label="生成影片")

    def render(self) -> "R2VTab":
        with gr.Tab("🎬 參考生影片 (R2V)"):
            with gr.Row():
                with gr.Column(scale=1):
                    self.prompt = gr.Textbox(
                        label="提示詞",
                        placeholder="描述如何結合參考素材（支援主體、動作、風格混合）...",
                        lines=4,
                        value="",
                    )
                    with gr.Accordion("📎 參考影音素材 (選填)", open=False):
                        with gr.Row():
                            self.ref_video = gr.Video(label="參考影片")
                            self.ref_audio = gr.Audio(type="filepath", label="參考音訊")

                    with gr.Accordion("🖼️ 參考圖片素材 (1~4 張選填)", open=False):
                        with gr.Row():
                            self.ref_img_1 = gr.Image(type="filepath", label="參考圖 1")
                            self.ref_img_2 = gr.Image(type="filepath", label="參考圖 2")
                        with gr.Row():
                            self.ref_img_3 = gr.Image(type="filepath", label="參考圖 3")
                            self.ref_img_4 = gr.Image(type="filepath", label="參考圖 4")
                        self.ref_image_size = gr.Radio(
                            choices=["match", "pad"],
                            value="match",
                            label="參考圖縮放模式",
                            info="match: 保持原始比例切齊；pad: 黑邊補齊",
                        )

                    self.params_card.render()
                    self.action_btns.render()

                self.player_card.render()
        return self

    def register_events(self, session_task_state: gr.BrowserState, device_id_state: gr.BrowserState, on_completed_cb=None):
        self.params_card.register_events(image_ref=self.ref_img_1)

        def generate_wrapper(*args):
            yield from handle_r2v_generate(*args, on_completed_cb=on_completed_cb)

        def handle_stop(device_id):
            task_manager.interrupt_device_tasks(device_id=device_id, module="minimax")
            logger.info("[R2V] User stopped generation for device '%s'", device_id)
            return (
                build_progress_html("⚠️ 任務已被手動中斷"),
                gr.update(visible=True),
                gr.update(visible=False),
            )

        gen_event = self.action_btns.generate_btn.click(
            lambda: (gr.update(visible=False), gr.update(visible=True)),
            outputs=[self.action_btns.generate_btn, self.action_btns.stop_btn],
        ).then(
            generate_wrapper,
            inputs=[
                self.prompt,
                self.ref_img_1, self.ref_img_2, self.ref_img_3, self.ref_img_4,
                self.ref_video, self.ref_audio, self.ref_image_size,
                self.params_card.aspect_ratio, self.params_card.quality_level,
                self.params_card.duration, self.params_card.seed,
                self.params_card.steps, self.params_card.denoise,
                self.params_card.sampler, self.params_card.scheduler,
                self.params_card.fps,
                session_task_state, device_id_state,
            ],
            outputs=[self.player_card.status, self.player_card.output_video, session_task_state, device_id_state],
            api_name="handle_r2v_generate",
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
            self.prompt,
            self.ref_video,
            self.ref_audio,
            self.ref_img_1,
            self.ref_img_2,
            self.ref_img_3,
            self.ref_img_4,
            self.ref_image_size,
            self.params_card.aspect_ratio,
            self.params_card.quality_level,
            self.params_card.duration,
            self.params_card.seed,
            self.params_card.steps,
            self.params_card.denoise,
            self.params_card.fps,
            self.params_card.sampler,
            self.params_card.scheduler,
            self.player_card.status,
            self.player_card.output_video,
        ]

    def get_action_btns(self) -> List[Any]:
        return [self.action_btns.generate_btn, self.action_btns.stop_btn]

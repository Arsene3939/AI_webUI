"""
Text-to-Video (T2V) tab UI and generation logic for MiniMax-H3.
"""
import os
import time
import uuid
from typing import Optional, Dict, Any, List
import gradio as gr
from config import (
    T2V_ASPECT_RATIOS,
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
from workflow_builder import build_t2v_workflow
from task_manager import task_manager
from components.video_params import VideoParamsComponent
from components.media_player import VideoPlayerCardComponent, ActionButtonsComponent, build_progress_html
from logger import get_logger

logger = get_logger("T2VTab")


def handle_t2v_generate(
    prompt,
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

    w, h = calculate_dimensions(aspect_ratio, quality_level, multiple=DEFAULT_MULTIPLE)

    yield build_progress_html("⚡ 前處理中：正在準備生成..."), None, current_session_task, device_id
    logger.info("[T2V] Request from device '%s': size=%dx%d, steps=%s, seed=%s, duration=%ss, prompt='%s'",
                device_id, w, h, steps, seed, duration, prompt[:50])

    prompt_graph = build_t2v_workflow(
        prompt=prompt,
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

    task = task_manager.create_task("T2V", prompt, saved_params, device_id=device_id)
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


class T2VTab:
    """Encapsulates Text-to-Video tab layout, parameter cards, and generation lifecycle."""

    def __init__(self):
        self.prompt: Optional[gr.Textbox] = None
        self.params_card = VideoParamsComponent(
            aspect_ratio_choices=T2V_ASPECT_RATIOS,
            default_aspect_ratio="16:9 (橫向風景)",
            default_quality=DEFAULT_QUALITY_LEVEL,
            default_duration=2.0,
            default_steps=20,
            default_fps=24,
        )
        self.action_btns = ActionButtonsComponent(generate_label="🚀 開始生成影片")
        self.player_card = VideoPlayerCardComponent(label="生成影片")

    def render(self) -> "T2VTab":
        with gr.Tab("✍️ 文生影片 (T2V)"):
            with gr.Row():
                with gr.Column(scale=1):
                    self.prompt = gr.Textbox(
                        label="提示詞",
                        placeholder="描述想生成的場景、運鏡、角色動態、氛圍與背景音樂/音效...",
                        lines=6,
                        value="",
                    )
                    self.params_card.render()
                    self.action_btns.render()

                self.player_card.render()
        return self

    def register_events(self, session_task_state: gr.BrowserState, device_id_state: gr.BrowserState, on_completed_cb=None):
        self.params_card.register_events()

        def generate_wrapper(*args):
            yield from handle_t2v_generate(*args, on_completed_cb=on_completed_cb)

        def handle_stop(device_id):
            task_manager.interrupt_device_tasks(device_id=device_id)
            logger.info("[T2V] User stopped generation for device '%s'", device_id)
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
                self.params_card.aspect_ratio, self.params_card.quality_level,
                self.params_card.duration, self.params_card.seed,
                self.params_card.steps, self.params_card.denoise,
                self.params_card.sampler, self.params_card.scheduler,
                self.params_card.fps,
                session_task_state, device_id_state,
            ],
            outputs=[self.player_card.status, self.player_card.output_video, session_task_state, device_id_state],
            api_name="handle_t2v_generate",
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

"""
MiniMax-H3 Mobile-Friendly Gradio WebUI with Persistent Session, Input Restoration,
and Strict Per-Device Isolation.
"""
import os
import time
import uuid
import random
import gradio as gr
from config import (
    COMFY_SERVER_URL,
    WEBUI_HOST,
    WEBUI_PORT,
    DEFAULT_UNET,
    DEFAULT_CLIP,
    DEFAULT_VIDEO_VAE,
    DEFAULT_AUDIO_VAE,
    RESOLUTION_PRESETS,
    SAMPLER_CHOICES,
    SCHEDULER_CHOICES,
    get_lan_ip,
)
from workflow_builder import (
    build_i2v_workflow,
    build_t2v_workflow,
    build_r2v_workflow,
)
from comfy_client import (
    check_server,
    start_comfyui_backend,
    upload_media_file,
)
from task_manager import task_manager

CUSTOM_CSS = """
/* Responsive adjustments for mobile screens */
.container {
    max-width: 1000px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding: 10px !important;
}

/* Finger-friendly buttons */
button.primary-btn {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    height: 52px !important;
    border-radius: 10px !important;
    margin-top: 10px !important;
    box-shadow: 0 4px 12px rgba(0, 100, 255, 0.25) !important;
}

button.recover-btn {
    font-weight: 600 !important;
    border-radius: 8px !important;
    background-color: #0369a1 !important;
    color: white !important;
}

/* Header Banner */
.header-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    padding: 16px 20px;
    border-radius: 12px;
    margin-bottom: 12px;
    color: #f8fafc;
}

.ip-badge {
    background-color: #0284c7;
    color: white;
    padding: 4px 10px;
    border-radius: 6px;
    font-family: monospace;
    font-weight: bold;
}

/* Mobile video player fix */
video {
    width: 100% !important;
    border-radius: 8px !important;
    background-color: #000;
}
"""

lan_ip = get_lan_ip()
server_ok, server_status_msg = check_server(COMFY_SERVER_URL)


def build_header_html(status_text=None, device_id=None):
    if status_text is None:
        _, status_text = check_server(COMFY_SERVER_URL)
    dev_str = f" | 📱 裝置識別: <code>{device_id[:8]}...</code>" if device_id else ""
    return f"""
    <div class="header-card">
        <h2 style="margin: 0 0 8px 0; font-size: 1.5rem;">🎬 MiniMax-H3 全模態影片生成系統</h2>
        <div style="font-size: 0.95rem; opacity: 0.9; line-height: 1.6;">
            📱 <b>手機內網連線網址：</b> <span class="ip-badge">http://{lan_ip}:{WEBUI_PORT}</span>
            <span style="margin-left: 12px;">|</span>
            <span style="margin-left: 12px;">🖥️ 後端狀態：<b>{status_text}</b></span>
            {dev_str}
        </div>
        <div style="font-size: 0.85rem; color: #94a3b8; margin-top: 6px;">
            💡 裝置隔離保護：每個裝置只會存取並恢復自己的任務與輸入參數，完全與其他裝置隔離。
        </div>
    </div>
    """


def update_resolution(preset_name, current_w, current_h):
    if preset_name in RESOLUTION_PRESETS:
        w, h = RESOLUTION_PRESETS[preset_name]
        if w is not None and h is not None:
            return gr.update(value=w), gr.update(value=h)
    return gr.update(value=current_w), gr.update(value=current_h)


def generate_random_seed():
    return random.randint(1, 999999999999999)


def get_history_dropdown_choices(device_id):
    if not device_id:
        return []
    completed = task_manager.get_completed_tasks_for_device(device_id)
    choices = []
    for t in completed:
        t_str = time.strftime("%m/%d %H:%M", time.localtime(t.created_at))
        short_prompt = (t.prompt[:30] + "...") if len(t.prompt) > 30 else t.prompt
        label = f"[{t.task_type}] {t_str} | {short_prompt}"
        choices.append((label, t.task_id))
    return choices


def on_select_history_item(selected_task_id, device_id):
    if not selected_task_id:
        return None, "請選擇上方歷史任務"
    task = task_manager.get_task(selected_task_id, device_id=device_id)
    if not task or not task.video_path or not os.path.exists(task.video_path):
        return None, "⚠️ 找不到該影片檔案（可能已被移除或不屬於此裝置）"
    
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task.created_at))
    info_md = f"""
    ### 📜 任務詳細資料
    * **任務類型**：`{task.task_type}`
    * **建立時間**：{t_str}
    * **生成耗時**：{task.elapsed} 秒
    * **檔案路徑**：`{os.path.basename(task.video_path)}`
    * **完整提示詞**：
    ```text
    {task.prompt}
    ```
    """
    return task.video_path, info_md


# --- Generation Handlers with Input Archiving & Device Isolation ---

def handle_i2v_generate(
    first_frame,
    last_frame,
    prompt,
    res_preset,
    custom_w,
    custom_h,
    duration,
    seed,
    steps,
    denoise,
    sampler,
    scheduler,
    fps,
    unet_name,
    clip_name,
    video_vae,
    audio_vae,
    current_session_task,
    device_id,
):
    if not device_id:
        device_id = f"dev_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    if not first_frame:
        yield "❌ 請至少上傳「首幀圖片」！", None, current_session_task, device_id
        return

    if not prompt or not prompt.strip():
        yield "❌ 提示詞 (Prompt) 不可為空！", None, current_session_task, device_id
        return

    w, h = custom_w, custom_h
    if res_preset in RESOLUTION_PRESETS:
        pw, ph = RESOLUTION_PRESETS[res_preset]
        if pw and ph:
            w, h = pw, ph

    yield "📤 正在上傳首幀 (及尾幀) 圖片至 ComfyUI...", None, current_session_task, device_id
    try:
        first_frame_fn = upload_media_file(first_frame)
        last_frame_fn = upload_media_file(last_frame) if last_frame else None
    except Exception as e:
        yield f"❌ 上傳圖片失敗: {str(e)}", None, current_session_task, device_id
        return

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
        fps=float(fps),
        unet_name=unet_name,
        clip_name=clip_name,
        video_vae_name=video_vae,
        audio_vae_name=audio_vae,
    )

    # Save full parameters for complete state restoration
    saved_params = {
        "first_frame": first_frame,
        "last_frame": last_frame,
        "prompt": prompt,
        "res_preset": res_preset,
        "custom_w": custom_w,
        "custom_h": custom_h,
        "duration": duration,
        "seed": seed,
        "steps": steps,
        "denoise": denoise,
        "sampler": sampler,
        "scheduler": scheduler,
        "fps": fps,
        "unet_name": unet_name,
        "clip_name": clip_name,
        "video_vae": video_vae,
        "audio_vae": audio_vae,
    }

    task = task_manager.create_task("I2V", prompt, saved_params, device_id=device_id)
    task_manager.start_background_task(task, prompt_graph)

    while True:
        t = task_manager.get_task(task.task_id, device_id=device_id)
        if not t:
            break
        yield t.message, t.video_path, t.task_id, device_id
        if t.status in ["completed", "failed"]:
            break
        time.sleep(1.5)


def handle_t2v_generate(
    prompt,
    res_preset,
    custom_w,
    custom_h,
    duration,
    seed,
    steps,
    denoise,
    sampler,
    scheduler,
    fps,
    unet_name,
    clip_name,
    video_vae,
    audio_vae,
    current_session_task,
    device_id,
):
    if not device_id:
        device_id = f"dev_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    if not prompt or not prompt.strip():
        yield "❌ 提示詞 (Prompt) 不可為空！", None, current_session_task, device_id
        return

    w, h = custom_w, custom_h
    if res_preset in RESOLUTION_PRESETS:
        pw, ph = RESOLUTION_PRESETS[res_preset]
        if pw and ph:
            w, h = pw, ph

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
        unet_name=unet_name,
        clip_name=clip_name,
        video_vae_name=video_vae,
        audio_vae_name=audio_vae,
    )

    saved_params = {
        "prompt": prompt,
        "res_preset": res_preset,
        "custom_w": custom_w,
        "custom_h": custom_h,
        "duration": duration,
        "seed": seed,
        "steps": steps,
        "denoise": denoise,
        "sampler": sampler,
        "scheduler": scheduler,
        "fps": fps,
        "unet_name": unet_name,
        "clip_name": clip_name,
        "video_vae": video_vae,
        "audio_vae": audio_vae,
    }

    task = task_manager.create_task("T2V", prompt, saved_params, device_id=device_id)
    task_manager.start_background_task(task, prompt_graph)

    while True:
        t = task_manager.get_task(task.task_id, device_id=device_id)
        if not t:
            break
        yield t.message, t.video_path, t.task_id, device_id
        if t.status in ["completed", "failed"]:
            break
        time.sleep(1.5)


def handle_r2v_generate(
    prompt,
    ref_img_1,
    ref_img_2,
    ref_img_3,
    ref_img_4,
    ref_video,
    ref_audio,
    ref_image_size,
    res_preset,
    custom_w,
    custom_h,
    duration,
    seed,
    steps,
    denoise,
    sampler,
    scheduler,
    fps,
    unet_name,
    clip_name,
    video_vae,
    audio_vae,
    current_session_task,
    device_id,
):
    if not device_id:
        device_id = f"dev_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    if not prompt or not prompt.strip():
        yield "❌ 提示詞 (Prompt) 不可為空！", None, current_session_task, device_id
        return

    w, h = custom_w, custom_h
    if res_preset in RESOLUTION_PRESETS:
        pw, ph = RESOLUTION_PRESETS[res_preset]
        if pw and ph:
            w, h = pw, ph

    yield "📤 正在上傳參考多媒體素材至 ComfyUI...", None, current_session_task, device_id

    ref_img_files = []
    for img in [ref_img_1, ref_img_2, ref_img_3, ref_img_4]:
        if img:
            try:
                fn = upload_media_file(img)
                ref_img_files.append(fn)
            except Exception as e:
                yield f"❌ 上傳參考圖失敗: {str(e)}", None, current_session_task, device_id
                return

    ref_video_fn = None
    if ref_video:
        try:
            ref_video_fn = upload_media_file(ref_video)
        except Exception as e:
            yield f"❌ 上傳參考影片失敗: {str(e)}", None, current_session_task, device_id
            return

    ref_audio_fn = None
    if ref_audio:
        try:
            ref_audio_fn = upload_media_file(ref_audio)
        except Exception as e:
            yield f"❌ 上傳參考音訊失敗: {str(e)}", None, current_session_task, device_id
            return

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
        unet_name=unet_name,
        clip_name=clip_name,
        video_vae_name=video_vae,
        audio_vae_name=audio_vae,
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
        "res_preset": res_preset,
        "custom_w": custom_w,
        "custom_h": custom_h,
        "duration": duration,
        "seed": seed,
        "steps": steps,
        "denoise": denoise,
        "sampler": sampler,
        "scheduler": scheduler,
        "fps": fps,
        "unet_name": unet_name,
        "clip_name": clip_name,
        "video_vae": video_vae,
        "audio_vae": audio_vae,
    }

    task = task_manager.create_task("R2V", prompt, saved_params, device_id=device_id)
    task_manager.start_background_task(task, prompt_graph)

    while True:
        t = task_manager.get_task(task.task_id, device_id=device_id)
        if not t:
            break
        yield t.message, t.video_path, t.task_id, device_id
        if t.status in ["completed", "failed"]:
            break
        time.sleep(1.5)


# --- Full State Restoration Callback for demo.load and Recover Buttons ---

def restore_device_state(stored_device_id, stored_task_id):
    """
    Called on page load (demo.load) or recover button click.
    Restores all inputs, parameters, and generated video for THIS specific device only.
    """
    if not stored_device_id:
        stored_device_id = f"dev_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    # Fetch task for THIS device only (No cross-device leakage!)
    task = task_manager.get_task(stored_task_id, device_id=stored_device_id) or task_manager.get_latest_task_for_device(stored_device_id)

    # Defaults (Leave untouched if no task)
    i2v_updates = [gr.update()] * 15
    t2v_updates = [gr.update()] * 13
    r2v_updates = [gr.update()] * 20
    history_choices = get_history_dropdown_choices(stored_device_id)

    if task and task.params:
        p = task.params
        if task.task_type == "I2V":
            i2v_updates = [
                gr.update(value=p.get("first_frame")),
                gr.update(value=p.get("last_frame")),
                gr.update(value=p.get("prompt", task.prompt)),
                gr.update(value=p.get("res_preset", "16:9 橫向風景 (1344 x 768)")),
                gr.update(value=p.get("custom_w", 1344)),
                gr.update(value=p.get("custom_h", 768)),
                gr.update(value=p.get("duration", 2.0)),
                gr.update(value=p.get("seed", 1)),
                gr.update(value=p.get("steps", 20)),
                gr.update(value=p.get("denoise", 1.0)),
                gr.update(value=p.get("fps", 24)),
                gr.update(value=p.get("sampler", "res_multistep")),
                gr.update(value=p.get("scheduler", "simple")),
                gr.update(value=task.message),
                gr.update(value=task.video_path if task.video_path and os.path.exists(task.video_path) else None),
            ]
        elif task.task_type == "T2V":
            t2v_updates = [
                gr.update(value=p.get("prompt", task.prompt)),
                gr.update(value=p.get("res_preset", "16:9 橫向風景 (1344 x 768)")),
                gr.update(value=p.get("custom_w", 1344)),
                gr.update(value=p.get("custom_h", 768)),
                gr.update(value=p.get("duration", 2.0)),
                gr.update(value=p.get("seed", 1)),
                gr.update(value=p.get("steps", 20)),
                gr.update(value=p.get("denoise", 1.0)),
                gr.update(value=p.get("fps", 24)),
                gr.update(value=p.get("sampler", "res_multistep")),
                gr.update(value=p.get("scheduler", "simple")),
                gr.update(value=task.message),
                gr.update(value=task.video_path if task.video_path and os.path.exists(task.video_path) else None),
            ]
        elif task.task_type == "R2V":
            r2v_updates = [
                gr.update(value=p.get("prompt", task.prompt)),
                gr.update(value=p.get("ref_video")),
                gr.update(value=p.get("ref_audio")),
                gr.update(value=p.get("ref_img_1")),
                gr.update(value=p.get("ref_img_2")),
                gr.update(value=p.get("ref_img_3")),
                gr.update(value=p.get("ref_img_4")),
                gr.update(value=p.get("ref_image_size", "match")),
                gr.update(value=p.get("res_preset", "16:9 橫向風景 (1344 x 768)")),
                gr.update(value=p.get("custom_w", 1344)),
                gr.update(value=p.get("custom_h", 768)),
                gr.update(value=p.get("duration", 3.0)),
                gr.update(value=p.get("seed", 1)),
                gr.update(value=p.get("steps", 20)),
                gr.update(value=p.get("denoise", 1.0)),
                gr.update(value=p.get("fps", 24)),
                gr.update(value=p.get("sampler", "res_multistep")),
                gr.update(value=p.get("scheduler", "simple")),
                gr.update(value=task.message),
                gr.update(value=task.video_path if task.video_path and os.path.exists(task.video_path) else None),
            ]

    active_task_id = task.task_id if task else stored_task_id
    header = build_header_html(device_id=stored_device_id)

    return (
        stored_device_id,
        active_task_id,
        header,
        gr.update(choices=history_choices),
        *i2v_updates,
        *t2v_updates,
        *r2v_updates,
    )


# --- UI Definition ---

with gr.Blocks(title="MiniMax-H3 AI Video WebUI") as demo:
    # Strictly isolated persistent states per browser/device LocalStorage
    device_id_state = gr.BrowserState(default_value="", storage_key="minimax_device_id")
    session_task_state = gr.BrowserState(default_value="", storage_key="minimax_active_task_id")

    header_html = gr.HTML(build_header_html(server_status_msg))

    with gr.Row():
        start_backend_btn = gr.Button("⚡ 啟動 ComfyUI 後端", variant="secondary", scale=2)
        refresh_status_btn = gr.Button("🔄 刷新連線狀態", variant="secondary", scale=1)
    
    backend_status_msg = gr.Markdown("")

    def on_start_backend(dev_id):
        ok, msg = start_comfyui_backend(COMFY_SERVER_URL)
        return build_header_html(msg, dev_id), f"**狀態反饋**：{msg}"

    def on_refresh_status(dev_id):
        ok, msg = check_server(COMFY_SERVER_URL)
        return build_header_html(msg, dev_id), f"**目前狀態**：{msg}"

    start_backend_btn.click(on_start_backend, inputs=[device_id_state], outputs=[header_html, backend_status_msg])
    refresh_status_btn.click(on_refresh_status, inputs=[device_id_state], outputs=[header_html, backend_status_msg])

    with gr.Tabs() as tabs:
        # ==========================================
        # TAB 1: 圖+文生影片 (I2V)
        # ==========================================
        with gr.Tab("🖼️ 圖+文生影片 (I2V)"):
            with gr.Row():
                with gr.Column(scale=1):
                    with gr.Row():
                        i2v_first_frame = gr.Image(type="filepath", label="首幀圖片 (必填 First Frame)", height=240)
                        i2v_last_frame = gr.Image(type="filepath", label="尾幀圖片 (選填 Last Frame - 首尾過渡)", height=240)

                    i2v_prompt = gr.Textbox(
                        label="提示詞 (Prompt)",
                        placeholder="詳細描述畫面的動態、角色動作、物理反饋、鏡頭運動，以及音效/語音（支援中英文）...",
                        lines=5,
                        value="二次元動畫風格，美少女站在櫻花飄落的街道上，微風吹拂她的長髮與裙襬，少女回眸露出溫柔微笑，伴隨輕柔微風聲與清脆鳥鳴。"
                    )

                    with gr.Row():
                        i2v_res_preset = gr.Dropdown(
                            choices=list(RESOLUTION_PRESETS.keys()),
                            value="16:9 橫向風景 (1344 x 768)",
                            label="常用解析度比例",
                            scale=2
                        )
                        i2v_duration = gr.Slider(
                            minimum=1.0, maximum=15.0, value=2.0, step=0.5,
                            label="時長(秒)", info="自動吸附 17k+5 幀數", scale=1
                        )

                    with gr.Row():
                        i2v_seed = gr.Number(value=1, precision=0, label="隨機種子 (Seed)", scale=2)
                        i2v_rand_btn = gr.Button("🎲 隨機", scale=1)

                    with gr.Accordion("⚙️ 進階參數 (模型與取樣設定)", open=False):
                        with gr.Row():
                            i2v_custom_w = gr.Slider(minimum=256, maximum=1920, value=1344, step=32, label="自訂寬度 (Width)")
                            i2v_custom_h = gr.Slider(minimum=256, maximum=1920, value=768, step=32, label="自訂高度 (Height)")
                        with gr.Row():
                            i2v_steps = gr.Slider(minimum=1, maximum=50, value=20, step=1, label="取樣步數 (Steps)")
                            i2v_denoise = gr.Slider(minimum=0.1, maximum=1.0, value=1.0, step=0.05, label="去噪強度 (Denoise)")
                            i2v_fps = gr.Slider(minimum=12, maximum=60, value=24, step=1, label="幀率 (FPS)")
                        with gr.Row():
                            i2v_sampler = gr.Dropdown(choices=SAMPLER_CHOICES, value="res_multistep", label="取樣器 (Sampler)")
                            i2v_scheduler = gr.Dropdown(choices=SCHEDULER_CHOICES, value="simple", label="調度器 (Scheduler)")
                        with gr.Row():
                            i2v_unet = gr.Textbox(value=DEFAULT_UNET, label="Diffusion Model (UNET)")
                            i2v_clip = gr.Textbox(value=DEFAULT_CLIP, label="Text Encoder (CLIP)")
                        with gr.Row():
                            i2v_v_vae = gr.Textbox(value=DEFAULT_VIDEO_VAE, label="Video VAE")
                            i2v_a_vae = gr.Textbox(value=DEFAULT_AUDIO_VAE, label="Audio VAE")

                    i2v_btn = gr.Button("🚀 開始生成圖生影片 (I2V)", variant="primary", elem_classes=["primary-btn"])

                with gr.Column(scale=1):
                    with gr.Row():
                        i2v_status = gr.Markdown("🟢 準備就緒，點擊按鈕即可開始生成。")
                        i2v_recover_btn = gr.Button("🔄 恢復本機最後進度與輸入", variant="secondary", size="sm")

                    i2v_output_video = gr.Video(label="生成結果影片 (自帶原生立體聲音效)", autoplay=True, interactive=False)

            i2v_res_preset.change(update_resolution, inputs=[i2v_res_preset, i2v_custom_w, i2v_custom_h], outputs=[i2v_custom_w, i2v_custom_h])
            i2v_rand_btn.click(generate_random_seed, outputs=[i2v_seed])
            i2v_btn.click(
                handle_i2v_generate,
                inputs=[
                    i2v_first_frame, i2v_last_frame, i2v_prompt, i2v_res_preset,
                    i2v_custom_w, i2v_custom_h, i2v_duration, i2v_seed,
                    i2v_steps, i2v_denoise, i2v_sampler, i2v_scheduler, i2v_fps,
                    i2v_unet, i2v_clip, i2v_v_vae, i2v_a_vae,
                    session_task_state, device_id_state
                ],
                outputs=[i2v_status, i2v_output_video, session_task_state, device_id_state]
            )

        # ==========================================
        # TAB 2: 純文生影片 (T2V)
        # ==========================================
        with gr.Tab("✍️ 純文生影片 (T2V)"):
            with gr.Row():
                with gr.Column(scale=1):
                    t2v_prompt = gr.Textbox(
                        label="提示詞 (Prompt)",
                        placeholder="請詳細描述想生成的場景、運鏡、角色動態、氛圍與背景音樂/音效（MiniMax-H3 原生支援音視訊聯合生成）...",
                        lines=6,
                        value="電影感廣角鏡頭，日落時分的未來賽博龐克都市，雨水在霓虹燈招牌下反光，一輛浮空飛車從高樓間穿梭而過。音訊：低沉科幻引擎轟鳴聲與淅淅瀝瀝的雨水聲。"
                    )

                    with gr.Row():
                        t2v_res_preset = gr.Dropdown(
                            choices=list(RESOLUTION_PRESETS.keys()),
                            value="16:9 橫向風景 (1344 x 768)",
                            label="常用解析度比例",
                            scale=2
                        )
                        t2v_duration = gr.Slider(
                            minimum=1.0, maximum=15.0, value=2.0, step=0.5,
                            label="時長(秒)", info="自動吸附 17k+5 幀數", scale=1
                        )

                    with gr.Row():
                        t2v_seed = gr.Number(value=1, precision=0, label="隨機種子 (Seed)", scale=2)
                        t2v_rand_btn = gr.Button("🎲 隨機", scale=1)

                    with gr.Accordion("⚙️ 進階參數 (模型與取樣設定)", open=False):
                        with gr.Row():
                            t2v_custom_w = gr.Slider(minimum=256, maximum=1920, value=1344, step=32, label="自訂寬度 (Width)")
                            t2v_custom_h = gr.Slider(minimum=256, maximum=1920, value=768, step=32, label="自訂高度 (Height)")
                        with gr.Row():
                            t2v_steps = gr.Slider(minimum=1, maximum=50, value=20, step=1, label="取樣步數 (Steps)")
                            t2v_denoise = gr.Slider(minimum=0.1, maximum=1.0, value=1.0, step=0.05, label="去噪強度 (Denoise)")
                            t2v_fps = gr.Slider(minimum=12, maximum=60, value=24, step=1, label="幀率 (FPS)")
                        with gr.Row():
                            t2v_sampler = gr.Dropdown(choices=SAMPLER_CHOICES, value="res_multistep", label="取樣器 (Sampler)")
                            t2v_scheduler = gr.Dropdown(choices=SCHEDULER_CHOICES, value="simple", label="調度器 (Scheduler)")
                        with gr.Row():
                            t2v_unet = gr.Textbox(value=DEFAULT_UNET, label="Diffusion Model (UNET)")
                            t2v_clip = gr.Textbox(value=DEFAULT_CLIP, label="Text Encoder (CLIP)")
                        with gr.Row():
                            t2v_v_vae = gr.Textbox(value=DEFAULT_VIDEO_VAE, label="Video VAE")
                            t2v_a_vae = gr.Textbox(value=DEFAULT_AUDIO_VAE, label="Audio VAE")

                    t2v_btn = gr.Button("🚀 開始生成文生影片 (T2V)", variant="primary", elem_classes=["primary-btn"])

                with gr.Column(scale=1):
                    with gr.Row():
                        t2v_status = gr.Markdown("🟢 準備就緒，點擊按鈕即可開始生成。")
                        t2v_recover_btn = gr.Button("🔄 恢復本機最後進度與輸入", variant="secondary", size="sm")

                    t2v_output_video = gr.Video(label="生成結果影片 (自帶原生立體聲音效)", autoplay=True, interactive=False)

            t2v_res_preset.change(update_resolution, inputs=[t2v_res_preset, t2v_custom_w, t2v_custom_h], outputs=[t2v_custom_w, t2v_custom_h])
            t2v_rand_btn.click(generate_random_seed, outputs=[t2v_seed])
            t2v_btn.click(
                handle_t2v_generate,
                inputs=[
                    t2v_prompt, t2v_res_preset,
                    t2v_custom_w, t2v_custom_h, t2v_duration, t2v_seed,
                    t2v_steps, t2v_denoise, t2v_sampler, t2v_scheduler, t2v_fps,
                    t2v_unet, t2v_clip, t2v_v_vae, t2v_a_vae,
                    session_task_state, device_id_state
                ],
                outputs=[t2v_status, t2v_output_video, session_task_state, device_id_state]
            )

        # ==========================================
        # TAB 3: 影片生影片 / 參考生成 (R2V)
        # ==========================================
        with gr.Tab("🎬 影片生影片 (R2V / V2V)"):
            with gr.Row():
                with gr.Column(scale=1):
                    r2v_prompt = gr.Textbox(
                        label="提示詞 (Prompt - 可包含引用標籤)",
                        placeholder="請使用 <Picture 1>, <Picture 2>, <Video 1>, <Audio 1> 精確關聯參考素材。例如：'根據 <Picture 1> 的角色特徵，參考 <Video 1> 的動作姿勢，生成動作影片...'",
                        lines=5,
                        value="保持 <Picture 1> 的角色外觀與特徵一致，參考 <Video 1> 中的動作與走位，生成流暢連續動作。音效：同步生成腳步聲與環境音。"
                    )

                    with gr.Row():
                        r2v_video = gr.Video(label="參考影片 (<Video 1>)", height=220)
                        r2v_audio = gr.Audio(label="獨立參考音訊 (<Audio 1> 選填)", type="filepath")

                    with gr.Accordion("🖼️ 參考圖片 (可選 1 ~ 4 張 Picture 標籤)", open=False):
                        with gr.Row():
                            r2v_img1 = gr.Image(type="filepath", label="參考圖 1 (<Picture 1>)", height=180)
                            r2v_img2 = gr.Image(type="filepath", label="參考圖 2 (<Picture 2>)", height=180)
                        with gr.Row():
                            r2v_img3 = gr.Image(type="filepath", label="參考圖 3 (<Picture 3>)", height=180)
                            r2v_img4 = gr.Image(type="filepath", label="參考圖 4 (<Picture 4>)", height=180)

                    with gr.Row():
                        r2v_image_size = gr.Radio(
                            choices=["match", "max"],
                            value="match",
                            label="參考圖尺寸模式",
                            info="match: 快速匹配生成畫幅 | max: 2048px 高保真 (較慢)"
                        )
                        r2v_duration = gr.Slider(
                            minimum=1.0, maximum=18.0, value=3.0, step=0.5,
                            label="時長(秒)", info="自動吸附 17k+5 幀數"
                        )

                    with gr.Row():
                        r2v_res_preset = gr.Dropdown(
                            choices=list(RESOLUTION_PRESETS.keys()),
                            value="16:9 橫向風景 (1344 x 768)",
                            label="常用解析度比例",
                            scale=2
                        )
                        r2v_seed = gr.Number(value=1, precision=0, label="隨機種子 (Seed)", scale=1)
                        r2v_rand_btn = gr.Button("🎲 隨機", scale=1)

                    with gr.Accordion("⚙️ 進階參數 (模型與取樣設定)", open=False):
                        with gr.Row():
                            r2v_custom_w = gr.Slider(minimum=256, maximum=1920, value=1344, step=32, label="自訂寬度 (Width)")
                            r2v_custom_h = gr.Slider(minimum=256, maximum=1920, value=768, step=32, label="自訂高度 (Height)")
                        with gr.Row():
                            r2v_steps = gr.Slider(minimum=1, maximum=50, value=20, step=1, label="取樣步數 (Steps)")
                            r2v_denoise = gr.Slider(minimum=0.1, maximum=1.0, value=1.0, step=0.05, label="去噪強度 (Denoise)")
                            r2v_fps = gr.Slider(minimum=12, maximum=60, value=24, step=1, label="幀率 (FPS)")
                        with gr.Row():
                            r2v_sampler = gr.Dropdown(choices=SAMPLER_CHOICES, value="res_multistep", label="取樣器 (Sampler)")
                            r2v_scheduler = gr.Dropdown(choices=SCHEDULER_CHOICES, value="simple", label="調度器 (Scheduler)")
                        with gr.Row():
                            r2v_unet = gr.Textbox(value=DEFAULT_UNET, label="Diffusion Model (UNET)")
                            r2v_clip = gr.Textbox(value=DEFAULT_CLIP, label="Text Encoder (CLIP)")
                        with gr.Row():
                            r2v_v_vae = gr.Textbox(value=DEFAULT_VIDEO_VAE, label="Video VAE")
                            r2v_a_vae = gr.Textbox(value=DEFAULT_AUDIO_VAE, label="Audio VAE")

                    r2v_btn = gr.Button("🚀 開始生成影片生影片 (R2V)", variant="primary", elem_classes=["primary-btn"])

                with gr.Column(scale=1):
                    with gr.Row():
                        r2v_status = gr.Markdown("🟢 準備就緒，點擊按鈕即可開始生成。")
                        r2v_recover_btn = gr.Button("🔄 恢復本機最後進度與輸入", variant="secondary", size="sm")

                    r2v_output_video = gr.Video(label="生成結果影片 (自帶原生立體聲音效)", autoplay=True, interactive=False)

            r2v_res_preset.change(update_resolution, inputs=[r2v_res_preset, r2v_custom_w, r2v_custom_h], outputs=[r2v_custom_w, r2v_custom_h])
            r2v_rand_btn.click(generate_random_seed, outputs=[r2v_seed])
            r2v_btn.click(
                handle_r2v_generate,
                inputs=[
                    r2v_prompt, r2v_img1, r2v_img2, r2v_img3, r2v_img4,
                    r2v_video, r2v_audio, r2v_image_size, r2v_res_preset,
                    r2v_custom_w, r2v_custom_h, r2v_duration, r2v_seed,
                    r2v_steps, r2v_denoise, r2v_sampler, r2v_scheduler, r2v_fps,
                    r2v_unet, r2v_clip, r2v_v_vae, r2v_a_vae,
                    session_task_state, device_id_state
                ],
                outputs=[r2v_status, r2v_output_video, session_task_state, device_id_state]
            )

        # ==========================================
        # TAB 4: 📁 歷史成果庫 (History Gallery) - Strictly per-device
        # ==========================================
        with gr.Tab("📁 歷史成果庫 (History Gallery)"):
            gr.Markdown("### 🗄️ 本裝置過去生成的影片記錄（僅顯示本裝置生成成果，嚴格隔離其他裝置）")
            with gr.Row():
                refresh_history_btn = gr.Button("🔄 刷新本裝置歷史列表", variant="secondary", scale=1)
                history_dropdown = gr.Dropdown(
                    choices=[],
                    label="選擇歷史任務 (依時間倒序排列)",
                    scale=4
                )
            with gr.Row():
                with gr.Column(scale=1):
                    gallery_video = gr.Video(label="歷史影片播放 (支援直接下載)", autoplay=False)
                with gr.Column(scale=1):
                    gallery_info = gr.Markdown("點選上方清單即可查看該次生成的詳細資訊與提示詞。")

            refresh_history_btn.click(
                fn=lambda dev_id: gr.update(choices=get_history_dropdown_choices(dev_id)),
                inputs=[device_id_state],
                outputs=[history_dropdown]
            )
            history_dropdown.change(
                on_select_history_item,
                inputs=[history_dropdown, device_id_state],
                outputs=[gallery_video, gallery_info]
            )

    # All outputs collected for full restore
    all_restored_outputs = [
        device_id_state,
        session_task_state,
        header_html,
        history_dropdown,
        # I2V
        i2v_first_frame, i2v_last_frame, i2v_prompt, i2v_res_preset,
        i2v_custom_w, i2v_custom_h, i2v_duration, i2v_seed,
        i2v_steps, i2v_denoise, i2v_fps, i2v_sampler, i2v_scheduler,
        i2v_status, i2v_output_video,
        # T2V
        t2v_prompt, t2v_res_preset,
        t2v_custom_w, t2v_custom_h, t2v_duration, t2v_seed,
        t2v_steps, t2v_denoise, t2v_fps, t2v_sampler, t2v_scheduler,
        t2v_status, t2v_output_video,
        # R2V
        r2v_prompt, r2v_video, r2v_audio,
        r2v_img1, r2v_img2, r2v_img3, r2v_img4,
        r2v_image_size, r2v_res_preset,
        r2v_custom_w, r2v_custom_h, r2v_duration, r2v_seed,
        r2v_steps, r2v_denoise, r2v_fps, r2v_sampler, r2v_scheduler,
        r2v_status, r2v_output_video,
    ]

    # Automatic page reload restoration (demo.load)
    demo.load(
        restore_device_state,
        inputs=[device_id_state, session_task_state],
        outputs=all_restored_outputs,
    )

    # Manual recover button triggers the exact same comprehensive restoration
    i2v_recover_btn.click(restore_device_state, inputs=[device_id_state, session_task_state], outputs=all_restored_outputs)
    t2v_recover_btn.click(restore_device_state, inputs=[device_id_state, session_task_state], outputs=all_restored_outputs)
    r2v_recover_btn.click(restore_device_state, inputs=[device_id_state, session_task_state], outputs=all_restored_outputs)

if __name__ == "__main__":
    print("=" * 60)
    print("MiniMax-H3 Gradio WebUI Starting...")
    print(f"Local Access: http://127.0.0.1:{WEBUI_PORT}")
    print(f"Mobile LAN Access: http://{lan_ip}:{WEBUI_PORT}")
    print(f"ComfyUI Backend: {COMFY_SERVER_URL}")
    print("=" * 60)
    demo.launch(
        server_name=WEBUI_HOST,
        server_port=WEBUI_PORT,
        share=False,
        theme=gr.themes.Default(primary_hue="blue"),
        css=CUSTOM_CSS,
    )

"""
MiniMax-H3 Mobile-Friendly Gradio WebUI with Persistent Session, Input Restoration,
and Strict Per-Device Isolation.
"""
import os
import time
import uuid
import random
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image
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
    ASPECT_RATIOS,
    ORIGINAL_RATIO_LABEL,
    I2V_ASPECT_RATIOS,
    T2V_ASPECT_RATIOS,
    MEGAPIXEL_CHOICES,
    DEFAULT_MEGAPIXELS,
    DEFAULT_MULTIPLE,
    QUALITY_CHOICES,
    DEFAULT_QUALITY_LEVEL,
    OUTPUT_DIR,
    quality_level_to_mp,
    calculate_dimensions,
    calculate_dimensions_from_image,
    calculate_dimensions_adaptive_ratio,
    find_nearest_aspect_ratio,
    normalize_quality_choice,
    normalize_aspect_ratio,
    normalize_sampler,
    normalize_scheduler,
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
    stop_comfyui_backend,
    upload_media_file,
)
from task_manager import task_manager
from logger import get_logger

logger = get_logger("App")

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

.id-badge {
    background-color: #334155;
    color: #38bdf8;
    padding: 3px 8px;
    border-radius: 6px;
    font-family: monospace;
    font-weight: 600;
}

/* Header ID Badge Copy Button */
.id-badge-btn {
    background-color: #334155;
    color: #38bdf8;
    border: 1px solid #475569;
    padding: 3px 10px;
    border-radius: 6px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    line-height: 1.4;
    transition: all 0.15s ease-in-out;
    user-select: none;
    -webkit-user-select: none;
    vertical-align: middle;
}

.id-badge-btn:hover {
    background-color: #475569;
    color: #7dd3fc;
    border-color: #38bdf8;
    box-shadow: 0 0 8px rgba(56, 189, 248, 0.25);
}

.id-badge-btn:active {
    transform: scale(0.96);
    background-color: #1e293b;
}

/* Header ID Edit Icon Button */
.id-edit-btn {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.85rem;
    line-height: 1.4;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease-in-out;
    user-select: none;
    -webkit-user-select: none;
    vertical-align: middle;
}

.id-edit-btn:hover {
    background-color: #475569;
    border-color: #38bdf8;
    box-shadow: 0 0 8px rgba(56, 189, 248, 0.25);
    transform: scale(1.05);
}

.id-edit-btn:active {
    transform: scale(0.95);
}

/* Hidden Trigger Button for clean layout */
.hidden-trigger-btn {
    position: fixed !important;
    left: -9999px !important;
    top: -9999px !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    opacity: 0 !important;
    pointer-events: none !important;
    overflow: hidden !important;
}

/* Mobile video player fix */
video {
    width: 100% !important;
    border-radius: 8px !important;
    background-color: #000;
}

/* Prevent virtual keyboard on dropdowns for mobile */
.gr-dropdown input {
    cursor: pointer !important;
    -webkit-user-select: none !important;
    user-select: none !important;
}

.header-row {
    align-items: center;
    margin-bottom: 4px;
}
"""

CUSTOM_HEAD_JS = """
<script>
window.copyDeviceId = function(btn, text) {
    function showSuccess() {
        var orig = btn.innerHTML;
        btn.innerHTML = '✅ 已複製!';
        btn.style.borderColor = '#22c55e';
        btn.style.color = '#86efac';
        setTimeout(function() {
            btn.innerHTML = orig;
            btn.style.borderColor = '';
            btn.style.color = '';
        }, 1500);
    }
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(showSuccess, function() {
            window.fallbackCopy(text, showSuccess);
        });
    } else {
        window.fallbackCopy(text, showSuccess);
    }
};

window.fallbackCopy = function(text, cb) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '-9999px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
        var successful = document.execCommand('copy');
        if (successful) {
            cb();
        } else {
            prompt('請手動選取並複製代碼：', text);
        }
    } catch (err) {
        prompt('請手動選取並複製代碼：', text);
    }
    document.body.removeChild(ta);
};

window.triggerEditId = function() {
    var triggerBtn = document.getElementById('edit-id-trigger-btn');
    if (triggerBtn) {
        var btn = triggerBtn.tagName === 'BUTTON' ? triggerBtn : triggerBtn.querySelector('button');
        if (btn) {
            btn.click();
        } else {
            triggerBtn.click();
        }
    }
};
</script>
"""

lan_ip = get_lan_ip()
server_ok, server_status_msg = check_server(COMFY_SERVER_URL)


def build_header_html(device_id=None):
    if device_id:
        short_hash = device_id.split("_")[-1][:6]
        dev_str = (
            f' | <span style="display: inline-flex; align-items: center; gap: 4px; vertical-align: middle;">'
            f'<button type="button" class="id-badge-btn" onclick="copyDeviceId(this, \'{short_hash}\')" title="點擊複製裝置代碼 ({short_hash})">📋 ID:{short_hash}</button>'
            f'<button type="button" class="id-edit-btn" onclick="triggerEditId()" title="手動指定裝置代碼">✏️</button>'
            f'</span>'
        )
    else:
        dev_str = ""
    return f"""
    <div class="header-card">
        <h2 style="margin: 0 0 8px 0; font-size: 1.5rem;">🎬 MiniMax-H3 影片生成系統</h2>
        <div style="font-size: 0.95rem; opacity: 0.9; line-height: 1.6;">
            📱 <b>手機內網連線網址：</b> <span class="ip-badge">http://{lan_ip}:{WEBUI_PORT}</span>
            {dev_str}
        </div>
    </div>
    """


def build_progress_html(task_or_msg) -> str:
    """
    Renders a yellow progress bar on a white background with direct step percentage.
    Calculates percentage strictly based on sampling steps per user specification.
    Displays clear phase status descriptions above the progress bar during preprocessing,
    sampling, postprocessing, and completion.
    """
    if isinstance(task_or_msg, str):
        msg = task_or_msg or "🟢 準備就緒"
        pct = 100 if "完成" in msg or "成功" in msg else 0
    elif task_or_msg is None:
        msg = "🟢 準備就緒"
        pct = 0
    else:
        task = task_or_msg
        msg = getattr(task, "message", "") or "🟢 準備就緒"
        status = getattr(task, "status", "")
        stage = getattr(task, "stage", "")
        step = getattr(task, "step", 0)
        total_steps = getattr(task, "total_steps", 0)

        if status == "completed":
            pct = 100
        elif stage == "postprocessing" or (total_steps > 0 and step >= total_steps):
            pct = 100
        elif total_steps > 0:
            pct = max(0, min(100, int(round((step / total_steps) * 100))))
        else:
            pct = 0

    return f"""
    <div style="width: 100%; margin-bottom: 8px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; font-size: 0.9rem; font-weight: 500; color: #334155;">
            <div style="flex: 1; min-width: 0; min-height: 2.7em; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; word-break: break-word; padding-right: 8px;">{msg}</div>
            <div style="flex-shrink: 0; font-weight: 700; color: #b45309; font-size: 0.95rem; line-height: 1.35;">{pct}%</div>
        </div>
        <div style="width: 100%; height: 26px; background-color: #ffffff; border: 1.5px solid #cbd5e1; border-radius: 6px; overflow: hidden; position: relative; box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);">
            <div style="width: {pct}%; height: 100%; background: linear-gradient(90deg, #fde047 0%, #eab308 100%); transition: width 0.3s ease;"></div>
            <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: 700; color: #0f172a; text-shadow: 0 0 2px rgba(255,255,255,0.7);">
                {pct}%
            </div>
        </div>
    </div>
    """


def on_resolution_change(ar, quality_str, img_path=None):
    """Calculates resolution label when aspect ratio, quality level, or image changes."""
    quality_str = normalize_quality_choice(quality_str)

    if ar == ORIGINAL_RATIO_LABEL or "原圖" in str(ar) or "自動" in str(ar):
        if img_path and os.path.exists(img_path):
            try:
                with Image.open(img_path) as im:
                    orig_w, orig_h = im.size
                w, h = calculate_dimensions_adaptive_ratio(orig_w, orig_h, quality_str, multiple=DEFAULT_MULTIPLE)
                actual_mp = round((w * h) / 1_000_000, 2)
                r_orig = orig_w / orig_h
                r_calc = w / h
                diff_pct = abs(r_calc - r_orig) / r_orig * 100
                return f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP) ｜ 💡 *精準對齊原圖 ({orig_w}x{orig_h})，拉伸誤差：{diff_pct:.2f}%*"
            except Exception:
                pass
        w, h = calculate_dimensions("16:9 (橫向風景)", quality_str, multiple=DEFAULT_MULTIPLE)
        actual_mp = round((w * h) / 1_000_000, 2)
        return f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP) ｜ 💡 *尚未上傳圖片，上傳後將自動對齊原圖比例*"

    ar = normalize_aspect_ratio(ar, allow_original=False)
    w, h = calculate_dimensions(ar, quality_str, multiple=DEFAULT_MULTIPLE)
    actual_mp = round((w * h) / 1_000_000, 2)
    return f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP)"


def on_first_frame_change(img_path, current_quality_str):
    """Detects uploaded image dimensions and automatically aligns to distortion-free original aspect ratio."""
    if not img_path or not os.path.exists(img_path):
        return gr.update(), "📐 **輸出解析度**：尚未上傳圖片", ""
    try:
        current_quality_str = normalize_quality_choice(current_quality_str)
        with Image.open(img_path) as im:
            orig_w, orig_h = im.size
        r_orig = orig_w / orig_h
        w, h = calculate_dimensions_adaptive_ratio(orig_w, orig_h, current_quality_str, multiple=DEFAULT_MULTIPLE)
        actual_mp = round((w * h) / 1_000_000, 2)
        r_calc = w / h
        diff_pct = abs(r_calc - r_orig) / r_orig * 100

        info_text = f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP) ｜ 💡 *精準對齊原圖 ({orig_w}x{orig_h})，拉伸誤差：{diff_pct:.2f}%*"
        badge_text = f"💡 *偵測到原始尺寸：`{orig_w} x {orig_h}` (比例 {r_orig:.2f})，已自動對齊無畸變輸出尺寸，拉伸誤差：{diff_pct:.2f}%*"
        return gr.update(value=ORIGINAL_RATIO_LABEL), info_text, badge_text
    except Exception as e:
        return gr.update(), gr.update(), f"⚠️ 圖片解析度偵測失敗: {str(e)}"


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
        return [("— 暫無歷史紀錄 —", "")]
    completed = task_manager.get_completed_tasks_for_device(device_id)
    if not completed:
        return [("— 暫無歷史紀錄 —", "")]
    choices = []
    for t in completed:
        t_str = time.strftime("%m/%d %H:%M", time.localtime(t.created_at))
        short_prompt = (t.prompt[:30] + "...") if len(t.prompt) > 30 else t.prompt
        label = f"[{t.task_type}] {t_str} | {short_prompt}"
        choices.append((label, t.task_id))
    return choices


def on_select_history_item(selected_task_id, device_id):
    if not selected_task_id:
        return None, "請選擇上方任務"
    task = task_manager.get_task(selected_task_id, device_id=device_id)
    if not task or not task.video_path or not os.path.exists(task.video_path):
        return None, "⚠️ 找不到該影片檔案"
    
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task.created_at))
    info_md = f"""
    ### 📜 任務詳細資料
    * **任務類型**：`{task.task_type}`
    * **建立時間**：{t_str}
    * **生成耗時**：{task.elapsed} 秒
    * **檔案名稱**：`{os.path.basename(task.video_path)}`
    * **提示詞**：
    ```text
    {task.prompt}
    ```
    """
    return task.video_path, info_md


# --- Generation Handlers with Input Archiving & Device Isolation ---

_device_last_reported_completed: Dict[str, str] = {}
_device_last_status_html: Dict[str, str] = {}


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
    fps,
    current_session_task,
    device_id,
    custom_w=None,
    custom_h=None,
    unet_name=DEFAULT_UNET,
    clip_name=DEFAULT_CLIP,
    video_vae=DEFAULT_VIDEO_VAE,
    audio_vae=DEFAULT_AUDIO_VAE,
):
    if not device_id:
        device_id = f"dev_{uuid.uuid4().hex[:6]}"

    if not first_frame:
        yield build_progress_html("❌ 請上傳首幀圖片"), None, current_session_task, device_id
        return

    if not prompt or not prompt.strip():
        yield build_progress_html("❌ 請輸入提示詞"), None, current_session_task, device_id
        return

    # Task 1: If there is an active running/queued task for this device, interrupt it immediately!
    interrupted_ids = task_manager.interrupt_device_tasks(device_id=device_id)
    if interrupted_ids:
        logger.info("[I2V] Preempted previous active task(s) for device '%s': %s", device_id, interrupted_ids)

    aspect_ratio = normalize_aspect_ratio(aspect_ratio)
    quality_level = normalize_quality_choice(quality_level)
    sampler = normalize_sampler(sampler)
    scheduler = normalize_scheduler(scheduler)

    # [I2V Dimension Calculation]
    w, h = calculate_dimensions(aspect_ratio, quality_level, multiple=DEFAULT_MULTIPLE, image_input=first_frame)

    logger.info("[I2V] Request from device '%s': size=%dx%d, steps=%s, seed=%s, duration=%ss, prompt='%s'",
                device_id, w, h, steps, seed, duration, prompt[:50])
    yield build_progress_html("⚡ 前處理中：正在上傳圖片..."), None, current_session_task, device_id
    try:
        first_frame_fn = upload_media_file(first_frame)
        last_frame_fn = upload_media_file(last_frame) if last_frame else None
    except Exception as e:
        yield build_progress_html(f"❌ 上傳圖片失敗: 檢查後端是否已啟動({str(e)}"), None, current_session_task, device_id
        return

    yield build_progress_html("⚡ 前處理中：正在編譯工作流..."), None, current_session_task, device_id

    # Task 4: Workflow strictly uses server-side configured models (DEFAULT_UNET, DEFAULT_CLIP, etc.)
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
        unet_name=DEFAULT_UNET,
        clip_name=DEFAULT_CLIP,
        video_vae_name=DEFAULT_VIDEO_VAE,
        audio_vae_name=DEFAULT_AUDIO_VAE,
    )

    # Save full parameters for complete state restoration
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
        "fps": fps,
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
            if t.status == "completed":
                _device_last_reported_completed[device_id] = t.task_id
            break
        time.sleep(0.5)


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
):
    if not device_id:
        device_id = f"dev_{uuid.uuid4().hex[:6]}"

    if not prompt or not prompt.strip():
        yield build_progress_html("❌ 請輸入提示詞"), None, current_session_task, device_id
        return

    # Task 1: If there is an active running/queued task for this device, interrupt it immediately!
    interrupted_ids = task_manager.interrupt_device_tasks(device_id=device_id)
    if interrupted_ids:
        logger.info("[T2V] Preempted previous active task(s) for device '%s': %s", device_id, interrupted_ids)

    aspect_ratio = normalize_aspect_ratio(aspect_ratio)
    quality_level = normalize_quality_choice(quality_level)
    sampler = normalize_sampler(sampler)
    scheduler = normalize_scheduler(scheduler)

    # Task 3 & 6: Width and height for T2V are calculated from Aspect Ratio and Quality Level (MP)
    w, h = calculate_dimensions(aspect_ratio, quality_level, multiple=DEFAULT_MULTIPLE)

    yield build_progress_html("⚡ 前處理中：正在準備生成任務..."), None, current_session_task, device_id

    logger.info("[T2V] Request from device '%s': size=%dx%d, steps=%s, seed=%s, duration=%ss, prompt='%s'",
                device_id, w, h, steps, seed, duration, prompt[:50])

    # Task 4: Workflow strictly uses server-side configured models
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
            if t.status == "completed":
                _device_last_reported_completed[device_id] = t.task_id
            break
        time.sleep(0.5)


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
):
    if not device_id:
        device_id = f"dev_{uuid.uuid4().hex[:6]}"

    if not prompt or not prompt.strip():
        yield build_progress_html("❌ 請輸入提示詞"), None, current_session_task, device_id
        return

    # Task 1: If there is an active running/queued task for this device, interrupt it immediately!
    interrupted_ids = task_manager.interrupt_device_tasks(device_id=device_id)
    if interrupted_ids:
        logger.info("[R2V] Preempted previous active task(s) for device '%s': %s", device_id, interrupted_ids)

    aspect_ratio = normalize_aspect_ratio(aspect_ratio)
    quality_level = normalize_quality_choice(quality_level)
    sampler = normalize_sampler(sampler)
    scheduler = normalize_scheduler(scheduler)

    # [R2V Dimension Calculation]
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

    yield build_progress_html("⚡ 前處理中：正在編譯工作流..."), None, current_session_task, device_id

    # Task 4: Workflow strictly uses server-side configured models
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
            if t.status == "completed":
                _device_last_reported_completed[device_id] = t.task_id
            break
        time.sleep(0.5)


# --- Full State Restoration Callback for demo.load and Recover Buttons ---

def restore_device_state(stored_device_id, stored_task_id):
    """
    Called on page load (demo.load) or recover button click.
    Restores all inputs, parameters, and generated video for THIS specific device only.
    """
    if not stored_device_id:
        stored_device_id = f"dev_{uuid.uuid4().hex[:6]}"

    # Fetch task for THIS device only (No cross-device leakage!)
    task = task_manager.get_task(stored_task_id, device_id=stored_device_id) or task_manager.get_latest_task_for_device(stored_device_id)
    logger.info("[Session] Device connected/restoring: %s (Active task: %s)", stored_device_id, task.task_id if task else "None")

    # Defaults (Leave untouched if no task) - I2V: 14, T2V: 12, R2V: 19
    i2v_updates = [gr.update()] * 14
    t2v_updates = [gr.update()] * 12
    r2v_updates = [gr.update()] * 19
    history_choices = get_history_dropdown_choices(stored_device_id)

    if task and task.params:
        p = task.params
        if task.task_type == "I2V":
            i2v_updates = [
                gr.update(value=p.get("first_frame")),
                gr.update(value=p.get("last_frame")),
                gr.update(value=p.get("prompt", task.prompt)),
                gr.update(value=normalize_aspect_ratio(p.get("aspect_ratio"))),
                gr.update(value=normalize_quality_choice(p.get("quality_level"))),
                gr.update(value=p.get("duration", 2.0)),
                gr.update(value=p.get("seed", 1)),
                gr.update(value=p.get("steps", 20)),
                gr.update(value=p.get("denoise", 1.0)),
                gr.update(value=p.get("fps", 24)),
                gr.update(value=normalize_sampler(p.get("sampler"))),
                gr.update(value=normalize_scheduler(p.get("scheduler"))),
                gr.update(value=build_progress_html(task)),
                gr.update(value=task.video_path if task.video_path and os.path.exists(task.video_path) else None),
            ]
        elif task.task_type == "T2V":
            t2v_updates = [
                gr.update(value=p.get("prompt", task.prompt)),
                gr.update(value=normalize_aspect_ratio(p.get("aspect_ratio"))),
                gr.update(value=normalize_quality_choice(p.get("quality_level"))),
                gr.update(value=p.get("duration", 2.0)),
                gr.update(value=p.get("seed", 1)),
                gr.update(value=p.get("steps", 20)),
                gr.update(value=p.get("denoise", 1.0)),
                gr.update(value=p.get("fps", 24)),
                gr.update(value=normalize_sampler(p.get("sampler"))),
                gr.update(value=normalize_scheduler(p.get("scheduler"))),
                gr.update(value=build_progress_html(task)),
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
                gr.update(value=normalize_aspect_ratio(p.get("aspect_ratio"))),
                gr.update(value=normalize_quality_choice(p.get("quality_level"))),
                gr.update(value=p.get("duration", 3.0)),
                gr.update(value=p.get("seed", 1)),
                gr.update(value=p.get("steps", 20)),
                gr.update(value=p.get("denoise", 1.0)),
                gr.update(value=p.get("fps", 24)),
                gr.update(value=normalize_sampler(p.get("sampler"))),
                gr.update(value=normalize_scheduler(p.get("scheduler"))),
                gr.update(value=build_progress_html(task)),
                gr.update(value=task.video_path if task.video_path and os.path.exists(task.video_path) else None),
            ]

    if task and task.status == "completed" and task.video_path and os.path.exists(task.video_path):
        _device_last_reported_completed[stored_device_id] = task.task_id
    elif task and task.status in ("running", "queued"):
        _device_last_reported_completed.pop(stored_device_id, None)

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


def switch_manual_device_id(custom_id, current_device_id, session_task_id):
    """Allows user to manually switch to a remembered device ID without exposing other IDs."""
    val = (custom_id or "").strip()
    if not val:
        return (gr.update(visible=False), *restore_device_state(current_device_id, session_task_id))

    if not val.startswith("dev_"):
        val = f"dev_{val}"

    logger.info("[Session] Device ID manual switch: '%s' -> '%s'", current_device_id, val)
    restored = restore_device_state(val, None)
    return (gr.update(visible=False), *restored)


def poll_active_task_progress(stored_device_id, stored_task_id):
    """
    Polled periodically by task_poll_timer (Spec Task 2).
    Automatically detects background task completion or progress for reconnected sessions,
    and updates progress bar, video player, and history dropdown without requiring manual refresh.
    """
    if not stored_device_id:
        return (
            gr.update(),
            gr.update(), gr.update(),
            gr.update(), gr.update(),
            gr.update(), gr.update(),
            gr.update(),
        )

    task = task_manager.get_task(stored_task_id, device_id=stored_device_id)
    if not task:
        task = task_manager.get_latest_task_for_device(stored_device_id)

    if not task:
        return (
            gr.update(),
            gr.update(), gr.update(),
            gr.update(), gr.update(),
            gr.update(), gr.update(),
            gr.update(),
        )

    # 1. If completed, failed, or interrupted
    if task.status in ("completed", "failed", "interrupted"):
        # Check if already pushed to client
        if _device_last_reported_completed.get(stored_device_id) == task.task_id:
            return (
                gr.update(),
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                gr.update(),
            )

        # Mark as reported so we don't reload player continuously
        _device_last_reported_completed[stored_device_id] = task.task_id
        history_choices = get_history_dropdown_choices(stored_device_id)
        progress_html = build_progress_html(task)
        video_val = task.video_path if (task.status == "completed" and task.video_path and os.path.exists(task.video_path)) else gr.update()

        if task.task_type == "I2V":
            return (
                task.task_id,
                progress_html, video_val,
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                gr.update(choices=history_choices),
            )
        elif task.task_type == "T2V":
            return (
                task.task_id,
                gr.update(), gr.update(),
                progress_html, video_val,
                gr.update(), gr.update(),
                gr.update(choices=history_choices),
            )
        elif task.task_type == "R2V":
            return (
                task.task_id,
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                progress_html, video_val,
                gr.update(choices=history_choices),
            )

    # 2. Task is actively queued or running
    if task.status in ("queued", "running"):
        _device_last_reported_completed.pop(stored_device_id, None)
        progress_html = build_progress_html(task)
        last_html = _device_last_status_html.get(stored_device_id)
        if last_html == progress_html:
            return (
                gr.update(),
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                gr.update(),
            )
        _device_last_status_html[stored_device_id] = progress_html

        if task.task_type == "I2V":
            return (
                task.task_id,
                progress_html, gr.update(),
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                gr.update(),
            )
        elif task.task_type == "T2V":
            return (
                task.task_id,
                gr.update(), gr.update(),
                progress_html, gr.update(),
                gr.update(), gr.update(),
                gr.update(),
            )
        elif task.task_type == "R2V":
            return (
                task.task_id,
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                progress_html, gr.update(),
                gr.update(),
            )

    return (
        gr.update(),
        gr.update(), gr.update(),
        gr.update(), gr.update(),
        gr.update(), gr.update(),
        gr.update(),
    )


# --- UI Definition ---

with gr.Blocks(title="MiniMax-H3 AI Video WebUI") as demo:
    # Strictly isolated persistent states per browser/device LocalStorage
    DEVICE_STORAGE_SECRET = "minimax_h3_device_secret_2026"
    device_id_state = gr.BrowserState(
        default_value="",
        storage_key="minimax_device_id",
        secret=DEVICE_STORAGE_SECRET,
    )
    session_task_state = gr.BrowserState(
        default_value="",
        storage_key="minimax_active_task_id",
        secret=DEVICE_STORAGE_SECRET,
    )

    header_html = gr.HTML(build_header_html())
    edit_id_btn = gr.Button("✏️", elem_id="edit-id-trigger-btn", elem_classes=["hidden-trigger-btn"])

    with gr.Row(visible=False) as edit_id_row:
        manual_id_input = gr.Textbox(
            label="手動指定裝置 ID (可找回該裝置歷史記錄)",
            placeholder="請輸入 6 位數 ID (例如 71c8f5) 或完整 ID...",
            scale=5,
        )
        save_id_btn = gr.Button("確認切換", variant="primary", scale=1)
        cancel_id_btn = gr.Button("取消", variant="secondary", scale=1)

    # ComfyUI Backend Control Toolbar (Spec 6)
    with gr.Row():
        start_backend_btn = gr.Button("⚡ 檢查後端模型狀態...", variant="secondary", scale=9)
        stop_backend_btn = gr.Button("🛑", variant="stop", scale=1, min_width=50)

    backend_status_msg = gr.Markdown("")

    # Auto poll backend status every 0.5s to dynamically color and label the button
    auto_timer = gr.Timer(value=0.5)
    _is_backend_starting = False

    def poll_backend_status():
        if _is_backend_starting:
            return gr.update(value="🟡 正在啟動後端模型...", variant="secondary")
        ok, _ = check_server(COMFY_SERVER_URL)
        if ok:
            return gr.update(value="🟢 後端模型運作中", variant="primary")
        else:
            return gr.update(value="⚡ 啟動後端模型", variant="secondary")

    auto_timer.tick(poll_backend_status, outputs=[start_backend_btn])

    def on_start_backend():
        global _is_backend_starting
        ok, _ = check_server(COMFY_SERVER_URL)
        if ok:
            yield gr.update(value="🟢 後端模型運作中", variant="primary"), "🟢 後端模型已經在運作中，無須重複啟動"
            return

        _is_backend_starting = True
        yield gr.update(value="🟡 正在啟動後端模型...", variant="secondary"), "🟡 正在啟動後端模型，請稍候..."

        try:
            ok, msg = start_comfyui_backend(COMFY_SERVER_URL)
        finally:
            _is_backend_starting = False

        btn_update = poll_backend_status()
        yield btn_update, f"{msg}"

    def on_stop_backend():
        ok, msg = stop_comfyui_backend(COMFY_SERVER_URL)
        btn_update = poll_backend_status()
        return btn_update, f"{msg}"

    start_backend_btn.click(on_start_backend, outputs=[start_backend_btn, backend_status_msg])
    stop_backend_btn.click(on_stop_backend, outputs=[start_backend_btn, backend_status_msg])

    with gr.Tabs() as tabs:
        # ==========================================
        # TAB 1: 圖生影片 (I2V)
        # ==========================================
        with gr.Tab("🖼️ 圖生影片 (I2V)"):
            with gr.Row():
                with gr.Column(scale=1):
                    with gr.Row():
                        i2v_first_frame = gr.Image(type="filepath", label="首幀圖片", height=240)
                        i2v_last_frame = gr.Image(type="filepath", label="尾幀圖片 (選填)", height=240)

                    i2v_img_badge = gr.Markdown("")

                    i2v_prompt = gr.Textbox(
                        label="提示詞",
                        placeholder="描述畫面的動態、角色動作、鏡頭運動與音效（支援中英文）...",
                        lines=5,
                        value=""
                    )

                    # Row 1: Aspect Ratio, Quality Level (1~10)
                    with gr.Row():
                        i2v_aspect_ratio = gr.Dropdown(
                            choices=I2V_ASPECT_RATIOS,
                            value=ORIGINAL_RATIO_LABEL,
                            label="長寬比",
                            scale=3,
                            filterable=False,
                        )
                        i2v_quality_level = gr.Dropdown(
                            choices=QUALITY_CHOICES,
                            value=DEFAULT_QUALITY_LEVEL,
                            label="畫質等級",
                            scale=3,
                            filterable=False,
                        )
                        i2v_res_info = gr.Markdown("📐 **輸出解析度**：`1344 x 768` (~1.03 MP) ｜ 💡 *尚未上傳圖片，上傳後將自動對齊原圖比例*", scale=3)

                    # Row 2: Duration, Seed, Random (Spec 4)
                    with gr.Row():
                        i2v_duration = gr.Slider(
                            minimum=1.0, maximum=15.0, value=2.0, step=0.5,
                            label="影片時長 (秒)", scale=3
                        )
                        i2v_seed = gr.Number(value=1, precision=0, label="隨機種子", scale=2)
                        i2v_rand_btn = gr.Button("🎲 隨機", scale=1)

                    with gr.Accordion("⚙️ 進階參數", open=False):
                        with gr.Row():
                            i2v_steps = gr.Slider(minimum=1, maximum=50, value=20, step=1, label="取樣步數")
                            i2v_denoise = gr.Slider(minimum=0.1, maximum=1.0, value=1.0, step=0.05, label="去噪強度")
                            i2v_fps = gr.Slider(minimum=12, maximum=60, value=24, step=1, label="影格率 (FPS)")
                        with gr.Row():
                            i2v_sampler = gr.Dropdown(choices=SAMPLER_CHOICES, value="res_multistep", label="取樣器", filterable=False)
                            i2v_scheduler = gr.Dropdown(choices=SCHEDULER_CHOICES, value="simple", label="調度器", filterable=False)

                    i2v_btn = gr.Button("🚀 開始生成影片", variant="primary", elem_classes=["primary-btn"])

                with gr.Column(scale=1):
                    i2v_status = gr.HTML(build_progress_html("🟢 準備就緒"))
                    i2v_recover_btn = gr.Button("🔄 恢復上次輸入與成果", variant="secondary")
                    i2v_output_video = gr.Video(label="生成影片", autoplay=True, interactive=False)

            # Auto resolution update listeners
            for comp in [i2v_aspect_ratio, i2v_quality_level]:
                comp.change(on_resolution_change, inputs=[i2v_aspect_ratio, i2v_quality_level, i2v_first_frame], outputs=[i2v_res_info])

            # Auto image resolution detection listener (Spec 3)
            i2v_first_frame.change(on_first_frame_change, inputs=[i2v_first_frame, i2v_quality_level], outputs=[i2v_aspect_ratio, i2v_res_info, i2v_img_badge])

            i2v_rand_btn.click(generate_random_seed, outputs=[i2v_seed])
            i2v_btn.click(
                handle_i2v_generate,
                inputs=[
                    i2v_first_frame, i2v_last_frame, i2v_prompt,
                    i2v_aspect_ratio, i2v_quality_level,
                    i2v_duration, i2v_seed,
                    i2v_steps, i2v_denoise, i2v_sampler, i2v_scheduler, i2v_fps,
                    session_task_state, device_id_state
                ],
                outputs=[i2v_status, i2v_output_video, session_task_state, device_id_state]
            )

        # ==========================================
        # TAB 2: 文生影片 (T2V)
        # ==========================================
        with gr.Tab("✍️ 文生影片 (T2V)"):
            with gr.Row():
                with gr.Column(scale=1):
                    t2v_prompt = gr.Textbox(
                        label="提示詞",
                        placeholder="描述想生成的場景、運鏡、角色動態、氛圍與背景音樂/音效...",
                        lines=6,
                        value=""
                    )

                    # Row 1: Aspect Ratio, Quality Level (1~10)
                    with gr.Row():
                        t2v_aspect_ratio = gr.Dropdown(
                            choices=T2V_ASPECT_RATIOS,
                            value="16:9 (橫向風景)",
                            label="長寬比",
                            scale=3,
                            filterable=False,
                        )
                        t2v_quality_level = gr.Dropdown(
                            choices=QUALITY_CHOICES,
                            value=DEFAULT_QUALITY_LEVEL,
                            label="畫質等級",
                            scale=3,
                            filterable=False,
                        )
                        t2v_res_info = gr.Markdown("📐 **輸出解析度**：`1344 x 768` (~1.03 MP)", scale=3)

                    # Row 2: Duration, Seed, Random (Spec 4)
                    with gr.Row():
                        t2v_duration = gr.Slider(
                            minimum=1.0, maximum=15.0, value=2.0, step=0.5,
                            label="影片時長 (秒)", scale=3
                        )
                        t2v_seed = gr.Number(value=1, precision=0, label="隨機種子", scale=2)
                        t2v_rand_btn = gr.Button("🎲 隨機", scale=1)

                    with gr.Accordion("⚙️ 進階參數", open=False):
                        with gr.Row():
                            t2v_steps = gr.Slider(minimum=1, maximum=50, value=20, step=1, label="取樣步數")
                            t2v_denoise = gr.Slider(minimum=0.1, maximum=1.0, value=1.0, step=0.05, label="去噪強度")
                            t2v_fps = gr.Slider(minimum=12, maximum=60, value=24, step=1, label="影格率 (FPS)")
                        with gr.Row():
                            t2v_sampler = gr.Dropdown(choices=SAMPLER_CHOICES, value="res_multistep", label="取樣器", filterable=False)
                            t2v_scheduler = gr.Dropdown(choices=SCHEDULER_CHOICES, value="simple", label="調度器", filterable=False)

                    t2v_btn = gr.Button("🚀 開始生成影片", variant="primary", elem_classes=["primary-btn"])

                with gr.Column(scale=1):
                    t2v_status = gr.HTML(build_progress_html("🟢 準備就緒"))
                    t2v_recover_btn = gr.Button("🔄 恢復上次輸入與成果", variant="secondary")
                    t2v_output_video = gr.Video(label="生成影片", autoplay=True, interactive=False)

            # Auto resolution update listeners
            for comp in [t2v_aspect_ratio, t2v_quality_level]:
                comp.change(on_resolution_change, inputs=[t2v_aspect_ratio, t2v_quality_level], outputs=[t2v_res_info])

            t2v_rand_btn.click(generate_random_seed, outputs=[t2v_seed])
            t2v_btn.click(
                handle_t2v_generate,
                inputs=[
                    t2v_prompt,
                    t2v_aspect_ratio, t2v_quality_level,
                    t2v_duration, t2v_seed,
                    t2v_steps, t2v_denoise, t2v_sampler, t2v_scheduler, t2v_fps,
                    session_task_state, device_id_state
                ],
                outputs=[t2v_status, t2v_output_video, session_task_state, device_id_state]
            )

        # ==========================================
        # TAB 3: 參考生影片 (R2V)
        # ==========================================
        with gr.Tab("🎬 參考生影片 (R2V)"):
            with gr.Row():
                with gr.Column(scale=1):
                    r2v_prompt = gr.Textbox(
                        label="提示詞",
                        placeholder="可使用 <Picture 1>, <Picture 2>, <Video 1>, <Audio 1> 關聯參考素材。例如：'根據 <Picture 1> 的角色特徵，參考 <Video 1> 的動作姿勢，生成動作影片...'",
                        lines=5,
                        value=""
                    )

                    with gr.Row():
                        r2v_video = gr.Video(label="參考影片 (<Video 1>)", height=220)
                        r2v_audio = gr.Audio(label="參考音訊 (<Audio 1> 選填)", type="filepath")

                    with gr.Accordion("🖼️ 參考圖片 (最多 4 張)", open=False):
                        with gr.Row():
                            r2v_img1 = gr.Image(type="filepath", label="參考圖 1 (<Picture 1>)", height=180)
                            r2v_img2 = gr.Image(type="filepath", label="參考圖 2 (<Picture 2>)", height=180)
                        with gr.Row():
                            r2v_img3 = gr.Image(type="filepath", label="參考圖 3 (<Picture 3>)", height=180)
                            r2v_img4 = gr.Image(type="filepath", label="參考圖 4 (<Picture 4>)", height=180)

                    r2v_img_badge = gr.Markdown("")

                    with gr.Row():
                        r2v_image_size = gr.Radio(
                            choices=["match", "max"],
                            value="match",
                            label="參考圖尺寸模式",
                            info="match: 匹配輸出畫幅 | max: 高解析度"
                        )

                    # Row 1: Aspect Ratio, Quality Level (1~10)
                    with gr.Row():
                        r2v_aspect_ratio = gr.Dropdown(
                            choices=I2V_ASPECT_RATIOS,
                            value=ORIGINAL_RATIO_LABEL,
                            label="長寬比",
                            scale=3,
                            filterable=False,
                        )
                        r2v_quality_level = gr.Dropdown(
                            choices=QUALITY_CHOICES,
                            value=DEFAULT_QUALITY_LEVEL,
                            label="畫質等級",
                            scale=3,
                            filterable=False,
                        )
                        r2v_res_info = gr.Markdown("📐 **輸出解析度**：`1344 x 768` (~1.03 MP) ｜ 💡 *尚未上傳圖片，上傳後將自動對齊原圖比例*", scale=3)

                    # Row 2: Duration, Seed, Random (Spec 4)
                    with gr.Row():
                        r2v_duration = gr.Slider(
                            minimum=1.0, maximum=18.0, value=3.0, step=0.5,
                            label="影片時長 (秒)", scale=3
                        )
                        r2v_seed = gr.Number(value=1, precision=0, label="隨機種子", scale=2)
                        r2v_rand_btn = gr.Button("🎲 隨機", scale=1)

                    with gr.Accordion("⚙️ 進階參數", open=False):
                        with gr.Row():
                            r2v_steps = gr.Slider(minimum=1, maximum=50, value=20, step=1, label="取樣步數")
                            r2v_denoise = gr.Slider(minimum=0.1, maximum=1.0, value=1.0, step=0.05, label="去噪強度")
                            r2v_fps = gr.Slider(minimum=12, maximum=60, value=24, step=1, label="影格率 (FPS)")
                        with gr.Row():
                            r2v_sampler = gr.Dropdown(choices=SAMPLER_CHOICES, value="res_multistep", label="取樣器", filterable=False)
                            r2v_scheduler = gr.Dropdown(choices=SCHEDULER_CHOICES, value="simple", label="調度器", filterable=False)

                    r2v_btn = gr.Button("🚀 開始生成影片", variant="primary", elem_classes=["primary-btn"])

                with gr.Column(scale=1):
                    r2v_status = gr.HTML(build_progress_html("🟢 準備就緒"))
                    r2v_recover_btn = gr.Button("🔄 恢復上次輸入與成果", variant="secondary")
                    r2v_output_video = gr.Video(label="生成影片", autoplay=True, interactive=False)

            # Auto resolution update listeners
            for comp in [r2v_aspect_ratio, r2v_quality_level]:
                comp.change(on_resolution_change, inputs=[r2v_aspect_ratio, r2v_quality_level, r2v_img1], outputs=[r2v_res_info])

            # Auto image resolution detection listener for R2V reference image (Spec 3)
            r2v_img1.change(on_first_frame_change, inputs=[r2v_img1, r2v_quality_level], outputs=[r2v_aspect_ratio, r2v_res_info, r2v_img_badge])

            r2v_rand_btn.click(generate_random_seed, outputs=[r2v_seed])
            r2v_btn.click(
                handle_r2v_generate,
                inputs=[
                    r2v_prompt, r2v_img1, r2v_img2, r2v_img3, r2v_img4,
                    r2v_video, r2v_audio, r2v_image_size,
                    r2v_aspect_ratio, r2v_quality_level,
                    r2v_duration, r2v_seed,
                    r2v_steps, r2v_denoise, r2v_sampler, r2v_scheduler, r2v_fps,
                    session_task_state, device_id_state
                ],
                outputs=[r2v_status, r2v_output_video, session_task_state, device_id_state]
            )

        # ==========================================
        # TAB 4: 📁 歷史成果庫
        # ==========================================
        with gr.Tab("📁 歷史成果庫"):
            gr.Markdown("### 🗄️ 歷史生成記錄")
            with gr.Row():
                refresh_history_btn = gr.Button("🔄 重新整理", variant="secondary", scale=1)
                # Spec 5: Strictly a dropdown without combobox / textbox degradation
                history_dropdown = gr.Dropdown(
                    choices=[("— 暫無歷史紀錄 —", "")],
                    value="",
                    label="選擇歷史任務",
                    allow_custom_value=False,
                    filterable=False,
                    interactive=True,
                    scale=4
                )
            with gr.Row():
                with gr.Column(scale=1):
                    gallery_video = gr.Video(label="歷史影片", autoplay=False)
                with gr.Column(scale=1):
                    gallery_info = gr.Markdown("選擇上方任務查看詳細資訊與播放。")

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

    # All outputs collected for full restore (49 components exact match)
    all_restored_outputs = [
        device_id_state,
        session_task_state,
        header_html,
        history_dropdown,
        # I2V (14 components)
        i2v_first_frame, i2v_last_frame, i2v_prompt,
        i2v_aspect_ratio, i2v_quality_level,
        i2v_duration, i2v_seed,
        i2v_steps, i2v_denoise, i2v_fps, i2v_sampler, i2v_scheduler,
        i2v_status, i2v_output_video,
        # T2V (12 components)
        t2v_prompt,
        t2v_aspect_ratio, t2v_quality_level,
        t2v_duration, t2v_seed,
        t2v_steps, t2v_denoise, t2v_fps, t2v_sampler, t2v_scheduler,
        t2v_status, t2v_output_video,
        # R2V (19 components)
        r2v_prompt, r2v_video, r2v_audio,
        r2v_img1, r2v_img2, r2v_img3, r2v_img4,
        r2v_image_size,
        r2v_aspect_ratio, r2v_quality_level,
        r2v_duration, r2v_seed,
        r2v_steps, r2v_denoise, r2v_fps, r2v_sampler, r2v_scheduler,
        r2v_status, r2v_output_video,
    ]

    # Spec Task 2: Auto-poll active task progress every 1s for reconnected sessions
    task_poll_timer = gr.Timer(value=1.0)
    task_poll_timer.tick(
        poll_active_task_progress,
        inputs=[device_id_state, session_task_state],
        outputs=[
            session_task_state,
            i2v_status, i2v_output_video,
            t2v_status, t2v_output_video,
            r2v_status, r2v_output_video,
            history_dropdown,
        ]
    )

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

    # Manual ID Switch Events (Spec 8)
    edit_id_btn.click(lambda: gr.update(visible=True), outputs=[edit_id_row])
    cancel_id_btn.click(lambda: gr.update(visible=False), outputs=[edit_id_row])
    save_id_btn.click(
        switch_manual_device_id,
        inputs=[manual_id_input, device_id_state, session_task_state],
        outputs=[edit_id_row, *all_restored_outputs],
    )
    manual_id_input.submit(
        switch_manual_device_id,
        inputs=[manual_id_input, device_id_state, session_task_state],
        outputs=[edit_id_row, *all_restored_outputs],
    )

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Checks whether a local TCP port is already bound."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def find_pids_on_port(port: int) -> list:
    """Finds PIDs listening on the specified port on Windows."""
    import subprocess
    try:
        output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True)
        pids = []
        for line in output.strip().splitlines():
            line_str = line.strip()
            if f":{port}" in line_str and "LISTENING" in line_str:
                parts = line_str.split()
                if len(parts) >= 5 and parts[-1] not in pids:
                    pids.append(parts[-1])
        return pids
    except Exception:
        return []


def get_process_name_by_pid(pid: str) -> str:
    """Gets the executable process name for a PID on Windows."""
    import subprocess
    try:
        out = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /FO CSV /NH', shell=True, text=True)
        if out and "," in out:
            return out.split(",")[0].strip('"\r\n ')
    except Exception:
        pass
    return "Unknown"


def print_port_conflict_help(port: int):
    """
    Displays a clear, formatted error message and troubleshooting guide for administrators
    when the target port (7860) is occupied.
    """
    pids = find_pids_on_port(port)
    pid_details = []
    kill_cmds = []
    for pid in pids:
        proc_name = get_process_name_by_pid(pid)
        pid_details.append(f"PID: {pid} ({proc_name})")
        kill_cmds.append(f"taskkill /PID {pid} /F")

    pid_str = ", ".join(pid_details) if pid_details else "無法直接取得（可能為其他使用者或系統服務）"

    print("\n" + "=" * 70)
    print(f"❌ [錯誤] 前端伺服器啟動失敗：連接埠 {port} 已被佔用！")
    print("=" * 70)
    print("【排查診斷資訊】：")
    print(f" • 目標連接埠：{port}")
    print(f" • 佔用進程資訊：{pid_str}")
    print()
    print("【伺服器管理員排查與解決步驟】：")
    print(f" 1. 使用者預設透過 http://127.0.0.1:{port} 訪問，系統維持固定通訊埠而不隨意跳號。")
    print(" 2. 請檢查是否已有先前開啟但未完全關閉的 WebUI 終端機或背景 Python 進程。")
    if kill_cmds:
        print(" 3. 若欲強制結束佔用此連接埠的進程，可開啟命令提示字元（CMD）或 PowerShell 執行：")
        for k_cmd in kill_cmds:
            print(f"    👉 {k_cmd}")
        print(f"    （亦可手動執行 netstat -ano | findstr :{port} 再次確認通訊狀態）")
    else:
        print(f" 3. 可於終端機執行下列指令查詢佔用此連接埠的 PID：")
        print(f"    👉 netstat -ano | findstr :{port}")
        print(f"    再執行 👉 taskkill /PID <查詢到的PID> /F 強制釋放。")
    print(f" 4. 釋放連接埠後，請重新執行 run.bat 啟動伺服器。")
    print("=" * 70 + "\n")


def launch_webui(port: int = WEBUI_PORT, raise_on_error: bool = False, **launch_kwargs):
    """
    Launches the Gradio WebUI strictly on the specified port (default 7860).
    If the port is occupied, displays a clear error and troubleshooting guide for the admin.
    """
    import sys
    import threading

    # If running inside Gradio's reload watcher thread or server is already running, bypass re-launch
    if (
        getattr(demo, "_is_running_in_reload_thread", False)
        or getattr(demo, "is_running", False)
        or (os.environ.get("GRADIO_WATCH_DIRS") and threading.current_thread() is not threading.main_thread())
    ):
        return demo

    if is_port_in_use(port):
        print_port_conflict_help(port)
        if raise_on_error:
            raise OSError(f"Port {port} is already in use by another process.")
        sys.exit(1)

    print("=" * 60)
    print(f"MiniMax-H3 Gradio WebUI Starting (Port: {port})...")
    print(f"Local Access: http://127.0.0.1:{port}")
    print(f"Mobile LAN Access: http://{lan_ip}:{port}")
    print(f"ComfyUI Backend: {COMFY_SERVER_URL}")
    print("=" * 60)
    logger.info("Starting Gradio WebUI on http://%s:%s (Local: http://127.0.0.1:%s, Mobile: http://%s:%s)",
                WEBUI_HOST, port, port, lan_ip, port)

    allowed = [OUTPUT_DIR]
    if "allowed_paths" in launch_kwargs:
        extra_paths = launch_kwargs.pop("allowed_paths")
        if isinstance(extra_paths, list):
            allowed.extend(extra_paths)
        else:
            allowed.append(extra_paths)

    kwargs = {
        "server_name": WEBUI_HOST,
        "server_port": port,
        "share": False,
        "theme": gr.themes.Default(primary_hue="blue"),
        "css": CUSTOM_CSS,
        "head": CUSTOM_HEAD_JS,
        "allowed_paths": list(set(allowed)),
    }
    kwargs.update(launch_kwargs)
    try:
        return demo.launch(**kwargs)
    except OSError as e:
        if "Cannot find empty port" in str(e) or "10048" in str(e):
            print_port_conflict_help(port)
            if raise_on_error:
                raise
            sys.exit(1)
        raise

if __name__ == "__main__":
    launch_webui()

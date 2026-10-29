"""
MiniMax-H3 Mobile-Friendly Gradio WebUI with Persistent Session, Input Restoration,
and Strict Per-Device Isolation.
"""
import os
import time
import uuid
import random
import socket
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image
import gradio as gr
from config import (
    COMFY_SERVER_URL,
    WEBUI_HOST,
    WEBUI_PORT,
    SERVER_STATUS_OK,
    SERVER_STATUS_UPDATING,
    get_server_status,
    set_server_status,
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
    check_system_resources,
    start_comfyui_backend,
    stop_comfyui_backend,
    upload_media_file,
    free_comfyui_memory,
    clear_comfyui_queue,
    get_comfyui_queue_status,
    get_system_dashboard_data,
    interrupt_execution,
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

/* Two-line status box styling */
.backend-status-box {
    min-height: 48px !important;
    line-height: 1.5 !important;
    display: flex !important;
    align-items: center !important;
    padding: 6px 12px !important;
    margin-top: 4px !important;
    margin-bottom: 8px !important;
    border-radius: 8px !important;
    background: rgba(30, 41, 59, 0.35) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-sizing: border-box !important;
}

.backend-status-box p {
    margin: 0 !important;
    padding: 0 !important;
}

.res-display-box {
    min-height: 44px !important;
    line-height: 1.5 !important;
    display: flex !important;
    align-items: center !important;
    padding: 8px 14px !important;
    margin-top: 4px !important;
    margin-bottom: 6px !important;
    border-radius: 8px !important;
    background: rgba(30, 41, 59, 0.45) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-sizing: border-box !important;
}

.res-display-box p {
    margin: 0 !important;
    padding: 0 !important;
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
    status_banner = ""
    if get_server_status() == SERVER_STATUS_UPDATING:
        status_banner = (
            '<div style="margin-top: 8px; padding: 6px 14px; background: #fff1f2; '
            'border: 1.5px solid #fda4af; border-radius: 6px; color: #e11d48; '
            'font-weight: 700; font-size: 0.95rem; text-align: center;">'
            '🔧 伺服器維護/更新中'
            '</div>'
        )

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
        {status_banner}
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
        <div style="display: flex; justify-content: space-between; align-items: center; min-height: 44px; margin-bottom: 6px; font-size: 0.9rem; font-weight: 500; color: #334155; box-sizing: border-box;">
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
                return f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP)"
            except Exception:
                pass
        w, h = calculate_dimensions("16:9 (橫向風景)", quality_str, multiple=DEFAULT_MULTIPLE)
        actual_mp = round((w * h) / 1_000_000, 2)
        return f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP)"

    ar = normalize_aspect_ratio(ar, allow_original=False)
    w, h = calculate_dimensions(ar, quality_str, multiple=DEFAULT_MULTIPLE)
    actual_mp = round((w * h) / 1_000_000, 2)
    return f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP)"


def on_first_frame_change(img_path, current_quality_str):
    """Detects uploaded image dimensions and automatically aligns to distortion-free original aspect ratio."""
    if not img_path or not os.path.exists(img_path):
        w, h = calculate_dimensions("16:9 (橫向風景)", current_quality_str, multiple=DEFAULT_MULTIPLE)
        actual_mp = round((w * h) / 1_000_000, 2)
        return gr.update(), f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP)", ""
    try:
        current_quality_str = normalize_quality_choice(current_quality_str)
        with Image.open(img_path) as im:
            orig_w, orig_h = im.size
        w, h = calculate_dimensions_adaptive_ratio(orig_w, orig_h, current_quality_str, multiple=DEFAULT_MULTIPLE)
        actual_mp = round((w * h) / 1_000_000, 2)

        info_text = f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP)"
        badge_text = f"💡 *原始尺寸：`{orig_w} x {orig_h}`*"
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


def on_delete_history_item(selected_task_id, device_id):
    """Deletes the selected historical task, cleans up storage, and refreshes the gallery."""
    if not selected_task_id:
        choices = get_history_dropdown_choices(device_id)
        return gr.update(choices=choices), None, "選擇上方任務查看詳細資訊與播放。"

    task_manager.delete_task(selected_task_id, device_id=device_id)
    choices = get_history_dropdown_choices(device_id)
    new_value = choices[0][1] if choices and choices[0][1] else ""

    if new_value:
        new_video, new_info = on_select_history_item(new_value, device_id)
        return gr.update(choices=choices, value=new_value), new_video, new_info
    else:
        return gr.update(choices=choices, value=""), None, "選擇上方任務查看詳細資訊與播放。"


# --- Super User / Admin Operations (Spec Task) ---

def get_local_ip_set() -> set:
    """Returns the set of IP addresses that belong to the local host machine."""
    ips = {"127.0.0.1", "::1", "localhost", "testclient"}
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            ips.add(ip)
    except Exception:
        pass
    try:
        ips.add(get_lan_ip())
    except Exception:
        pass
    return ips


def is_super_user(request: Optional[gr.Request] = None) -> bool:
    """
    Checks if client connection originates from localhost (same machine).
    Localhost clients ('127.0.0.1', 'localhost', '::1', 'testclient', and the host's own LAN IP)
    are granted Super User status. Remote LAN devices (e.g. mobile phones) return False.
    """
    if request is None:
        return False
    client = getattr(request, "client", None)
    host = getattr(client, "host", "") if client else ""
    if not host:
        return False
    return host in get_local_ip_set()


def check_super_user_visibility(request: gr.Request) -> dict:
    """Dynamically sets Admin tab visibility on page load based on client IP."""
    return gr.update(visible=is_super_user(request))


def build_admin_status_badge() -> str:
    status = get_server_status()
    if status == SERVER_STATUS_OK:
        return (
            '<div style="padding: 8px 16px; border-radius: 8px; background: #ecfdf5; '
            'border: 1.5px solid #6ee7b7; color: #047857; font-weight: 700; font-size: 0.95rem;">'
            '🟢 系統狀態：正常服務中 (OK)'
            '</div>'
        )
    return (
        '<div style="padding: 8px 16px; border-radius: 8px; background: #fff1f2; '
        'border: 1.5px solid #fda4af; color: #e11d48; font-weight: 700; font-size: 0.95rem;">'
        '🔧 系統狀態：維護更新中 (UPDATING)'
        '</div>'
    )


def build_admin_hw_dashboard_html() -> str:
    d = get_system_dashboard_data()

    card_style = (
        'background: #f8fafc; border: 1.5px solid #e2e8f0; border-radius: 10px; '
        'padding: 14px 18px; flex: 1; min-width: 180px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);'
    )
    title_style = 'font-size: 0.85rem; font-weight: 600; color: #64748b; margin-bottom: 6px;'
    val_style = 'font-size: 1.25rem; font-weight: 700; color: #0f172a; margin-bottom: 4px;'
    sub_style = 'font-size: 0.8rem; color: #94a3b8;'

    return f"""
    <div style="display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 8px;">
        <div style="{card_style}">
            <div style="{title_style}">🧠 記憶體 (RAM)</div>
            <div style="{val_style}">{d['ram_used_gb']} / {d['ram_total_gb']} GB</div>
            <div style="{sub_style}">可用 {d['ram_available_gb']} GB ({d['ram_percent']}%)</div>
        </div>
        <div style="{card_style}">
            <div style="{title_style}">⚡ GPU 核心負載</div>
            <div style="{val_style}">{d['gpu_util_pct']}%</div>
            <div style="{sub_style}">晶片即時運算佔用</div>
        </div>
        <div style="{card_style}">
            <div style="{title_style}">🎮 GPU 顯存 (VRAM)</div>
            <div style="{val_style}">{d['vram_used_gb']} / {d['vram_total_gb']} GB</div>
            <div style="{sub_style}">可用 {d['vram_free_gb']} GB ({d['vram_percent']}%)</div>
        </div>
        <div style="{card_style}">
            <div style="{title_style}">💾 輸出磁碟空間</div>
            <div style="{val_style}">{d['disk_free_gb']} GB 可用</div>
            <div style="{sub_style}">總量 {d['disk_total_gb']} GB ({d['disk_percent']}% 已用)</div>
        </div>
    </div>
    """


def build_admin_queue_html() -> str:
    q = get_comfyui_queue_status()
    if not q["online"]:
        return '<div style="padding: 12px; background: #fff1f2; border: 1.5px solid #fecdd3; border-radius: 8px; color: #e11d48; font-weight: 600;">🔴 ComfyUI 後端未連線</div>'

    running = q.get("running", [])
    pending = q.get("pending", [])

    running_html = ""
    if running:
        p_id = running[0][1] if len(running[0]) > 1 else str(running[0])
        running_html = f'<div style="margin-bottom: 8px; color: #1e293b;">⚡ <b>正在運算任務</b>：<code>{p_id}</code></div>'
    else:
        running_html = '<div style="margin-bottom: 8px; color: #64748b;">☕ 目前無正在執行的生成任務</div>'

    pending_html = ""
    if pending:
        items = []
        for idx, item in enumerate(pending, 1):
            pid = item[1] if len(item) > 1 else str(item)
            items.append(f"<li>#{idx} - <code>{pid}</code></li>")
        pending_html = f'<div style="color: #1e293b;">⏳ <b>排隊中 ({len(pending)} 個)</b>：<ul style="margin: 4px 0 0 18px; padding: 0;">{"".join(items)}</ul></div>'
    else:
        pending_html = '<div style="color: #64748b;">🟢 佇列無排隊中的任務</div>'

    return f"""
    <div style="background: #f8fafc; border: 1.5px solid #e2e8f0; border-radius: 8px; padding: 14px 18px;">
        {running_html}
        {pending_html}
    </div>
    """


def build_admin_devices_html() -> str:
    summaries = task_manager.get_connected_devices_summary()
    if not summaries:
        return '<div style="padding: 12px; color: #64748b;">暫無連線裝置紀錄</div>'

    rows = []
    for s in summaries:
        t_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["last_active"]))
        rows.append(
            f'<tr style="border-bottom: 1px solid #f1f5f9;">'
            f'<td style="padding: 8px 12px; font-weight: 600;"><code>{s["device_id"]}</code></td>'
            f'<td style="padding: 8px 12px;">{s["task_count"]}</td>'
            f'<td style="padding: 8px 12px;">{s["completed_count"]}</td>'
            f'<td style="padding: 8px 12px; color: #64748b;">{t_str}</td>'
            f'</tr>'
        )

    return f"""
    <table style="width: 100%; border-collapse: collapse; background: #ffffff; border: 1.5px solid #e2e8f0; border-radius: 8px; overflow: hidden; font-size: 0.9rem;">
        <thead>
            <tr style="background: #f8fafc; border-bottom: 1.5px solid #e2e8f0; text-align: left; color: #475569;">
                <th style="padding: 10px 12px;">裝置代碼 (Device ID)</th>
                <th style="padding: 10px 12px;">總任務數</th>
                <th style="padding: 10px 12px;">成功生成</th>
                <th style="padding: 10px 12px;">最後活躍時間</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
    """


def get_admin_device_filter_choices() -> List[str]:
    summaries = task_manager.get_connected_devices_summary()
    dev_ids = [s["device_id"] for s in summaries if s.get("device_id")]
    return ["全部裝置"] + dev_ids


def get_admin_tasks_dropdown_choices(device_filter: str = "全部裝置", status_filter: str = "全部狀態") -> List[Tuple[str, str]]:
    tasks = task_manager.get_all_tasks(device_filter, status_filter)
    if not tasks:
        return [("— 查無符合條件的任務 —", "")]

    choices = []
    for t in tasks:
        t_str = time.strftime("%m/%d %H:%M", time.localtime(t.created_at))
        short_prompt = (t.prompt[:25] + "...") if len(t.prompt) > 25 else t.prompt
        short_dev = t.device_id.split("_")[-1][:6] if "_" in t.device_id else t.device_id[:6]
        status_icon = "✅" if t.status == "completed" else ("⚡" if t.status == "running" else ("⏳" if t.status == "queued" else "❌"))
        label = f"{status_icon} [{t.task_type}] ID:{short_dev} | {t_str} | {short_prompt}"
        choices.append((label, t.task_id))
    return choices


def on_toggle_server_status(request: gr.Request = None):
    if not is_super_user(request):
        return gr.update(), gr.update(), "⚠️ 權限不足，僅限本機管理員操作"
    cur = get_server_status()
    new_status = SERVER_STATUS_UPDATING if cur == SERVER_STATUS_OK else SERVER_STATUS_OK
    set_server_status(new_status)
    btn_text = "切換為維護模式" if new_status == SERVER_STATUS_OK else "恢復正常服務"
    badge_html = build_admin_status_badge()
    msg = f"✅ 已成功切換為：{'🟢 正常服務中' if new_status == SERVER_STATUS_OK else '🔧 伺服器維護/更新中'}"
    return badge_html, gr.update(value=btn_text), msg


def on_free_vram(request: gr.Request = None):
    if not is_super_user(request):
        return "⚠️ 權限不足，僅限本機管理員操作"
    ok, msg = free_comfyui_memory()
    return msg


def on_restart_backend(request: gr.Request = None):
    if not is_super_user(request):
        return "⚠️ 權限不足，僅限本機管理員操作"
    stop_comfyui_backend()
    time.sleep(1)
    ok, msg = start_comfyui_backend()
    return msg


def on_cancel_current_task(request: gr.Request = None):
    if not is_super_user(request):
        return build_admin_queue_html(), "⚠️ 權限不足"
    q = get_comfyui_queue_status()
    running = q.get("running", [])
    if running and len(running[0]) > 1:
        pid = running[0][1]
        interrupt_execution(pid)
        time.sleep(0.5)
        return build_admin_queue_html(), f"🛑 已送出中斷請求 (Prompt ID: {pid[:8]})"
    return build_admin_queue_html(), "目前無正在執行的生成任務"


def on_clear_queue(request: gr.Request = None):
    if not is_super_user(request):
        return build_admin_queue_html(), "⚠️ 權限不足"
    ok, msg = clear_comfyui_queue()
    time.sleep(0.5)
    return build_admin_queue_html(), msg


def on_select_admin_task(selected_task_id, request: gr.Request = None):
    if not is_super_user(request):
        return None, "⚠️ 權限不足"
    if not selected_task_id:
        return None, "請選擇上方任務"
    task = task_manager.get_task(selected_task_id)
    if not task:
        return None, "⚠️ 找不到該任務紀錄"

    video_path = task.video_path if task.video_path and os.path.exists(task.video_path) else None
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task.created_at))
    status_str = "已完成" if task.status == "completed" else ("運算中" if task.status == "running" else ("排隊中" if task.status == "queued" else "失敗/中斷"))

    params = task.params or {}
    w = params.get("width", "-")
    h = params.get("height", "-")
    seed = params.get("seed", "-")
    duration = params.get("duration", "-")

    info_md = f"""
    ### 📜 任務詳細資料 (管理員檢視)
    * **任務代碼**：`{task.task_id}`
    * **所屬裝置**：`{task.device_id}`
    * **任務類型**：`{task.task_type}`
    * **當前狀態**：`{status_str}` ({task.message})
    * **建立時間**：{t_str}
    * **總耗時**：{task.elapsed} 秒
    * **解析度**：`{w} x {h}`
    * **隨機種子**：`{seed}`
    * **影片長度**：`{duration} 秒`
    * **產出檔案**：`{os.path.basename(task.video_path) if task.video_path else "無"}`
    * **提示詞**：
    ```text
    {task.prompt}
    ```
    """
    return video_path, info_md


def on_delete_admin_task(selected_task_id, device_filter, status_filter, request: gr.Request = None):
    if not is_super_user(request):
        return gr.update(), None, "⚠️ 權限不足", gr.update()
    if not selected_task_id:
        choices = get_admin_tasks_dropdown_choices(device_filter, status_filter)
        return gr.update(choices=choices), None, "請選擇上方任務", gr.update()

    task_manager.delete_task(selected_task_id, is_admin=True)
    choices = get_admin_tasks_dropdown_choices(device_filter, status_filter)
    new_value = choices[0][1] if choices and choices[0][1] else ""

    dev_choices = get_admin_device_filter_choices()
    if new_value:
        new_video, new_info = on_select_admin_task(new_value, request)
        return gr.update(choices=choices, value=new_value), new_video, new_info, gr.update(choices=dev_choices)
    return gr.update(choices=choices, value=""), None, "✅ 任務已成功刪除", gr.update(choices=dev_choices)


def on_clean_failed_tasks(device_filter, status_filter, request: gr.Request = None):
    if not is_super_user(request):
        return gr.update(), None, "⚠️ 權限不足", gr.update()
    count = task_manager.delete_failed_and_interrupted_tasks()
    choices = get_admin_tasks_dropdown_choices(device_filter, status_filter)
    dev_choices = get_admin_device_filter_choices()
    msg = f"🧹 已清除 {count} 個失敗或中斷的任務"
    return gr.update(choices=choices, value=""), None, msg, gr.update(choices=dev_choices)



def handle_stop_generate(device_id):
    """Handles user clicking the '停止生成' button to abort active tasks for their device (Spec 1)."""
    interrupted = task_manager.interrupt_device_tasks(device_id=device_id)
    logger.info("[App] User stopped generation for device '%s'. Interrupted: %s", device_id, interrupted)
    return (
        build_progress_html("⚠️ 任務已被手動中斷"),
        gr.update(visible=True),
        gr.update(visible=False),
    )


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

    if get_server_status() == SERVER_STATUS_UPDATING:
        yield build_progress_html("⚠️ 伺服器維護/更新中，暫停提交生成任務"), None, current_session_task, device_id
        return

    if not first_frame:
        yield build_progress_html("❌ 請上傳首幀圖片"), None, current_session_task, device_id
        return

    if not prompt or not prompt.strip():
        yield build_progress_html("❌ 請輸入提示詞"), None, current_session_task, device_id
        return

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

    yield build_progress_html("⚡ 前處理中：正在準備生成..."), None, current_session_task, device_id

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

    # Task 3 & 6: Width and height for T2V are calculated from Aspect Ratio and Quality Level (MP)
    w, h = calculate_dimensions(aspect_ratio, quality_level, multiple=DEFAULT_MULTIPLE)

    yield build_progress_html("⚡ 前處理中：正在準備生成..."), None, current_session_task, device_id

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

    yield build_progress_html("⚡ 前處理中：正在準備生成..."), None, current_session_task, device_id

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

    # Compute button states based on whether this device has an active running/queued task (Spec 1)
    active_task = task_manager.get_active_task_for_device(stored_device_id)
    is_active = active_task is not None
    active_type = active_task.task_type if active_task else None

    i2v_btn_st = gr.update(visible=False) if (is_active and active_type == "I2V") else gr.update(visible=True)
    i2v_stop_st = gr.update(visible=True) if (is_active and active_type == "I2V") else gr.update(visible=False)

    t2v_btn_st = gr.update(visible=False) if (is_active and active_type == "T2V") else gr.update(visible=True)
    t2v_stop_st = gr.update(visible=True) if (is_active and active_type == "T2V") else gr.update(visible=False)

    r2v_btn_st = gr.update(visible=False) if (is_active and active_type == "R2V") else gr.update(visible=True)
    r2v_stop_st = gr.update(visible=True) if (is_active and active_type == "R2V") else gr.update(visible=False)

    btn_updates = [i2v_btn_st, i2v_stop_st, t2v_btn_st, t2v_stop_st, r2v_btn_st, r2v_stop_st]

    return (
        stored_device_id,
        active_task_id,
        header,
        gr.update(choices=history_choices),
        *i2v_updates,
        *t2v_updates,
        *r2v_updates,
        *btn_updates,
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
    default_btns = [
        gr.update(visible=True), gr.update(visible=False),
        gr.update(visible=True), gr.update(visible=False),
        gr.update(visible=True), gr.update(visible=False),
    ]

    if not stored_device_id:
        return (
            gr.update(),
            gr.update(), gr.update(),
            gr.update(), gr.update(),
            gr.update(), gr.update(),
            gr.update(),
            *default_btns,
        )

    task = task_manager.get_active_task_for_device(stored_device_id) or task_manager.get_task(stored_task_id, device_id=stored_device_id)
    if not task:
        task = task_manager.get_latest_task_for_device(stored_device_id)

    if not task:
        return (
            gr.update(),
            gr.update(), gr.update(),
            gr.update(), gr.update(),
            gr.update(), gr.update(),
            gr.update(),
            *default_btns,
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
                *default_btns,
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
                *default_btns,
            )
        elif task.task_type == "T2V":
            return (
                task.task_id,
                gr.update(), gr.update(),
                progress_html, video_val,
                gr.update(), gr.update(),
                gr.update(choices=history_choices),
                *default_btns,
            )
        elif task.task_type == "R2V":
            return (
                task.task_id,
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                progress_html, video_val,
                gr.update(choices=history_choices),
                *default_btns,
            )

    # 2. Task is actively queued or running
    if task.status in ("queued", "running"):
        _device_last_reported_completed.pop(stored_device_id, None)
        progress_html = build_progress_html(task)

        i2v_btn_st = gr.update(visible=False) if task.task_type == "I2V" else gr.update(visible=True)
        i2v_stop_st = gr.update(visible=True) if task.task_type == "I2V" else gr.update(visible=False)

        t2v_btn_st = gr.update(visible=False) if task.task_type == "T2V" else gr.update(visible=True)
        t2v_stop_st = gr.update(visible=True) if task.task_type == "T2V" else gr.update(visible=False)

        r2v_btn_st = gr.update(visible=False) if task.task_type == "R2V" else gr.update(visible=True)
        r2v_stop_st = gr.update(visible=True) if task.task_type == "R2V" else gr.update(visible=False)

        active_btns = [i2v_btn_st, i2v_stop_st, t2v_btn_st, t2v_stop_st, r2v_btn_st, r2v_stop_st]

        last_html = _device_last_status_html.get(stored_device_id)
        if last_html == progress_html:
            return (
                gr.update(),
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                gr.update(),
                *active_btns,
            )
        _device_last_status_html[stored_device_id] = progress_html

        if task.task_type == "I2V":
            return (
                task.task_id,
                progress_html, gr.update(),
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                gr.update(),
                *active_btns,
            )
        elif task.task_type == "T2V":
            return (
                task.task_id,
                gr.update(), gr.update(),
                progress_html, gr.update(),
                gr.update(), gr.update(),
                gr.update(),
                *active_btns,
            )
        elif task.task_type == "R2V":
            return (
                task.task_id,
                gr.update(), gr.update(),
                gr.update(), gr.update(),
                progress_html, gr.update(),
                gr.update(),
                *active_btns,
            )

    return (
        gr.update(),
        gr.update(), gr.update(),
        gr.update(), gr.update(),
        gr.update(), gr.update(),
        gr.update(),
        *default_btns,
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
            label="切換裝置 ID",
            placeholder="請輸入 6 位數代碼 (例如 71c8f5)...",
            scale=5,
        )
        save_id_btn = gr.Button("確認切換", variant="primary", scale=1)
        cancel_id_btn = gr.Button("取消", variant="secondary", scale=1)

    # ComfyUI Backend Control Toolbar (Spec 6)
    with gr.Row():
        start_backend_btn = gr.Button("⚡ 檢查後端模型狀態...", variant="secondary", scale=9)
        stop_backend_btn = gr.Button("🛑", variant="stop", scale=1, min_width=50)

    backend_status_msg = gr.Markdown("", elem_classes=["backend-status-box"])

    # Auto poll backend status every 0.5s to dynamically color and label the button
    auto_timer = gr.Timer(value=0.5)
    _is_backend_starting = False

    def poll_backend_status():
        if get_server_status() == SERVER_STATUS_UPDATING:
            return gr.update(value="🔧 伺服器維護/更新中", variant="stop")
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
        if get_server_status() == SERVER_STATUS_UPDATING:
            yield gr.update(value="🔧 伺服器維護/更新中", variant="stop"), "⚠️ 伺服器維護/更新中，暫停啟動後端"
            return
        ok, _ = check_server(COMFY_SERVER_URL)
        if ok:
            yield gr.update(value="🟢 後端模型運作中", variant="primary"), "🟢 後端模型已經在運作中，無須重複啟動"
            return

        # Pre-check computer resources before launching backend (Spec Task 2)
        res_ok, warning_msg, _ = check_system_resources()
        if not res_ok:
            yield gr.update(value="⚡ 啟動後端模型", variant="secondary"), warning_msg
            return

        _is_backend_starting = True
        yield gr.update(value="🟡 正在啟動後端模型...", variant="secondary"), "🟡 正在啟動後端模型，請稍候..."

        try:
            ok, msg = start_comfyui_backend(COMFY_SERVER_URL, skip_resource_check=True)
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
                            scale=1,
                            filterable=False,
                        )
                        i2v_quality_level = gr.Dropdown(
                            choices=QUALITY_CHOICES,
                            value=DEFAULT_QUALITY_LEVEL,
                            label="畫質等級",
                            scale=1,
                            filterable=False,
                        )

                    # Output resolution dedicated 2-line display card
                    i2v_res_info = gr.Markdown("📐 **輸出解析度**：`1344 x 768` (~1.03 MP)", elem_classes=["res-display-box"])

                    # Row 2: Duration, Steps, FPS (Basic Parameters)
                    with gr.Row():
                        i2v_duration = gr.Slider(
                            minimum=1.0, maximum=15.0, value=2.0, step=0.5,
                            label="影片時長 (秒)", scale=1
                        )
                        i2v_steps = gr.Slider(
                            minimum=1, maximum=50, value=20, step=1,
                            label="取樣步數", scale=1
                        )
                        i2v_fps = gr.Slider(
                            minimum=12, maximum=60, value=24, step=1,
                            label="影格率 (FPS)", scale=1
                        )

                    with gr.Accordion("⚙️ 進階參數", open=False):
                        with gr.Row():
                            i2v_seed = gr.Number(value=1, precision=0, label="隨機種子", scale=4)
                            i2v_rand_btn = gr.Button("🎲 隨機", scale=1)
                        with gr.Row():
                            i2v_denoise = gr.Slider(minimum=0.1, maximum=1.0, value=1.0, step=0.05, label="去噪強度")
                        with gr.Row():
                            i2v_sampler = gr.Dropdown(choices=SAMPLER_CHOICES, value="res_multistep", label="取樣器", filterable=False)
                            i2v_scheduler = gr.Dropdown(choices=SCHEDULER_CHOICES, value="simple", label="調度器", filterable=False)

                    with gr.Row():
                        i2v_btn = gr.Button("🚀 開始生成影片", variant="primary", elem_classes=["primary-btn"], visible=True)
                        i2v_stop_btn = gr.Button("🛑 停止生成", variant="stop", visible=False)

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
            i2v_gen_event = i2v_btn.click(
                lambda: (gr.update(visible=False), gr.update(visible=True)),
                outputs=[i2v_btn, i2v_stop_btn],
            ).then(
                handle_i2v_generate,
                inputs=[
                    i2v_first_frame, i2v_last_frame, i2v_prompt,
                    i2v_aspect_ratio, i2v_quality_level,
                    i2v_duration, i2v_seed,
                    i2v_steps, i2v_denoise, i2v_sampler, i2v_scheduler, i2v_fps,
                    session_task_state, device_id_state
                ],
                outputs=[i2v_status, i2v_output_video, session_task_state, device_id_state],
                concurrency_limit=None,
            ).then(
                lambda: (gr.update(visible=True), gr.update(visible=False)),
                outputs=[i2v_btn, i2v_stop_btn],
            )

            i2v_stop_btn.click(
                handle_stop_generate,
                inputs=[device_id_state],
                outputs=[i2v_status, i2v_btn, i2v_stop_btn],
                cancels=[i2v_gen_event],
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
                            scale=1,
                            filterable=False,
                        )
                        t2v_quality_level = gr.Dropdown(
                            choices=QUALITY_CHOICES,
                            value=DEFAULT_QUALITY_LEVEL,
                            label="畫質等級",
                            scale=1,
                            filterable=False,
                        )

                    # Output resolution dedicated 2-line display card
                    t2v_res_info = gr.Markdown("📐 **輸出解析度**：`1344 x 768` (~1.03 MP)", elem_classes=["res-display-box"])

                    # Row 2: Duration, Steps, FPS (Basic Parameters)
                    with gr.Row():
                        t2v_duration = gr.Slider(
                            minimum=1.0, maximum=15.0, value=2.0, step=0.5,
                            label="影片時長 (秒)", scale=1
                        )
                        t2v_steps = gr.Slider(
                            minimum=1, maximum=50, value=20, step=1,
                            label="取樣步數", scale=1
                        )
                        t2v_fps = gr.Slider(
                            minimum=12, maximum=60, value=24, step=1,
                            label="影格率 (FPS)", scale=1
                        )

                    with gr.Accordion("⚙️ 進階參數", open=False):
                        with gr.Row():
                            t2v_seed = gr.Number(value=1, precision=0, label="隨機種子", scale=4)
                            t2v_rand_btn = gr.Button("🎲 隨機", scale=1)
                        with gr.Row():
                            t2v_denoise = gr.Slider(minimum=0.1, maximum=1.0, value=1.0, step=0.05, label="去噪強度")
                        with gr.Row():
                            t2v_sampler = gr.Dropdown(choices=SAMPLER_CHOICES, value="res_multistep", label="取樣器", filterable=False)
                            t2v_scheduler = gr.Dropdown(choices=SCHEDULER_CHOICES, value="simple", label="調度器", filterable=False)

                    with gr.Row():
                        t2v_btn = gr.Button("🚀 開始生成影片", variant="primary", elem_classes=["primary-btn"], visible=True)
                        t2v_stop_btn = gr.Button("🛑 停止生成", variant="stop", visible=False)

                with gr.Column(scale=1):
                    t2v_status = gr.HTML(build_progress_html("🟢 準備就緒"))
                    t2v_recover_btn = gr.Button("🔄 恢復上次輸入與成果", variant="secondary")
                    t2v_output_video = gr.Video(label="生成影片", autoplay=True, interactive=False)

            # Auto resolution update listeners
            for comp in [t2v_aspect_ratio, t2v_quality_level]:
                comp.change(on_resolution_change, inputs=[t2v_aspect_ratio, t2v_quality_level], outputs=[t2v_res_info])

            t2v_rand_btn.click(generate_random_seed, outputs=[t2v_seed])
            t2v_gen_event = t2v_btn.click(
                lambda: (gr.update(visible=False), gr.update(visible=True)),
                outputs=[t2v_btn, t2v_stop_btn],
            ).then(
                handle_t2v_generate,
                inputs=[
                    t2v_prompt,
                    t2v_aspect_ratio, t2v_quality_level,
                    t2v_duration, t2v_seed,
                    t2v_steps, t2v_denoise, t2v_sampler, t2v_scheduler, t2v_fps,
                    session_task_state, device_id_state
                ],
                outputs=[t2v_status, t2v_output_video, session_task_state, device_id_state],
                concurrency_limit=None,
            ).then(
                lambda: (gr.update(visible=True), gr.update(visible=False)),
                outputs=[t2v_btn, t2v_stop_btn],
            )

            t2v_stop_btn.click(
                handle_stop_generate,
                inputs=[device_id_state],
                outputs=[t2v_status, t2v_btn, t2v_stop_btn],
                cancels=[t2v_gen_event],
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
                            scale=1,
                            filterable=False,
                        )
                        r2v_quality_level = gr.Dropdown(
                            choices=QUALITY_CHOICES,
                            value=DEFAULT_QUALITY_LEVEL,
                            label="畫質等級",
                            scale=1,
                            filterable=False,
                        )

                    # Output resolution dedicated 2-line display card
                    r2v_res_info = gr.Markdown("📐 **輸出解析度**：`1344 x 768` (~1.03 MP)", elem_classes=["res-display-box"])

                    # Row 2: Duration, Steps, FPS (Basic Parameters)
                    with gr.Row():
                        r2v_duration = gr.Slider(
                            minimum=1.0, maximum=18.0, value=3.0, step=0.5,
                            label="影片時長 (秒)", scale=1
                        )
                        r2v_steps = gr.Slider(
                            minimum=1, maximum=50, value=20, step=1,
                            label="取樣步數", scale=1
                        )
                        r2v_fps = gr.Slider(
                            minimum=12, maximum=60, value=24, step=1,
                            label="影格率 (FPS)", scale=1
                        )

                    with gr.Accordion("⚙️ 進階參數", open=False):
                        with gr.Row():
                            r2v_seed = gr.Number(value=1, precision=0, label="隨機種子", scale=4)
                            r2v_rand_btn = gr.Button("🎲 隨機", scale=1)
                        with gr.Row():
                            r2v_denoise = gr.Slider(minimum=0.1, maximum=1.0, value=1.0, step=0.05, label="去噪強度")
                        with gr.Row():
                            r2v_sampler = gr.Dropdown(choices=SAMPLER_CHOICES, value="res_multistep", label="取樣器", filterable=False)
                            r2v_scheduler = gr.Dropdown(choices=SCHEDULER_CHOICES, value="simple", label="調度器", filterable=False)

                    with gr.Row():
                        r2v_btn = gr.Button("🚀 開始生成影片", variant="primary", elem_classes=["primary-btn"], visible=True)
                        r2v_stop_btn = gr.Button("🛑 停止生成", variant="stop", visible=False)

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
            r2v_gen_event = r2v_btn.click(
                lambda: (gr.update(visible=False), gr.update(visible=True)),
                outputs=[r2v_btn, r2v_stop_btn],
            ).then(
                handle_r2v_generate,
                inputs=[
                    r2v_prompt, r2v_img1, r2v_img2, r2v_img3, r2v_img4,
                    r2v_video, r2v_audio, r2v_image_size,
                    r2v_aspect_ratio, r2v_quality_level,
                    r2v_duration, r2v_seed,
                    r2v_steps, r2v_denoise, r2v_sampler, r2v_scheduler, r2v_fps,
                    session_task_state, device_id_state
                ],
                outputs=[r2v_status, r2v_output_video, session_task_state, device_id_state],
                concurrency_limit=None,
            ).then(
                lambda: (gr.update(visible=True), gr.update(visible=False)),
                outputs=[r2v_btn, r2v_stop_btn],
            )

            r2v_stop_btn.click(
                handle_stop_generate,
                inputs=[device_id_state],
                outputs=[r2v_status, r2v_btn, r2v_stop_btn],
                cancels=[r2v_gen_event],
            )

        # ==========================================
        # TAB 4: 📁 歷史成果庫
        # ==========================================
        with gr.Tab("📁 歷史成果庫"):
            gr.Markdown("### 🗄️ 歷史生成記錄")
            with gr.Row():
                refresh_history_btn = gr.Button("🔄 重新整理", variant="secondary", scale=2)
                # Spec 5: Strictly a dropdown without combobox / textbox degradation
                history_dropdown = gr.Dropdown(
                    choices=[("— 暫無歷史紀錄 —", "")],
                    value="",
                    label="選擇歷史任務",
                    allow_custom_value=False,
                    filterable=False,
                    interactive=True,
                    scale=8,
                )
                delete_history_btn = gr.Button("🗑️", variant="stop", scale=1, min_width=50)
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
            delete_history_btn.click(
                on_delete_history_item,
                inputs=[history_dropdown, device_id_state],
                outputs=[history_dropdown, gallery_video, gallery_info]
            )

        # ==========================================
        # TAB 5: ⚙️ 管理員操作 (Super User Only)
        # ==========================================
        with gr.Tab("⚙️ 管理員操作", visible=False) as admin_tab:
            gr.Markdown("## ⚙️ 系統管理員操作台")

            # --- 區塊 1: 伺服器狀態與控制 ---
            gr.Markdown("### 🔧 伺服器運作與維護控制")
            with gr.Row():
                admin_status_badge = gr.HTML(build_admin_status_badge())
                admin_toggle_status_btn = gr.Button("切換為維護模式" if get_server_status() == SERVER_STATUS_OK else "恢復正常服務", variant="secondary")
                admin_free_vram_btn = gr.Button("🧹 釋放 GPU 顯存 (Free VRAM)", variant="secondary")
                admin_restart_backend_btn = gr.Button("🔄 重啟後端模型服務", variant="secondary")
            admin_op_msg = gr.Markdown("")

            # --- 區塊 2: 電腦硬體資源儀表板 ---
            gr.Markdown("### 📊 伺服器硬體資源狀態")
            admin_hw_dashboard_html = gr.HTML(build_admin_hw_dashboard_html())
            with gr.Row():
                admin_refresh_hw_btn = gr.Button("🔄 刷新硬體數據", variant="secondary", scale=1)

            # --- 區塊 3: 即時佇列監控 ---
            gr.Markdown("### ⏳ 即時運算與等待佇列")
            admin_queue_html = gr.HTML(build_admin_queue_html())
            with gr.Row():
                admin_cancel_current_btn = gr.Button("🛑 強制中斷當前任務", variant="stop")
                admin_clear_queue_btn = gr.Button("🗑️ 清空等待佇列", variant="secondary")
                admin_refresh_queue_btn = gr.Button("🔄 刷新佇列狀態", variant="secondary")

            # --- 區塊 4: 全域跨裝置歷史紀錄 ---
            gr.Markdown("### 🗂️ 全域跨裝置歷史紀錄")
            with gr.Row():
                admin_device_filter = gr.Dropdown(
                    choices=get_admin_device_filter_choices(),
                    value="全部裝置",
                    label="篩選裝置",
                    filterable=False,
                    allow_custom_value=False,
                    scale=3,
                )
                admin_status_filter = gr.Dropdown(
                    choices=["全部狀態", "已完成", "生成中/排隊中", "失敗/中斷"],
                    value="全部狀態",
                    label="篩選狀態",
                    filterable=False,
                    allow_custom_value=False,
                    scale=3,
                )
                admin_refresh_all_tasks_btn = gr.Button("🔄 刷新列表", variant="secondary", scale=1)
                admin_clean_failed_btn = gr.Button("🧹 一鍵清理失敗與中斷任務", variant="secondary", scale=2)

            _init_admin_choices = get_admin_tasks_dropdown_choices("全部裝置", "全部狀態")
            with gr.Row():
                admin_all_tasks_dropdown = gr.Dropdown(
                    choices=_init_admin_choices,
                    value=_init_admin_choices[0][1] if _init_admin_choices else "",
                    label="選取歷史任務 (全部裝置)",
                    filterable=False,
                    allow_custom_value=False,
                    scale=8,
                )
                admin_delete_task_btn = gr.Button("🗑️ 刪除此任務", variant="stop", scale=2)

            with gr.Row():
                with gr.Column(scale=1):
                    admin_video_preview = gr.Video(label="產出影片預覽", autoplay=False)
                with gr.Column(scale=1):
                    admin_task_detail = gr.Markdown("請從上方選取任務檢視詳細參數")

            # --- 區塊 5: 連線裝置總覽 ---
            gr.Markdown("### 📱 連線裝置總覽")
            admin_devices_html = gr.HTML(build_admin_devices_html())
            admin_refresh_devices_btn = gr.Button("🔄 刷新裝置列表", variant="secondary")

            # Wire up admin events
            admin_toggle_status_btn.click(
                on_toggle_server_status,
                outputs=[admin_status_badge, admin_toggle_status_btn, admin_op_msg],
            )
            admin_free_vram_btn.click(
                on_free_vram,
                outputs=[admin_op_msg],
            )
            admin_restart_backend_btn.click(
                on_restart_backend,
                outputs=[admin_op_msg],
            )
            admin_refresh_hw_btn.click(
                build_admin_hw_dashboard_html,
                outputs=[admin_hw_dashboard_html],
            )
            admin_cancel_current_btn.click(
                on_cancel_current_task,
                outputs=[admin_queue_html, admin_op_msg],
            )
            admin_clear_queue_btn.click(
                on_clear_queue,
                outputs=[admin_queue_html, admin_op_msg],
            )
            admin_refresh_queue_btn.click(
                build_admin_queue_html,
                outputs=[admin_queue_html],
            )
            admin_device_filter.change(
                get_admin_tasks_dropdown_choices,
                inputs=[admin_device_filter, admin_status_filter],
                outputs=[admin_all_tasks_dropdown],
            )
            admin_status_filter.change(
                get_admin_tasks_dropdown_choices,
                inputs=[admin_device_filter, admin_status_filter],
                outputs=[admin_all_tasks_dropdown],
            )
            admin_refresh_all_tasks_btn.click(
                get_admin_tasks_dropdown_choices,
                inputs=[admin_device_filter, admin_status_filter],
                outputs=[admin_all_tasks_dropdown],
            )
            admin_all_tasks_dropdown.change(
                on_select_admin_task,
                inputs=[admin_all_tasks_dropdown],
                outputs=[admin_video_preview, admin_task_detail],
            )
            admin_delete_task_btn.click(
                on_delete_admin_task,
                inputs=[admin_all_tasks_dropdown, admin_device_filter, admin_status_filter],
                outputs=[admin_all_tasks_dropdown, admin_video_preview, admin_task_detail, admin_device_filter],
            )
            admin_clean_failed_btn.click(
                on_clean_failed_tasks,
                inputs=[admin_device_filter, admin_status_filter],
                outputs=[admin_all_tasks_dropdown, admin_video_preview, admin_task_detail, admin_device_filter],
            )
            admin_refresh_devices_btn.click(
                build_admin_devices_html,
                outputs=[admin_devices_html],
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
        # Buttons (Spec 1: 6 components)
        i2v_btn, i2v_stop_btn,
        t2v_btn, t2v_stop_btn,
        r2v_btn, r2v_stop_btn,
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
            i2v_btn, i2v_stop_btn,
            t2v_btn, t2v_stop_btn,
            r2v_btn, r2v_stop_btn,
        ]
    )

    # Automatic page reload restoration (demo.load)
    demo.load(
        restore_device_state,
        inputs=[device_id_state, session_task_state],
        outputs=all_restored_outputs,
    )

    # Super User dynamic visibility on page load (Spec Task)
    demo.load(
        check_super_user_visibility,
        outputs=[admin_tab],
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

demo.queue(default_concurrency_limit=None)

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
        demo.queue(default_concurrency_limit=None)
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

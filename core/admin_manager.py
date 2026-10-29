"""
Administrator authorization, IP whitelist management, and backend maintenance supervisor.
"""
import os
import json
import time
import socket
import ipaddress
import threading
from typing import List, Tuple, Optional, Any
import gradio as gr
from config import (
    OUTPUT_DIR,
    SERVER_STATUS_OK,
    SERVER_STATUS_UPDATING,
    get_server_status,
    set_server_status,
    get_lan_ip,
)
from comfy_client import (
    free_comfyui_memory,
    start_comfyui_backend,
    stop_comfyui_backend,
    get_system_dashboard_data,
    get_comfyui_queue_status,
    interrupt_execution,
    clear_comfyui_queue,
)
from task_manager import task_manager
from logger import get_logger

logger = get_logger("AdminManager")

ADMIN_IPS_FILE = os.path.join(OUTPUT_DIR, "admin_ips.json")
_admin_ips_lock = threading.Lock()


class AdminManager:
    """Manages administrator IP whitelisting, superuser checks, and maintenance control."""

    @staticmethod
    def load_admin_ip_list() -> List[str]:
        if not os.path.exists(ADMIN_IPS_FILE):
            return []
        try:
            with _admin_ips_lock:
                with open(ADMIN_IPS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [str(ip).strip() for ip in data if str(ip).strip()]
        except Exception as e:
            logger.warning("Failed to load admin IP list: %s", e)
        return []

    @staticmethod
    def save_admin_ip_list(ip_list: List[str]):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        try:
            with _admin_ips_lock:
                with open(ADMIN_IPS_FILE, "w", encoding="utf-8") as f:
                    json.dump(sorted(list(set(ip_list))), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save admin IP list: %s", e)

    @staticmethod
    def is_valid_ip_address(ip_str: str) -> bool:
        try:
            ipaddress.ip_address(ip_str.strip())
            return True
        except Exception:
            return False

    @classmethod
    def normalize_ip(cls, host: str) -> str:
        """Normalizes IP address, stripping IPv4-mapped IPv6 prefixes and whitespace."""
        if not host:
            return ""
        clean = str(host).strip()
        if clean.startswith("::ffff:"):
            clean = clean[7:]
        return clean

    @classmethod
    def get_local_ip_set(cls) -> set:
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
        for custom_ip in cls.load_admin_ip_list():
            ips.add(custom_ip)
            ips.add(cls.normalize_ip(custom_ip))
        return ips

    @classmethod
    def is_super_user(cls, request: Optional[gr.Request] = None) -> bool:
        if request is None:
            return False
        client = getattr(request, "client", None)
        host = getattr(client, "host", "") if client else ""
        if not host:
            return False

        clean_host = cls.normalize_ip(host)

        # 1. Loopback addresses are guaranteed local administrator
        try:
            ip_obj = ipaddress.ip_address(clean_host)
            if ip_obj.is_loopback:
                return True
        except Exception:
            pass

        # 2. Check directly against local and configured admin set
        local_set = cls.get_local_ip_set()
        if host in local_set or clean_host in local_set:
            return True

        # 3. Check normalized comparison against admin IP list
        for admin_ip in cls.load_admin_ip_list():
            if clean_host == cls.normalize_ip(admin_ip):
                return True

        return False

    @classmethod
    def check_super_user_visibility(cls, request: gr.Request) -> dict:
        return gr.update(visible=cls.is_super_user(request))

    @classmethod
    def build_admin_status_badge(cls) -> str:
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

    @classmethod
    def build_admin_ip_list_html(cls) -> str:
        admin_ips = cls.load_admin_ip_list()
        lan = get_lan_ip()

        default_chips = f"""
        <span style="display: inline-block; background: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-size: 0.88rem; font-weight: 600; margin: 3px;">127.0.0.1 (本機)</span>
        <span style="display: inline-block; background: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-size: 0.88rem; font-weight: 600; margin: 3px;">{lan} (本機內網)</span>
        """

        if not admin_ips:
            custom_chips = '<span style="color: #64748b; font-size: 0.88rem; margin-left: 6px;">(目前尚未加入其他管理員 IP)</span>'
        else:
            chips = []
            for ip in admin_ips:
                chips.append(
                    f'<span style="display: inline-block; background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-size: 0.88rem; font-weight: 600; margin: 3px;">{ip}</span>'
                )
            custom_chips = "".join(chips)

        return f"""
        <div style="background: #ffffff; border: 1.5px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; line-height: 1.8;">
            <div style="font-size: 0.85rem; color: #475569; font-weight: 600; margin-bottom: 6px;">固定本機權限：</div>
            <div>{default_chips}</div>
            <div style="font-size: 0.85rem; color: #475569; font-weight: 600; margin-top: 10px; margin-bottom: 6px;">手動授權的管理員名單：</div>
            <div>{custom_chips}</div>
        </div>
        """

    @classmethod
    def get_admin_ip_remove_choices(cls) -> List[str]:
        ips = cls.load_admin_ip_list()
        return ips if ips else ["— 目前無可移除的管理員 IP —"]

    @classmethod
    def on_add_admin_ip(cls, new_ip: str, request: gr.Request = None):
        if not cls.is_super_user(request):
            return cls.build_admin_ip_list_html(), gr.update(), "⚠️ 權限不足"

        ip_clean = (new_ip or "").strip()
        if not ip_clean:
            return cls.build_admin_ip_list_html(), gr.update(choices=cls.get_admin_ip_remove_choices()), "⚠️ 請輸入有效的 IP 位址"

        if not cls.is_valid_ip_address(ip_clean):
            return cls.build_admin_ip_list_html(), gr.update(choices=cls.get_admin_ip_remove_choices()), f"❌ '{ip_clean}' 不是正確的 IP 格式 (例如 192.168.0.11)"

        local_defaults = {"127.0.0.1", "::1", "localhost", get_lan_ip()}
        if ip_clean in local_defaults:
            return cls.build_admin_ip_list_html(), gr.update(choices=cls.get_admin_ip_remove_choices()), f"ℹ️ '{ip_clean}' 本身已具有本機管理員權限，無需重複加入"

        current_list = cls.load_admin_ip_list()
        if ip_clean in current_list:
            return cls.build_admin_ip_list_html(), gr.update(choices=cls.get_admin_ip_remove_choices()), f"ℹ️ IP '{ip_clean}' 已在管理員名單中"

        current_list.append(ip_clean)
        cls.save_admin_ip_list(current_list)
        logger.info("[Admin] Added '%s' to admin IP list", ip_clean)
        rem_choices = cls.get_admin_ip_remove_choices()
        return cls.build_admin_ip_list_html(), gr.update(choices=rem_choices, value=rem_choices[0] if rem_choices else ""), f"✅ 已成功將 IP '{ip_clean}' 加入管理員名單"

    @classmethod
    def on_remove_admin_ip(cls, target_ip: str, request: gr.Request = None):
        if not cls.is_super_user(request):
            return cls.build_admin_ip_list_html(), gr.update(), "⚠️ 權限不足"

        target = (target_ip or "").strip()
        if not target or "無可移除" in target:
            return cls.build_admin_ip_list_html(), gr.update(choices=cls.get_admin_ip_remove_choices()), "請從選單中選取要移除的管理員 IP"

        current_list = cls.load_admin_ip_list()
        if target not in current_list:
            rem_choices = cls.get_admin_ip_remove_choices()
            return cls.build_admin_ip_list_html(), gr.update(choices=rem_choices), f"⚠️ IP '{target}' 不在自訂名單中"

        current_list.remove(target)
        cls.save_admin_ip_list(current_list)
        logger.info("[Admin] Removed '%s' from admin IP list", target)
        rem_choices = cls.get_admin_ip_remove_choices()
        new_val = rem_choices[0] if rem_choices and "無可移除" not in rem_choices[0] else ""
        return cls.build_admin_ip_list_html(), gr.update(choices=rem_choices, value=new_val), f"✅ 已將 IP '{target}' 從管理員名單中移除"

    @classmethod
    def build_admin_hw_dashboard_html(cls) -> str:
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

    @classmethod
    def build_admin_queue_html(cls) -> str:
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

    @classmethod
    def build_admin_devices_html(cls) -> str:
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

    @classmethod
    def get_admin_device_filter_choices(cls) -> List[str]:
        summaries = task_manager.get_connected_devices_summary()
        dev_ids = [s["device_id"] for s in summaries if s.get("device_id")]
        return ["全部裝置"] + dev_ids

    @classmethod
    def get_admin_tasks_dropdown_choices(cls, device_filter: str = "全部裝置", status_filter: str = "全部狀態") -> List[Tuple[str, str]]:
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

    @classmethod
    def on_toggle_server_status(cls, request: gr.Request = None):
        if not cls.is_super_user(request):
            return gr.update(), gr.update(), "⚠️ 權限不足，僅限本機管理員操作"
        cur = get_server_status()
        new_status = SERVER_STATUS_UPDATING if cur == SERVER_STATUS_OK else SERVER_STATUS_OK
        set_server_status(new_status)
        btn_text = "切換為維護模式" if new_status == SERVER_STATUS_OK else "恢復正常服務"
        badge_html = cls.build_admin_status_badge()
        msg = f"✅ 已成功切換為：{'🟢 正常服務中' if new_status == SERVER_STATUS_OK else '🔧 伺服器維護/更新中'}"
        return badge_html, gr.update(value=btn_text), msg

    @classmethod
    def on_free_vram(cls, request: gr.Request = None):
        if not cls.is_super_user(request):
            return "⚠️ 權限不足，僅限本機管理員操作"
        ok, msg = free_comfyui_memory()
        return msg

    @classmethod
    def on_restart_backend(cls, request: gr.Request = None):
        if not cls.is_super_user(request):
            return "⚠️ 權限不足，僅限本機管理員操作"
        stop_comfyui_backend()
        time.sleep(1)
        ok, msg = start_comfyui_backend()
        return msg

    @classmethod
    def on_cancel_current_task(cls, request: gr.Request = None):
        if not cls.is_super_user(request):
            return cls.build_admin_queue_html(), "⚠️ 權限不足"
        q = get_comfyui_queue_status()
        running = q.get("running", [])
        if running and len(running[0]) > 1:
            pid = running[0][1]
            interrupt_execution(pid)
            time.sleep(0.5)
            return cls.build_admin_queue_html(), f"🛑 已送出中斷請求 (Prompt ID: {pid[:8]})"
        return cls.build_admin_queue_html(), "目前無正在執行的生成任務"

    @classmethod
    def on_clear_queue(cls, request: gr.Request = None):
        if not cls.is_super_user(request):
            return cls.build_admin_queue_html(), "⚠️ 權限不足"
        ok, msg = clear_comfyui_queue()
        time.sleep(0.5)
        return cls.build_admin_queue_html(), msg

    @classmethod
    def on_select_admin_task(cls, selected_task_id: str, request: gr.Request = None):
        if not cls.is_super_user(request):
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

    @classmethod
    def on_delete_admin_task(cls, selected_task_id: str, device_filter: str, status_filter: str, request: gr.Request = None):
        if not cls.is_super_user(request):
            return gr.update(), None, "⚠️ 權限不足", gr.update()
        if not selected_task_id:
            choices = cls.get_admin_tasks_dropdown_choices(device_filter, status_filter)
            return gr.update(choices=choices), None, "請選擇上方任務", gr.update()

        task_manager.delete_task(selected_task_id, is_admin=True)
        choices = cls.get_admin_tasks_dropdown_choices(device_filter, status_filter)
        new_value = choices[0][1] if choices and choices[0][1] else ""

        dev_choices = cls.get_admin_device_filter_choices()
        if new_value:
            new_video, new_info = cls.on_select_admin_task(new_value, request)
            return gr.update(choices=choices, value=new_value), new_video, new_info, gr.update(choices=dev_choices)
        return gr.update(choices=choices, value=""), None, "✅ 任務已成功刪除", gr.update(choices=dev_choices)

    @classmethod
    def on_clean_failed_tasks(cls, device_filter: str, status_filter: str, request: gr.Request = None):
        if not cls.is_super_user(request):
            return gr.update(), None, "⚠️ 權限不足", gr.update()
        count = task_manager.delete_failed_and_interrupted_tasks()
        choices = cls.get_admin_tasks_dropdown_choices(device_filter, status_filter)
        dev_choices = cls.get_admin_device_filter_choices()
        msg = f"🧹 已清除 {count} 個失敗或中斷的任務"
        return gr.update(choices=choices, value=""), None, msg, gr.update(choices=dev_choices)

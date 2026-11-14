"""
Administrator authorization, IP whitelist management, and backend maintenance supervisor.
"""
import os
import json
import time
import socket
import subprocess
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
    get_system_thresholds,
    set_system_thresholds,
    ADMIN_PC_SHUTDOWN_DELAY_S,
)
from core.comfy_client import (
    free_comfyui_memory,
    start_comfyui_backend,
    stop_comfyui_backend,
    get_system_dashboard_data,
    get_comfyui_queue_status,
    interrupt_execution,
    clear_comfyui_queue,
)
from task_manager import task_manager
from ui_text import (
    ADMIN_BADGE_OK_HTML,
    ADMIN_BADGE_UPDATING_HTML,
    ADMIN_CANCEL_FAIL_MSG,
    ADMIN_CANCEL_NONE_MSG,
    ADMIN_CANCEL_OK_MSG,
    ADMIN_CLEANED_MSG,
    ADMIN_DEVICES_EMPTY_HTML,
    ADMIN_DEVICES_THEAD_HTML,
    ADMIN_FILTER_ALL_DEVICES,
    ADMIN_FILTER_ALL_STATUS,
    ADMIN_HW_SUB_FREE,
    ADMIN_HW_SUB_DISK,
    ADMIN_HW_SUB_GPU,
    ADMIN_HW_TITLE_DISK,
    ADMIN_HW_TITLE_GPU,
    ADMIN_HW_TITLE_RAM,
    ADMIN_HW_TITLE_VRAM,
    ADMIN_HW_VAL_DISK,
    ADMIN_HW_VAL_USAGE,
    ADMIN_INTERRUPTED_MSG,
    ADMIN_IP_ADDED_MSG,
    ADMIN_IP_BAD_FORMAT_MSG,
    ADMIN_IP_EMPTY_MSG,
    ADMIN_IP_EXISTS_MSG,
    ADMIN_IP_IS_LOCAL_MSG,
    ADMIN_IP_LIST_HTML,
    ADMIN_IP_LOCAL_CHIPS_HTML,
    ADMIN_IP_NONE_CHIP_HTML,
    ADMIN_IP_CHIP_ADMIN_HTML,
    ADMIN_IP_NOT_IN_LIST_MSG,
    ADMIN_IP_PICK_MSG,
    ADMIN_IP_REMOVE_PLACEHOLDER,
    ADMIN_IP_REMOVED_MSG,
    ADMIN_NO_PERM_LOCAL_MSG,
    ADMIN_NO_PERM_MSG,
    ADMIN_NO_PERM_SHUTDOWN_MSG,
    ADMIN_NO_PERM_CANCEL_MSG,
    ADMIN_NO_PERM_THRESHOLDS_MSG,
    ADMIN_QUEUE_IDLE_HTML,
    ADMIN_QUEUE_NO_TASK_MSG,
    ADMIN_QUEUE_OFFLINE_HTML,
    ADMIN_QUEUE_PENDING_EMPTY_HTML,
    ADMIN_QUEUE_PENDING_HTML,
    ADMIN_QUEUE_RUNNING_HTML,
    ADMIN_RESTART_BUSY_MSG,
    ADMIN_STATE_OK_TEXT,
    ADMIN_SHUTDOWN_OS_NOTICE,
    ADMIN_SHUTDOWN_FAIL_MSG,
    ADMIN_SHUTDOWN_SCHEDULED_MSG,
    ADMIN_STATUS_DONE_LABEL,
    ADMIN_STATUS_FAILED_LABEL,
    ADMIN_STATUS_QUEUED_LABEL,
    ADMIN_STATUS_RUNNING_LABEL,
    ADMIN_TASK_CHOICE_FMT,
    ADMIN_TASK_DETAIL_MD,
    ADMIN_TASK_DELETED_MSG,
    ADMIN_TASK_ICON_DONE,
    ADMIN_TASK_ICON_FAILED,
    ADMIN_TASK_ICON_QUEUED,
    ADMIN_TASK_ICON_RUNNING,
    ADMIN_TASK_MISSING_MSG,
    ADMIN_TASK_PICK_MSG,
    ADMIN_NO_TASKS_PLACEHOLDER,
    ADMIN_RESTORE_OK_BTN,
    ADMIN_TOGGLE_OK_MD,
    ADMIN_TOGGLE_TO_MAINT_BTN,
    ADMIN_THRESHOLDS_SAVED_MD,
    COMMON_MAINT_BTN,
)
from utils.logger import get_logger

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
        if get_server_status() == SERVER_STATUS_OK:
            return ADMIN_BADGE_OK_HTML
        return ADMIN_BADGE_UPDATING_HTML

    @classmethod
    def build_admin_ip_list_html(cls) -> str:
        admin_ips = cls.load_admin_ip_list()
        lan = get_lan_ip()

        default_chips = ADMIN_IP_LOCAL_CHIPS_HTML.format(lan)

        if not admin_ips:
            custom_chips = ADMIN_IP_NONE_CHIP_HTML
        else:
            chips = [ADMIN_IP_CHIP_ADMIN_HTML.format(ip) for ip in admin_ips]
            custom_chips = "".join(chips)

        return ADMIN_IP_LIST_HTML.format(default_chips, custom_chips)

    @classmethod
    def get_admin_ip_remove_choices(cls) -> List[str]:
        ips = cls.load_admin_ip_list()
        return ips if ips else [ADMIN_IP_REMOVE_PLACEHOLDER]

    @classmethod
    def on_add_admin_ip(cls, new_ip: str, request: gr.Request = None):
        if not cls.is_super_user(request):
            return cls.build_admin_ip_list_html(), gr.update(), ADMIN_NO_PERM_MSG

        ip_clean = (new_ip or "").strip()
        if not ip_clean:
            return cls.build_admin_ip_list_html(), gr.update(choices=cls.get_admin_ip_remove_choices()), ADMIN_IP_EMPTY_MSG

        if not cls.is_valid_ip_address(ip_clean):
            return cls.build_admin_ip_list_html(), gr.update(choices=cls.get_admin_ip_remove_choices()), ADMIN_IP_BAD_FORMAT_MSG.format(ip_clean)

        local_defaults = {"127.0.0.1", "::1", "localhost", get_lan_ip()}
        if ip_clean in local_defaults:
            return cls.build_admin_ip_list_html(), gr.update(choices=cls.get_admin_ip_remove_choices()), ADMIN_IP_IS_LOCAL_MSG.format(ip_clean)

        current_list = cls.load_admin_ip_list()
        if ip_clean in current_list:
            return cls.build_admin_ip_list_html(), gr.update(choices=cls.get_admin_ip_remove_choices()), ADMIN_IP_EXISTS_MSG.format(ip_clean)

        current_list.append(ip_clean)
        cls.save_admin_ip_list(current_list)
        logger.info("[Admin] Added '%s' to admin IP list", ip_clean)
        rem_choices = cls.get_admin_ip_remove_choices()
        return cls.build_admin_ip_list_html(), gr.update(choices=rem_choices, value=rem_choices[0] if rem_choices else ""), ADMIN_IP_ADDED_MSG.format(ip_clean)

    @classmethod
    def on_remove_admin_ip(cls, target_ip: str, request: gr.Request = None):
        if not cls.is_super_user(request):
            return cls.build_admin_ip_list_html(), gr.update(), ADMIN_NO_PERM_MSG

        target = (target_ip or "").strip()
        if not target or "無可移除" in target:  # 清單佔選的內部偵測標記（技術協定，非文案）
            return cls.build_admin_ip_list_html(), gr.update(choices=cls.get_admin_ip_remove_choices()), ADMIN_IP_PICK_MSG

        current_list = cls.load_admin_ip_list()
        if target not in current_list:
            rem_choices = cls.get_admin_ip_remove_choices()
            return cls.build_admin_ip_list_html(), gr.update(choices=rem_choices), ADMIN_IP_NOT_IN_LIST_MSG.format(target)

        current_list.remove(target)
        cls.save_admin_ip_list(current_list)
        logger.info("[Admin] Removed '%s' from admin IP list", target)
        rem_choices = cls.get_admin_ip_remove_choices()
        new_val = rem_choices[0] if rem_choices and "無可移除" not in rem_choices[0] else ""
        return cls.build_admin_ip_list_html(), gr.update(choices=rem_choices, value=new_val), ADMIN_IP_REMOVED_MSG.format(target)

    # ── 後端啟動資源門檻設定（Spec 2026-11-01 任務 2）────────────────────────
    # RAM／GPU 使用率／VRAM 三項門檻，管理員在頁面直接調整；
    # 持久化與範圍驗證在 config.set_system_thresholds，儲存後立即生效。

    @classmethod
    def reload_system_thresholds(cls):
        """從儲存設定重抓三個滑桿現值（掛在 blocks.load，規避建置期快照問題）。"""
        t = get_system_thresholds()
        return (
            gr.update(value=t["min_ram_gb"]),
            gr.update(value=t["max_gpu_util"]),
            gr.update(value=t["min_vram_gb"]),
        )

    @classmethod
    def on_save_system_thresholds(cls, min_ram_gb, max_gpu_util, min_vram_gb, request: gr.Request = None) -> str:
        if not cls.is_super_user(request):
            return ADMIN_NO_PERM_THRESHOLDS_MSG
        ok, msg = set_system_thresholds(min_ram_gb, max_gpu_util, min_vram_gb)
        if not ok:
            return f"❌ {msg}"
        t = get_system_thresholds()
        logger.info(
            "[Admin] Startup resource thresholds updated: RAM>=%gGB, GPU<=%g%%, VRAM>=%gGB",
            t["min_ram_gb"], t["max_gpu_util"], t["min_vram_gb"],
        )
        return ADMIN_THRESHOLDS_SAVED_MD.format(
            msg,
            "{:g}".format(t["min_ram_gb"]),
            "{:g}".format(t["max_gpu_util"]),
            "{:g}".format(t["min_vram_gb"]),
        )

    @classmethod
    def build_admin_hw_dashboard_html(cls) -> str:
        d = get_system_dashboard_data()
        t = get_system_thresholds()
        card_style = (
            'background: #f8fafc; border: 1.5px solid #e2e8f0; border-radius: 10px; '
            'padding: 14px 18px; flex: 1; min-width: 180px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);'
        )
        title_style = 'font-size: 0.85rem; font-weight: 600; color: #64748b; margin-bottom: 6px;'
        val_style = 'font-size: 1.25rem; font-weight: 700; color: #0f172a; margin-bottom: 4px;'
        sub_style = 'font-size: 0.8rem; color: #94a3b8;'

        ram_sub = ADMIN_HW_SUB_FREE.format(d['ram_available_gb'], d['ram_percent'], "{:g}".format(t['min_ram_gb']))
        vram_sub = ADMIN_HW_SUB_FREE.format(d['vram_free_gb'], d['vram_percent'], "{:g}".format(t['min_vram_gb']))
        gpu_sub = ADMIN_HW_SUB_GPU.format("{:g}".format(t['max_gpu_util']))
        disk_val = ADMIN_HW_VAL_DISK.format(d['disk_free_gb'])
        disk_sub = ADMIN_HW_SUB_DISK.format(d['disk_total_gb'], d['disk_percent'])

        return f"""
        <div style="display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 8px;">
            <div style="{card_style}">
                <div style="{title_style}">{ADMIN_HW_TITLE_RAM}</div>
                <div style="{val_style}">{ADMIN_HW_VAL_USAGE.format(d['ram_used_gb'], d['ram_total_gb'])}</div>
                <div style="{sub_style}">{ram_sub}</div>
            </div>
            <div style="{card_style}">
                <div style="{title_style}">{ADMIN_HW_TITLE_GPU}</div>
                <div style="{val_style}">{d['gpu_util_pct']}%</div>
                <div style="{sub_style}">{gpu_sub}</div>
            </div>
            <div style="{card_style}">
                <div style="{title_style}">{ADMIN_HW_TITLE_VRAM}</div>
                <div style="{val_style}">{ADMIN_HW_VAL_USAGE.format(d['vram_used_gb'], d['vram_total_gb'])}</div>
                <div style="{sub_style}">{vram_sub}</div>
            </div>
            <div style="{card_style}">
                <div style="{title_style}">{ADMIN_HW_TITLE_DISK}</div>
                <div style="{val_style}">{disk_val}</div>
                <div style="{sub_style}">{disk_sub}</div>
            </div>
        </div>
        """

    @classmethod
    def build_admin_queue_html(cls) -> str:
        q = get_comfyui_queue_status()
        if not q["online"]:
            return ADMIN_QUEUE_OFFLINE_HTML

        running = q.get("running", [])
        pending = q.get("pending", [])

        running_html = ""
        if running:
            p_id = running[0][1] if len(running[0]) > 1 else str(running[0])
            running_html = ADMIN_QUEUE_RUNNING_HTML.format(p_id)
        else:
            running_html = ADMIN_QUEUE_IDLE_HTML

        pending_html = ""
        if pending:
            items = []
            for idx, item in enumerate(pending, 1):
                pid = item[1] if len(item) > 1 else str(item)
                items.append(f"<li>#{idx} - <code>{pid}</code></li>")
            pending_html = ADMIN_QUEUE_PENDING_HTML.format(len(pending), "".join(items))
        else:
            pending_html = ADMIN_QUEUE_PENDING_EMPTY_HTML

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
            return ADMIN_DEVICES_EMPTY_HTML

        rows = []
        for s in summaries:
            t_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["last_active"]))
            rows.append(
                f'<tr style="border-bottom: 1px solid #f1f5f9;">'
                f'<td style="padding: 8px 12px; font-weight: 600;"><code>{s["device_id"]}</code></td>'
                f'<td style="padding: 8px 12px;"><code>{s.get("ip") or "—"}</code></td>'
                f'<td style="padding: 8px 12px;">{s["task_count"]}</td>'
                f'<td style="padding: 8px 12px;">{s["completed_count"]}</td>'
                f'<td style="padding: 8px 12px; color: #64748b;">{t_str}</td>'
                f'</tr>'
            )

        return (
            '<table style="width: 100%; border-collapse: collapse; background: #ffffff; '
            'border: 1.5px solid #e2e8f0; border-radius: 8px; overflow: hidden; font-size: 0.9rem;">\n'
            "            " + ADMIN_DEVICES_THEAD_HTML + "\n"
            "            <tbody>\n                " + "".join(rows) + "\n            </tbody>\n"
            "        </table>"
        )

    @classmethod
    def get_admin_device_filter_choices(cls) -> List[str]:
        summaries = task_manager.get_connected_devices_summary()
        dev_ids = [s["device_id"] for s in summaries if s.get("device_id")]
        return [ADMIN_FILTER_ALL_DEVICES] + dev_ids

    @classmethod
    def get_admin_tasks_dropdown_choices(cls, device_filter: str = ADMIN_FILTER_ALL_DEVICES,
                                         status_filter: str = ADMIN_FILTER_ALL_STATUS) -> List[Tuple[str, str]]:
        tasks = task_manager.get_all_tasks(device_filter, status_filter)
        if not tasks:
            return [(ADMIN_NO_TASKS_PLACEHOLDER, "")]

        choices = []
        for t in tasks:
            t_str = time.strftime("%m/%d %H:%M", time.localtime(t.created_at))
            short_prompt = (t.prompt[:25] + "...") if len(t.prompt) > 25 else t.prompt
            short_dev = t.device_id.split("_")[-1][:6] if "_" in t.device_id else t.device_id[:6]
            status_icon = (ADMIN_TASK_ICON_DONE if t.status == "completed"
                           else ADMIN_TASK_ICON_RUNNING if t.status == "running"
                           else ADMIN_TASK_ICON_QUEUED if t.status == "queued"
                           else ADMIN_TASK_ICON_FAILED)
            label = ADMIN_TASK_CHOICE_FMT.format(status_icon, t.task_type, short_dev, t_str, short_prompt)
            choices.append((label, t.task_id))
        return choices

    @classmethod
    def apply_task_filter(cls, device_filter: str = ADMIN_FILTER_ALL_DEVICES, status_filter: str = ADMIN_FILTER_ALL_STATUS,
                          current_task_id: str = None, request: gr.Request = None):
        """
        Filter-driven refresh of the「選取歷史任務」+「篩選裝置」dropdowns.
        Returns (task_dropdown_update, device_filter_update). MUST be gr.update(choices=…)
        (not the raw choices list — gradio reads a bare output as the dropdown's *value*,
        which left the menu stuck on the original choices and raised
        "'…' is not in the list of choices" for the tuple-list value. Bug 2026-11-01.)
        - task value stays put when it survives the filter, else snaps to the first
          valid choice (never outside `choices`).
        - device choices are re-scanned on every apply so devices created after the
          page was built show up without a page reload (second output).
        """
        if not cls.is_super_user(request):
            return gr.update(), gr.update()
        choices = cls.get_admin_tasks_dropdown_choices(device_filter, status_filter)
        ids = [c[1] for c in choices]
        new_value = current_task_id if current_task_id in ids else ids[0]

        dev_choices = cls.get_admin_device_filter_choices()
        dev_value = device_filter if device_filter in dev_choices else ADMIN_FILTER_ALL_DEVICES
        return gr.update(choices=choices, value=new_value), gr.update(choices=dev_choices, value=dev_value)

    @classmethod
    def on_toggle_server_status(cls, request: gr.Request = None):
        if not cls.is_super_user(request):
            return gr.update(), gr.update(), ADMIN_NO_PERM_LOCAL_MSG
        cur = get_server_status()
        new_status = SERVER_STATUS_UPDATING if cur == SERVER_STATUS_OK else SERVER_STATUS_OK
        set_server_status(new_status)
        btn_text = ADMIN_TOGGLE_TO_MAINT_BTN if new_status == SERVER_STATUS_OK else ADMIN_RESTORE_OK_BTN
        badge_html = cls.build_admin_status_badge()
        state_label = ADMIN_STATE_OK_TEXT if new_status == SERVER_STATUS_OK else COMMON_MAINT_BTN
        msg = ADMIN_TOGGLE_OK_MD.format(state_label)
        return badge_html, gr.update(value=btn_text), msg

    # ── 電腦電源控制（Spec 2026-11-02 第 2 輪任務 1）─────────────────────────
    # 關機走 Windows 內建 shutdown 指令：先排定 N 秒倒數（期間系統会有倒數提示），
    # 讓管理員有一段反悔窗口可用「取消關機」(shutdown /a) 中止。super-user 門護。

    @classmethod
    def on_shutdown_pc(cls, request: gr.Request = None) -> str:
        if not cls.is_super_user(request):
            return ADMIN_NO_PERM_SHUTDOWN_MSG
        delay = ADMIN_PC_SHUTDOWN_DELAY_S
        try:
            subprocess.Popen(
                ["shutdown", "/s", "/t", str(delay), "/c", ADMIN_SHUTDOWN_OS_NOTICE.format(delay)],
            )
        except Exception as e:
            logger.error("[Admin] PC shutdown scheduling failed: %s", e)
            return ADMIN_SHUTDOWN_FAIL_MSG.format(e)
        logger.warning("[Admin] PC shutdown scheduled in %ss by admin request", delay)
        return ADMIN_SHUTDOWN_SCHEDULED_MSG.format(delay)

    @classmethod
    def on_cancel_shutdown(cls, request: gr.Request = None) -> str:
        if not cls.is_super_user(request):
            return ADMIN_NO_PERM_CANCEL_MSG
        try:
            result = subprocess.run(
                ["shutdown", "/a"], capture_output=True, text=True, timeout=5,
            )
        except Exception as e:
            logger.error("[Admin] shutdown abort failed: %s", e)
            return ADMIN_CANCEL_FAIL_MSG.format(e)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return ADMIN_CANCEL_NONE_MSG.format("（" + detail + "）" if detail else "")
        logger.warning("[Admin] Scheduled PC shutdown aborted by admin request")
        return ADMIN_CANCEL_OK_MSG

    @classmethod
    def on_free_vram(cls, request: gr.Request = None):
        if not cls.is_super_user(request):
            return ADMIN_NO_PERM_LOCAL_MSG
        ok, msg = free_comfyui_memory()
        return msg

    @classmethod
    def on_restart_backend(cls, request: gr.Request = None):
        if not cls.is_super_user(request):
            return ADMIN_NO_PERM_LOCAL_MSG
        # SAFEGUARD: never kill the backend while generation jobs are queued/running —
        # it orphans the active worker and silently discards everyone's queued work.
        active_count = task_manager.get_active_task_count()
        if active_count:
            return ADMIN_RESTART_BUSY_MSG.format(active_count)
        stop_comfyui_backend()
        time.sleep(1)
        ok, msg = start_comfyui_backend()
        return msg

    @classmethod
    def on_cancel_current_task(cls, request: gr.Request = None):
        if not cls.is_super_user(request):
            return cls.build_admin_queue_html(), ADMIN_NO_PERM_MSG
        q = get_comfyui_queue_status()
        running = q.get("running", [])
        if running and len(running[0]) > 1:
            pid = running[0][1]
            interrupt_execution(pid)
            time.sleep(0.5)
            return cls.build_admin_queue_html(), ADMIN_INTERRUPTED_MSG.format(pid[:8])
        return cls.build_admin_queue_html(), ADMIN_QUEUE_NO_TASK_MSG

    @classmethod
    def on_clear_queue(cls, request: gr.Request = None):
        if not cls.is_super_user(request):
            return cls.build_admin_queue_html(), ADMIN_NO_PERM_MSG
        ok, msg = clear_comfyui_queue()
        time.sleep(0.5)
        return cls.build_admin_queue_html(), msg

    @classmethod
    def on_select_admin_task(cls, selected_task_id: str, request: gr.Request = None):
        if not cls.is_super_user(request):
            return None, ADMIN_NO_PERM_MSG
        if not selected_task_id:
            return None, ADMIN_TASK_PICK_MSG
        task = task_manager.get_task(selected_task_id)
        if not task:
            return None, ADMIN_TASK_MISSING_MSG

        video_path = task.video_path if task.video_path and os.path.exists(task.video_path) else None
        t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task.created_at))
        status_str = (ADMIN_STATUS_DONE_LABEL if task.status == "completed"
                      else ADMIN_STATUS_RUNNING_LABEL if task.status == "running"
                      else ADMIN_STATUS_QUEUED_LABEL if task.status == "queued"
                      else ADMIN_STATUS_FAILED_LABEL)

        params = task.params or {}
        w = params.get("width", "-")
        h = params.get("height", "-")
        seed = params.get("seed", "-")
        duration = params.get("duration", "-")

        info_md = ADMIN_TASK_DETAIL_MD.format(
            task.task_id, task.device_id, task.task_type, status_str, task.message,
            t_str, task.elapsed, w, h, seed, duration,
            os.path.basename(task.video_path) if task.video_path else "無",
            task.prompt,
        )
        return video_path, info_md

    @classmethod
    def on_delete_admin_task(cls, selected_task_id: str, device_filter: str, status_filter: str, request: gr.Request = None):
        if not cls.is_super_user(request):
            return gr.update(), None, ADMIN_NO_PERM_MSG, gr.update()
        if not selected_task_id:
            choices = cls.get_admin_tasks_dropdown_choices(device_filter, status_filter)
            return gr.update(choices=choices), None, ADMIN_TASK_PICK_MSG, gr.update()

        task_manager.delete_task(selected_task_id, is_admin=True)
        choices = cls.get_admin_tasks_dropdown_choices(device_filter, status_filter)
        new_value = choices[0][1] if choices and choices[0][1] else ""

        dev_choices = cls.get_admin_device_filter_choices()
        if new_value:
            new_video, new_info = cls.on_select_admin_task(new_value, request)
            return gr.update(choices=choices, value=new_value), new_video, new_info, gr.update(choices=dev_choices)
        return gr.update(choices=choices, value=""), None, ADMIN_TASK_DELETED_MSG, gr.update(choices=dev_choices)

    @classmethod
    def on_clean_failed_tasks(cls, device_filter: str, status_filter: str, request: gr.Request = None):
        if not cls.is_super_user(request):
            return gr.update(), None, ADMIN_NO_PERM_MSG, gr.update()
        count = task_manager.delete_failed_and_interrupted_tasks()
        choices = cls.get_admin_tasks_dropdown_choices(device_filter, status_filter)
        dev_choices = cls.get_admin_device_filter_choices()
        msg = ADMIN_CLEANED_MSG.format(count)
        # value must stay inside choices (empty-list case = placeholder with value ""),
        # otherwise gradio rejects the selection with "not in the list of choices".
        return gr.update(choices=choices, value=choices[0][1]), None, msg, gr.update(choices=dev_choices)

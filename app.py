"""
AI WebUI Application Entry Point.

Routing refactor (Spec 2026-10-31, 方案A): the single mega Blocks in this file
was split into three mounted pages living in the `webapp/` package:

    /          -> last-used-page redirector
    /minimax   -> webapp/pages_minimax.py
    /upscaler  -> webapp/pages_upscaler.py
    /strata    -> webapp/pages_strata.py
    /<module>/<tab> -> pseudo tab deep links (see webapp/server.py)

This file stays a stable façade: it re-exports every name tests/e2e have always
imported from `app`, and owns `launch_webui` (uvicorn assembly + port guard).
Dev hot-reload is no longer `python -m gradio app.py`; run.bat sets
WEBUI_DEV_RELOAD=1 and uvicorn's reloader restarts the ASGI app on file changes.
"""
import os
import sys
import time
import threading

import gradio as gr
import uvicorn

from config import (
    COMFY_SERVER_URL,
    WEBUI_HOST,
    WEBUI_PORT,
    OUTPUT_DIR,
    get_lan_ip,
    ASPECT_RATIOS,
    QUALITY_CHOICES,
)
from task_manager import task_manager
from utils.logger import get_logger

from core.session_context import SessionContext, DEVICE_STORAGE_SECRET
from core.admin_manager import AdminManager
from core.port_guardian import PortGuardian

from components.styles import CUSTOM_CSS, CUSTOM_HEAD_JS
from components.header import build_header_html
from components.media_player import build_progress_html
from components.video_params import on_resolution_change
from components.history_gallery import (
    get_history_dropdown_choices,
    on_select_history_item,
    on_delete_history_item,
)

from views.minimax.tabs import on_first_frame_change
from views.minimax.tabs.i2v_tab import handle_i2v_generate
from views.minimax.tabs.t2v_tab import handle_t2v_generate
from views.minimax.tabs.r2v_tab import handle_r2v_generate
from views.upscaler.view import handle_upscale_generate

from webapp.shell import APP_THEME, TAB_SEGMENTS
from webapp.server import PAGES, create_asgi_app

logger = get_logger("App")
lan_ip = get_lan_ip()

# --- Backward-compatible re-exports (tests/e2e import these from `app`) ------
PAGE_MINIMAX = PAGES["minimax"]
PAGE_UPSCALER = PAGES["upscaler"]
PAGE_STRATA = PAGES["strata"]

demo = PAGE_MINIMAX.blocks  # legacy name: the primary (minimax) Blocks
device_id_state = PAGE_MINIMAX.device_id_state
session_task_state = PAGE_MINIMAX.session_task_state
history_dropdown = PAGE_MINIMAX.history_dropdown
all_restored_outputs = PAGE_MINIMAX.all_restored_outputs

restore_device_state = PAGE_MINIMAX.restore_device_state
switch_manual_device_id = PAGE_MINIMAX.switch_manual_device_id
poll_active_task_progress = PAGE_MINIMAX.poll_active_task_progress

i2v_aspect_ratio = PAGE_MINIMAX.i2v_aspect_ratio
i2v_quality_level = PAGE_MINIMAX.i2v_quality_level
i2v_sampler = PAGE_MINIMAX.i2v_sampler
i2v_scheduler = PAGE_MINIMAX.i2v_scheduler
t2v_aspect_ratio = PAGE_MINIMAX.t2v_aspect_ratio
t2v_quality_level = PAGE_MINIMAX.t2v_quality_level
t2v_sampler = PAGE_MINIMAX.t2v_sampler
t2v_scheduler = PAGE_MINIMAX.t2v_scheduler
r2v_aspect_ratio = PAGE_MINIMAX.r2v_aspect_ratio
r2v_quality_level = PAGE_MINIMAX.r2v_quality_level
r2v_sampler = PAGE_MINIMAX.r2v_sampler
r2v_scheduler = PAGE_MINIMAX.r2v_scheduler

# per-device completion/status dedup trackers (patchable surfaces kept importable)
from webapp.pages_minimax import _device_last_reported_completed, _device_last_status_html


def handle_stop_generate(device_id: str):
    """Halts active generation tasks for the requesting device."""
    interrupted = task_manager.interrupt_device_tasks(device_id=device_id, module="minimax")
    logger.info("[App] User stopped generation for device '%s'. Interrupted: %s", device_id, interrupted)
    return (
        build_progress_html("⚠️ 任務已被手動中斷"),
        gr.update(visible=True),
        gr.update(visible=False),
    )


# Admin operations delegators for backward-compatibility
is_super_user = AdminManager.is_super_user
check_super_user_visibility = AdminManager.check_super_user_visibility
build_admin_status_badge = AdminManager.build_admin_status_badge
build_admin_hw_dashboard_html = AdminManager.build_admin_hw_dashboard_html
build_admin_queue_html = AdminManager.build_admin_queue_html
build_admin_devices_html = AdminManager.build_admin_devices_html
get_admin_device_filter_choices = AdminManager.get_admin_device_filter_choices
get_admin_tasks_dropdown_choices = AdminManager.get_admin_tasks_dropdown_choices
on_toggle_server_status = AdminManager.on_toggle_server_status
on_select_admin_task = AdminManager.on_select_admin_task
on_delete_admin_task = AdminManager.on_delete_admin_task
on_clean_failed_tasks = AdminManager.on_clean_failed_tasks
load_admin_ip_list = AdminManager.load_admin_ip_list
save_admin_ip_list = AdminManager.save_admin_ip_list
build_admin_ip_list_html = AdminManager.build_admin_ip_list_html
get_admin_ip_remove_choices = AdminManager.get_admin_ip_remove_choices
on_add_admin_ip = AdminManager.on_add_admin_ip
on_remove_admin_ip = AdminManager.on_remove_admin_ip


def launch_webui(
    port: int = WEBUI_PORT,
    raise_on_error: bool = False,
    prevent_thread_lock: bool = False,
    quiet: bool = False,
    **launch_kwargs,
):
    """
    Launch the routed WebUI (uvicorn serving webapp.server's FastAPI app).

    prevent_thread_lock=True (used by the e2e harness): starts uvicorn in a
    daemon thread and returns the uvicorn Server handle — set `handle.should_exit
    = True` to stop it. Otherwise blocks until interrupted.
    """
    if PortGuardian.is_port_in_use(port):
        PortGuardian.print_port_conflict_help(port)
        if raise_on_error:
            raise OSError(f"Port {port} is already in use by another process.")
        sys.exit(1)

    # Startup reconciliation: queued/running tasks reloaded from history have no live worker
    # behind them; verify each against ComfyUI once and demote the genuinely-lost ones.
    try:
        task_manager.reconcile_orphaned_tasks()
    except Exception as e:
        logger.warning("Orphaned-task reconciliation failed: %s", e)

    extra_allowed = []
    extra = launch_kwargs.pop("allowed_paths", None)
    if extra:
        extra_allowed = extra if isinstance(extra, list) else [extra]

    print("=" * 60)
    print(f"AI WebUI Multi-Module Platform Starting (Port: {port})...")
    print(f"Local Access: http://127.0.0.1:{port}  (→ 上次使用的頁面)")
    print(f"Pages: /minimax /upscaler /strata   Mobile LAN: http://{lan_ip}:{port}")
    print(f"ComfyUI Backend: {COMFY_SERVER_URL}")
    print("=" * 60)
    logger.info("Starting routed WebUI (uvicorn) on http://%s:%s", WEBUI_HOST, port)

    asgi_app = create_asgi_app(extra_allowed_paths=extra_allowed or None)
    log_level = "warning" if quiet else "info"

    if prevent_thread_lock:
        config = uvicorn.Config(asgi_app, host=WEBUI_HOST, port=port, log_level=log_level, access_log=False)
        server = uvicorn.Server(config)
        threading.Thread(target=server.run, name="WebUI-uvicorn", daemon=True).start()
        deadline = time.time() + 30
        while not server.started and not server.should_exit and time.time() < deadline:
            time.sleep(0.1)
        if not server.started:
            if raise_on_error:
                raise OSError(f"WebUI uvicorn server failed to start on port {port}.")
            sys.exit(1)
        return server

    try:
        uvicorn.run(asgi_app, host=WEBUI_HOST, port=port, log_level=log_level, access_log=False)
        return asgi_app
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            PortGuardian.print_port_conflict_help(port)
            if raise_on_error:
                raise
            sys.exit(1)
        raise


def _run_dev_reload():
    """run.bat path: uvicorn reloader restarts the ASGI app on any .py change.
    (Replaces the old `python -m gradio app.py` watch mode — styles/theme now
    ride the mount calls, so a reload re-applies everything automatically.)"""
    if PortGuardian.is_port_in_use(WEBUI_PORT):
        PortGuardian.print_port_conflict_help(WEBUI_PORT)
        sys.exit(1)
    try:
        task_manager.reconcile_orphaned_tasks()
    except Exception as e:
        logger.warning("Orphaned-task reconciliation failed: %s", e)
    print("=" * 60)
    print(f"AI WebUI Multi-Module Platform (Auto-Reload, Port: {WEBUI_PORT})...")
    print(f"Local Access: http://127.0.0.1:{WEBUI_PORT}   LAN: http://{lan_ip}:{WEBUI_PORT}")
    print("Pages: /minimax  /upscaler  /strata")
    print("=" * 60)
    uvicorn.run(
        "webapp.server:create_asgi_app",
        factory=True,
        host=WEBUI_HOST,
        port=WEBUI_PORT,
        reload=True,
        reload_dirs=[os.path.dirname(os.path.abspath(__file__))],
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    if os.environ.get("WEBUI_DEV_RELOAD") == "1":
        _run_dev_reload()
    else:
        launch_webui()

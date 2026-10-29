"""
AI WebUI Application Entry Point.
Modular, Object-Oriented multi-service interface hosting:
1. ComfyUI MiniMax-H3 Video Generator
2. ComfyUI Video Resolution Upscaler
3. Strata Qwen3.8-flash-next LLM
"""
import os
import time
import uuid
from typing import Optional, Tuple, Any, List
import gradio as gr

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
from logger import get_logger

from core.session_context import SessionContext, DEVICE_STORAGE_SECRET
from core.admin_manager import AdminManager
from core.port_guardian import PortGuardian

from components.styles import CUSTOM_CSS, CUSTOM_HEAD_JS
from components.header import HeaderComponent, build_header_html
from components.dashboard_sidebar import (
    DashboardNavComponent,
    MODULE_MINIMAX,
    MODULE_UPSCALER,
    MODULE_STRATA,
)
from components.comfy_toolbar import ComfyToolbarComponent
from components.media_player import build_progress_html
from components.video_params import on_resolution_change
from components.history_gallery import (
    get_history_dropdown_choices,
    on_select_history_item,
    on_delete_history_item,
)

from views.minimax.view import MiniMaxView
from views.minimax.tabs import (
    I2VTab,
    T2VTab,
    R2VTab,
    on_first_frame_change,
)
from views.minimax.tabs.i2v_tab import handle_i2v_generate
from views.minimax.tabs.t2v_tab import handle_t2v_generate
from views.minimax.tabs.r2v_tab import handle_r2v_generate
from views.upscaler.view import UpscalerView, handle_upscale_generate
from views.strata.view import StrataView
from views.admin.view import AdminPanelView

logger = get_logger("App")
lan_ip = get_lan_ip()

# --- Shared Tracking State for Device Notifications ---
_device_last_reported_completed: dict = {}
_device_last_status_html: dict = {}


def handle_stop_generate(device_id: str):
    """Halts active generation tasks for the requesting device."""
    interrupted = task_manager.interrupt_device_tasks(device_id=device_id)
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


# --- Build UI Layout ---
with gr.Blocks(title="MiniMax-H3 AI Video WebUI") as demo:
    # 1. Strictly isolated persistent states per browser/device LocalStorage
    session_ctx = SessionContext().render()
    device_id_state = session_ctx.device_id_state
    session_task_state = session_ctx.session_task_state

    # 2. Header Banner & Device ID Controls
    header_comp = HeaderComponent().render()
    header_html = header_comp.header_html
    edit_id_btn = header_comp.edit_id_btn
    edit_id_row = header_comp.edit_id_row
    manual_id_input = header_comp.manual_id_input
    save_id_btn = header_comp.save_id_btn
    cancel_id_btn = header_comp.cancel_id_btn

    # 3. Top-Left Expandable Dashboard (Controls switching across the 3 core modules)
    dashboard_comp = DashboardNavComponent().render()

    # 4. ComfyUI Backend Control Toolbar
    toolbar_comp = ComfyToolbarComponent().render()

    # 5. Core Views Construction (OOP Modularized with dedicated Admin Tabs)
    minimax_view = MiniMaxView()
    upscaler_view = UpscalerView()
    strata_view = StrataView()

    minimax_container = minimax_view.render(session_ctx)
    upscaler_container = upscaler_view.render(session_ctx)
    strata_container = strata_view.render(session_ctx)

    # Collect Admin tabs across all views (Layered within each module's tab bar)
    admin_tab = minimax_view.admin_tab.tab
    all_admin_tabs = [
        minimax_view.admin_tab.tab,
        upscaler_view.admin_tab.tab,
        strata_view.admin_tab.tab,
    ]

    # Dropdown aliases for direct component inspection
    i2v_aspect_ratio = minimax_view.i2v_tab.params_card.aspect_ratio
    i2v_quality_level = minimax_view.i2v_tab.params_card.quality_level
    i2v_sampler = minimax_view.i2v_tab.params_card.sampler
    i2v_scheduler = minimax_view.i2v_tab.params_card.scheduler

    t2v_aspect_ratio = minimax_view.t2v_tab.params_card.aspect_ratio
    t2v_quality_level = minimax_view.t2v_tab.params_card.quality_level
    t2v_sampler = minimax_view.t2v_tab.params_card.sampler
    t2v_scheduler = minimax_view.t2v_tab.params_card.scheduler

    r2v_aspect_ratio = minimax_view.r2v_tab.params_card.aspect_ratio
    r2v_quality_level = minimax_view.r2v_tab.params_card.quality_level
    r2v_sampler = minimax_view.r2v_tab.params_card.sampler
    r2v_scheduler = minimax_view.r2v_tab.params_card.scheduler

    # 6. Dashboard Switching Logic
    def switch_active_module(choice: str):
        is_minimax = (choice == MODULE_MINIMAX)
        is_upscaler = (choice == MODULE_UPSCALER)
        is_strata = (choice == MODULE_STRATA)
        return (
            gr.update(visible=is_minimax),
            gr.update(visible=is_upscaler),
            gr.update(visible=is_strata),
        )

    dashboard_comp.bind_module_change(
        switch_active_module,
        outputs=[minimax_container, upscaler_container, strata_container],
    )

    # 7. Auto poll timer for backend status and active task polling
    backend_poll_timer = gr.Timer(value=0.5)
    task_poll_timer = gr.Timer(value=1.0)
    toolbar_comp.register_events(timer=backend_poll_timer)
    header_comp.register_toggle_events()

    # 8. Register events for each module (including each module's admin tab)
    minimax_view.register_events(session_ctx)
    upscaler_view.register_events(session_ctx, poll_timer=task_poll_timer)
    strata_view.register_events(session_ctx)

    # 9. Super User dynamic visibility on page load (updates all admin tabs across views)
    def update_all_admin_tabs_visibility(request: gr.Request):
        is_admin = AdminManager.is_super_user(request)
        return [gr.update(visible=is_admin) for _ in all_admin_tabs]

    demo.load(
        update_all_admin_tabs_visibility,
        outputs=all_admin_tabs,
    )

    # 10. Backward-compatible state restoration outputs (55 components)
    history_dropdown = minimax_view.history_gallery.dropdown
    all_restored_outputs = [
        device_id_state,
        session_task_state,
        header_html,
        history_dropdown,
        *minimax_view.get_restore_components(),
        *minimax_view.get_action_buttons(),
    ]

    def restore_device_state(stored_device_id: Optional[str], stored_task_id: Optional[str]):
        """Restores inputs, parameters, and generated video for THIS specific device."""
        if not stored_device_id:
            stored_device_id = f"dev_{uuid.uuid4().hex[:6]}"

        task = task_manager.get_task(stored_task_id, device_id=stored_device_id) or task_manager.get_latest_task_for_device(stored_device_id)
        logger.info("[Session] Device connected/restoring: %s (Active task: %s)", stored_device_id, task.task_id if task else "None")

        content_updates, btn_updates = minimax_view.restore_state(task, stored_device_id)
        history_choices = get_history_dropdown_choices(stored_device_id)
        header = build_header_html(device_id=stored_device_id)
        active_task_id = task.task_id if task else stored_task_id

        return (
            stored_device_id,
            active_task_id,
            header,
            gr.update(choices=history_choices),
            *content_updates,
            *btn_updates,
        )

    def switch_manual_device_id(custom_id: str, current_device_id: str, session_task_id: str):
        """Allows user to switch to a remembered device ID without exposing others."""
        val = (custom_id or "").strip()
        if not val:
            return (gr.update(visible=False), *restore_device_state(current_device_id, session_task_id))
        target_id = val if val.startswith("dev_") else f"dev_{val}"
        logger.info("[Session] Device ID manual switch: '%s' -> '%s'", current_device_id, target_id)
        return (gr.update(visible=False), *restore_device_state(target_id, None))

    def poll_active_task_progress(stored_device_id: Optional[str], stored_task_id: Optional[str]):
        """Polled every 1s to detect background completion or progress without full refresh."""
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

        if task.status in ("completed", "failed", "interrupted"):
            if _device_last_reported_completed.get(stored_device_id) == task.task_id:
                return (
                    gr.update(),
                    gr.update(), gr.update(),
                    gr.update(), gr.update(),
                    gr.update(), gr.update(),
                    gr.update(),
                    *default_btns,
                )

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

    # 11. Connect recovery and page reload triggers
    demo.load(
        restore_device_state,
        inputs=[device_id_state, session_task_state],
        outputs=all_restored_outputs,
    )

    minimax_view.i2v_tab.player_card.recover_btn.click(
        restore_device_state,
        inputs=[device_id_state, session_task_state],
        outputs=all_restored_outputs,
    )
    minimax_view.t2v_tab.player_card.recover_btn.click(
        restore_device_state,
        inputs=[device_id_state, session_task_state],
        outputs=all_restored_outputs,
    )
    minimax_view.r2v_tab.player_card.recover_btn.click(
        restore_device_state,
        inputs=[device_id_state, session_task_state],
        outputs=all_restored_outputs,
    )

    # 12. Connect manual device ID switch triggers
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

    # 13. Auto-poll active task progress every 1s
    task_poll_timer.tick(
        poll_active_task_progress,
        inputs=[device_id_state, session_task_state],
        outputs=[
            session_task_state,
            minimax_view.i2v_tab.player_card.status, minimax_view.i2v_tab.player_card.output_video,
            minimax_view.t2v_tab.player_card.status, minimax_view.t2v_tab.player_card.output_video,
            minimax_view.r2v_tab.player_card.status, minimax_view.r2v_tab.player_card.output_video,
            history_dropdown,
            *minimax_view.get_action_buttons(),
        ],
    )


demo.queue(default_concurrency_limit=None)


def launch_webui(port: int = WEBUI_PORT, raise_on_error: bool = False, **launch_kwargs):
    """Launches the Gradio WebUI strictly on the specified port (default 7860)."""
    import sys
    import threading

    if (
        getattr(demo, "_is_running_in_reload_thread", False)
        or getattr(demo, "is_running", False)
        or (os.environ.get("GRADIO_WATCH_DIRS") and threading.current_thread() is not threading.main_thread())
    ):
        return demo

    if PortGuardian.is_port_in_use(port):
        PortGuardian.print_port_conflict_help(port)
        if raise_on_error:
            raise OSError(f"Port {port} is already in use by another process.")
        sys.exit(1)

    print("=" * 60)
    print(f"AI WebUI Multi-Module Platform Starting (Port: {port})...")
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
            PortGuardian.print_port_conflict_help(port)
            if raise_on_error:
                raise
            sys.exit(1)
        raise


if __name__ == "__main__":
    launch_webui()

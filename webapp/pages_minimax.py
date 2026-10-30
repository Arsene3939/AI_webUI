"""
MiniMax module page (Spec 2026-10-31 routing refactor): the gr.Blocks that is
mounted at /minimax. Houses everything app.py used to build inline for the
minimax view — state restoration, device switching, progress polling, component
aliases and the 55-output restore contract that tests/e2e assert on.
"""
import os
import uuid
from typing import Optional

import gradio as gr

from task_manager import task_manager
from utils.logger import get_logger

from core.admin_manager import AdminManager
from components.header import build_header_html
from components.media_player import build_progress_html
from components.history_gallery import get_history_dropdown_choices

from views.minimax.view import MiniMaxView

from .shell import WebPageScaffold

logger = get_logger("Page.minimax")

# --- Shared Tracking State for Device Notifications (module-level: patchable/inspectable) ---
_device_last_reported_completed: dict = {}
_device_last_status_html: dict = {}


class MiniMaxPage(WebPageScaffold):
    module_key = "minimax"

    def __init__(self):
        super().__init__(title="MiniMax-H3 AI Video WebUI")
        self.minimax_view: Optional[MiniMaxView] = None
        self.history_dropdown = None
        self.all_restored_outputs: list = []
        self.build()
        self._build_page()
        self.blocks.queue(default_concurrency_limit=None)

    def _build_page(self):
        with self.blocks:
            # Core View (OOP Modularized with dedicated Admin Tab)
            self.minimax_view = MiniMaxView()
            self.minimax_view.render(self.session_ctx)

            # Dropdown aliases for direct component inspection
            self.i2v_aspect_ratio = self.minimax_view.i2v_tab.params_card.aspect_ratio
            self.i2v_quality_level = self.minimax_view.i2v_tab.params_card.quality_level
            self.i2v_sampler = self.minimax_view.i2v_tab.params_card.sampler
            self.i2v_scheduler = self.minimax_view.i2v_tab.params_card.scheduler

            self.t2v_aspect_ratio = self.minimax_view.t2v_tab.params_card.aspect_ratio
            self.t2v_quality_level = self.minimax_view.t2v_tab.params_card.quality_level
            self.t2v_sampler = self.minimax_view.t2v_tab.params_card.sampler
            self.t2v_scheduler = self.minimax_view.t2v_tab.params_card.scheduler

            self.r2v_aspect_ratio = self.minimax_view.r2v_tab.params_card.aspect_ratio
            self.r2v_quality_level = self.minimax_view.r2v_tab.params_card.quality_level
            self.r2v_sampler = self.minimax_view.r2v_tab.params_card.sampler
            self.r2v_scheduler = self.minimax_view.r2v_tab.params_card.scheduler

            # Register events for the view (including its admin tab)
            self.minimax_view.register_events(self.session_ctx)

            # Super User dynamic visibility on page load
            def update_admin_tab_visibility(request: gr.Request):
                is_admin = AdminManager.is_super_user(request)
                # NOTE: single output -> must return the update dict DIRECTLY.
                # Wrapping it in a list hands the whole list to the Tab slot as a raw
                # prediction, which trips gradio's "Tab not a valid output" guard.
                return gr.update(visible=is_admin)

            self.blocks.load(
                update_admin_tab_visibility,
                outputs=[self.minimax_view.admin_tab.tab],
            )

            # Backward-compatible state restoration outputs (55 components)
            self.history_dropdown = self.minimax_view.history_gallery.dropdown
            self.all_restored_outputs = [
                self.device_id_state,
                self.session_task_state,
                self.header_comp.header_html,
                self.history_dropdown,
                *self.minimax_view.get_restore_components(),
                *self.minimax_view.get_action_buttons(),
            ]

            # Connect recovery and page reload triggers
            self.blocks.load(
                self.restore_device_state,
                inputs=[self.device_id_state, self.session_task_state],
                outputs=self.all_restored_outputs,
            )
            for tab in (self.minimax_view.i2v_tab, self.minimax_view.t2v_tab, self.minimax_view.r2v_tab):
                tab.player_card.recover_btn.click(
                    self.restore_device_state,
                    inputs=[self.device_id_state, self.session_task_state],
                    outputs=self.all_restored_outputs,
                )

            # Manual device ID switch (full minimax state restoration semantics)
            save_id_btn = self.header_comp.save_id_btn
            manual_id_input = self.header_comp.manual_id_input
            edit_id_row = self.header_comp.edit_id_row
            save_id_btn.click(
                self.switch_manual_device_id,
                inputs=[manual_id_input, self.device_id_state, self.session_task_state],
                outputs=[edit_id_row, *self.all_restored_outputs],
            )
            manual_id_input.submit(
                self.switch_manual_device_id,
                inputs=[manual_id_input, self.device_id_state, self.session_task_state],
                outputs=[edit_id_row, *self.all_restored_outputs],
            )

            # Auto-poll active task progress every 1s
            self.task_poll_timer.tick(
                self.poll_active_task_progress,
                inputs=[self.device_id_state, self.session_task_state],
                outputs=[
                    self.session_task_state,
                    self.minimax_view.i2v_tab.player_card.status, self.minimax_view.i2v_tab.player_card.output_video,
                    self.minimax_view.t2v_tab.player_card.status, self.minimax_view.t2v_tab.player_card.output_video,
                    self.minimax_view.r2v_tab.player_card.status, self.minimax_view.r2v_tab.player_card.output_video,
                    self.history_dropdown,
                    *self.minimax_view.get_action_buttons(),
                ],
            )

    # ------------------------------------------------------------------
    # Device state handlers (formerly closures inside app.py's single Blocks)
    # ------------------------------------------------------------------
    def restore_device_state(self, stored_device_id: Optional[str], stored_task_id: Optional[str]):
        """Restores inputs, parameters, and generated video for THIS specific device."""
        if not stored_device_id:
            stored_device_id = f"dev_{uuid.uuid4().hex[:6]}"

        task = (
            task_manager.get_task(stored_task_id, device_id=stored_device_id, module="minimax")
            or task_manager.get_latest_task_for_device(stored_device_id, module="minimax")
        )
        logger.info("[Session] Device connected/restoring: %s (Active task: %s)", stored_device_id, task.task_id if task else "None")

        content_updates, btn_updates = self.minimax_view.restore_state(task, stored_device_id)
        history_choices = get_history_dropdown_choices(stored_device_id, module="minimax")
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

    def switch_manual_device_id(self, custom_id: str, current_device_id: str, session_task_id: str):
        """Allows user to switch to a remembered device ID without exposing others."""
        val = (custom_id or "").strip()
        if not val:
            return (gr.update(visible=False), *self.restore_device_state(current_device_id, session_task_id))
        target_id = val if val.startswith("dev_") else f"dev_{val}"
        logger.info("[Session] Device ID manual switch: '%s' -> '%s'", current_device_id, target_id)
        return (gr.update(visible=False), *self.restore_device_state(target_id, None))

    def poll_active_task_progress(self, stored_device_id: Optional[str], stored_task_id: Optional[str]):
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

        task = (
            task_manager.get_active_task_for_device(stored_device_id, module="minimax")
            or task_manager.get_task(stored_task_id, device_id=stored_device_id, module="minimax")
        )
        if not task:
            task = task_manager.get_latest_task_for_device(stored_device_id, module="minimax")

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
            history_choices = get_history_dropdown_choices(stored_device_id, module="minimax")
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


PAGE = MiniMaxPage()

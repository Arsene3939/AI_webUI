"""
MiniMax-H3 main view encapsulating I2V, T2V, R2V tabs, and history gallery.
"""
import os
from typing import Optional, Any, List, Dict, Tuple
import gradio as gr
from core.comfy_view import ComfyUIBaseView
from views.minimax.tabs.i2v_tab import I2VTab
from views.minimax.tabs.t2v_tab import T2VTab
from views.minimax.tabs.r2v_tab import R2VTab
from views.minimax.admin_tab import MiniMaxAdminTab
from components.history_gallery import (
    HistoryGalleryComponent,
    get_history_dropdown_choices,
    on_select_history_item,
    on_delete_history_item,
)
from components.media_player import build_progress_html
from config import (
    normalize_aspect_ratio,
    normalize_quality_choice,
    normalize_sampler,
    normalize_scheduler,
)
from task_manager import task_manager
from utils.logger import get_logger

logger = get_logger("MiniMaxView")


class MiniMaxView(ComfyUIBaseView):
    """
    Main MiniMax-H3 video generator view containing I2V, T2V, and R2V generation tabs,
    as well as device-isolated history gallery.
    """

    def __init__(self):
        super().__init__(name="minimax", icon="🎬", title="comfyUI: minimax video generator")
        self.i2v_tab = I2VTab()
        self.t2v_tab = T2VTab()
        self.r2v_tab = R2VTab()
        self.history_gallery = HistoryGalleryComponent(module="minimax")
        self.admin_tab = MiniMaxAdminTab()
        self.tabs: Optional[gr.Tabs] = None
        self._device_last_reported_completed: Dict[str, str] = {}
        self._device_last_status_html: Dict[str, str] = {}

    def render(self, session_ctx: Any) -> gr.Column:
        with gr.Column(visible=True) as self.container:
            with gr.Tabs() as self.tabs:
                self.i2v_tab.render()
                self.t2v_tab.render()
                self.r2v_tab.render()
                with gr.Tab("📜 歷史紀錄"):
                    self.history_gallery.render()
                self.admin_tab.render(session_ctx)
        return self.container

    def register_events(self, session_ctx: Any) -> None:
        def on_completed(device_id: str, task_id: str):
            self._device_last_reported_completed[device_id] = task_id

        self.i2v_tab.register_events(session_ctx.session_task_state, session_ctx.device_id_state, on_completed)
        self.t2v_tab.register_events(session_ctx.session_task_state, session_ctx.device_id_state, on_completed)
        self.r2v_tab.register_events(session_ctx.session_task_state, session_ctx.device_id_state, on_completed)
        self.history_gallery.register_events(session_ctx.device_id_state)
        self.admin_tab.register_events(session_ctx)

        # Last-frame extraction/download for each player card (Spec task 3),
        # plus clearing a stale frame offer whenever a new generation starts.
        for tab in (self.i2v_tab, self.t2v_tab, self.r2v_tab):
            tab.player_card.register_frame_events()
            tab.action_btns.generate_btn.click(
                lambda tab=tab: tab.player_card.reset_frame_updates(),
                outputs=[tab.player_card.frame_download, tab.player_card.frame_msg],
            )

    def get_restore_components(self) -> List[Any]:
        """
        Returns all 45 sub-components belonging to MiniMax (I2V 14 + T2V 12 + R2V 19).
        Buttons are also accessible via get_action_buttons().
        """
        return (
            self.i2v_tab.get_components_for_restore()
            + self.t2v_tab.get_components_for_restore()
            + self.r2v_tab.get_components_for_restore()
        )

    def get_action_buttons(self) -> List[Any]:
        return (
            self.i2v_tab.get_action_btns()
            + self.t2v_tab.get_action_btns()
            + self.r2v_tab.get_action_btns()
        )

    def restore_state(self, task: Optional[Any], device_id: str) -> Tuple[List[Any], List[Any]]:
        """
        Restores MiniMax inputs, parameters, and action button states for the device.
        Returns (content_updates [45 items], button_updates [6 items]).
        """
        i2v_updates = [gr.update()] * 14
        t2v_updates = [gr.update()] * 12
        r2v_updates = [gr.update()] * 19

        if task and getattr(task, "params", None):
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
            self._device_last_reported_completed[device_id] = task.task_id
        elif task and task.status in ("running", "queued"):
            self._device_last_reported_completed.pop(device_id, None)

        active_task = task_manager.get_active_task_for_device(device_id, module="minimax")
        is_active = active_task is not None
        active_type = active_task.task_type if active_task else None

        i2v_btn_st = gr.update(visible=False) if (is_active and active_type == "I2V") else gr.update(visible=True)
        i2v_stop_st = gr.update(visible=True) if (is_active and active_type == "I2V") else gr.update(visible=False)
        t2v_btn_st = gr.update(visible=False) if (is_active and active_type == "T2V") else gr.update(visible=True)
        t2v_stop_st = gr.update(visible=True) if (is_active and active_type == "T2V") else gr.update(visible=False)
        r2v_btn_st = gr.update(visible=False) if (is_active and active_type == "R2V") else gr.update(visible=True)
        r2v_stop_st = gr.update(visible=True) if (is_active and active_type == "R2V") else gr.update(visible=False)

        btn_updates = [i2v_btn_st, i2v_stop_st, t2v_btn_st, t2v_stop_st, r2v_btn_st, r2v_stop_st]
        return i2v_updates + t2v_updates + r2v_updates, btn_updates

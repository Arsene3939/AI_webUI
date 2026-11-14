"""
助理模型（Strata）控制 toolbar — Spec 2026-11-03。

與 components/comfy_toolbar.py 完全同構：同一顆「啟動後端模型」式的按鈕＋
狀態訊息＋定時輪詢；資源不足由原本的系統資源檢查機制擋下（同一套門檻與
訊息，不另設新門檻）。差别只有對象是本機的 Strata 推理服務：
啟動＝`strata runtime start --profile …`（背景服務），就緒以 /health 輪詢為準。
使用者看到的文案不出現顯存／後端进程等開發者字眼。
"""
from typing import Optional, Tuple

import gradio as gr

from config import SERVER_STATUS_UPDATING, get_server_status
from core.comfy_client import check_system_resources
from core.strata_client import is_up, start_backend, stop_backend
from ui_text import (
    COMMON_MAINT_BTN,
    STRATA_ALREADY_RUNNING_MSG,
    STRATA_BTN_START,
    STRATA_BTN_STARTING,
    STRATA_CHECK_BTN,
    STRATA_GATE_MAINT_MSG,
    STRATA_MODEL_RUNNING,
    STRATA_STARTING_MSG,
    STRATA_START_RESOURCE_HINT,
    STRATA_STOP_BTN,
)
from utils.logger import get_logger

logger = get_logger("StrataToolbar")


class StrataToolbarComponent:
    """助理模型狀態指示與啟動／停止按鈕（/strata 頁專用）。"""

    def __init__(self):
        self.row: Optional[gr.Row] = None
        self.start_btn: Optional[gr.Button] = None
        self.stop_btn: Optional[gr.Button] = None
        self.status_msg: Optional[gr.Markdown] = None
        self._is_backend_starting: bool = False

    def render(self) -> "StrataToolbarComponent":
        with gr.Row() as self.row:
            self.start_btn = gr.Button(STRATA_CHECK_BTN, variant="secondary", scale=9)
            self.stop_btn = gr.Button(STRATA_STOP_BTN, variant="stop", scale=1, min_width=50)

        self.status_msg = gr.Markdown("", elem_classes=["backend-status-box"])
        return self

    def poll_backend_status(self) -> dict:
        """定時輪詢助理狀態，決定按鈕文字與顏色。"""
        if get_server_status() == SERVER_STATUS_UPDATING:
            return gr.update(value=COMMON_MAINT_BTN, variant="stop")
        if self._is_backend_starting:
            return gr.update(value=STRATA_BTN_STARTING, variant="secondary")
        if is_up():
            return gr.update(value=STRATA_MODEL_RUNNING, variant="primary")
        return gr.update(value=STRATA_BTN_START, variant="secondary")

    def on_start_backend(self):
        """啟動助理模型：先過資源檢查（與啟動影片後端同一道關卡），才真正啟動。"""
        if get_server_status() == SERVER_STATUS_UPDATING:
            yield gr.update(value=COMMON_MAINT_BTN, variant="stop"), STRATA_GATE_MAINT_MSG
            return

        if is_up():
            yield gr.update(value=STRATA_MODEL_RUNNING, variant="primary"), STRATA_ALREADY_RUNNING_MSG
            return

        res_ok, warning_msg, _ = check_system_resources()
        if not res_ok:
            # 常見情境是「影片生成後端」還在跑：用既有檢查的訊息，另加一句可操作提示
            yield gr.update(value=STRATA_BTN_START, variant="secondary"), (
                warning_msg + STRATA_START_RESOURCE_HINT
            )
            return

        self._is_backend_starting = True
        yield gr.update(value=STRATA_BTN_STARTING, variant="secondary"), STRATA_STARTING_MSG

        try:
            _ok, msg = start_backend()
        finally:
            self._is_backend_starting = False

        yield self.poll_backend_status(), f"{msg}"

    def on_stop_backend(self) -> Tuple[dict, str]:
        """停止助理模型。交談／導演正在進行的內容會以友善訊息自然收尾。"""
        _ok, msg = stop_backend()
        return self.poll_backend_status(), f"{msg}"

    def register_events(self, timer: Optional[gr.Timer] = None):
        if self.start_btn and self.status_msg:
            self.start_btn.click(self.on_start_backend, outputs=[self.start_btn, self.status_msg])
        if self.stop_btn and self.status_msg:
            self.stop_btn.click(self.on_stop_backend, outputs=[self.start_btn, self.status_msg])
        if timer and self.start_btn:
            timer.tick(self.poll_backend_status, outputs=[self.start_btn])

"""
Strata 管理專區（Spec 2026-11-03 重建：移除早期 Ollama 時代的假設定）。

管理員可調整助理服務的位址與金鑰（存進 outputs/strata_settings.json，與
資源門檻相同的持久化模式；存檔當下立即生效），並用白話看到助理即時狀態
（用什麼模型、上線沒有、能不能看圖）。繼承 BaseAdminTab 的共用維護功能。
"""
from typing import Any, Optional

import gradio as gr

from config import get_strata_settings, set_strata_settings
from core.admin_manager import AdminManager
from core.base_admin_tab import BaseAdminTab
from core.strata_client import full_status, health
from ui_text import (
    STRATA_ADMIN_DESC_MD,
    STRATA_ADMIN_HEADING_MD,
    STRATA_ADMIN_TAB_TITLE,
    STRATA_API_BASE_LABEL,
    STRATA_API_BASE_PLACEHOLDER,
    STRATA_API_KEY_LABEL,
    STRATA_API_KEY_PLACEHOLDER,
    STRATA_MODEL_RUNNING,
    STRATA_NO_PERM_MSG,
    STRATA_REFRESH_STATUS_BTN,
    STRATA_SAVE_CONN_BTN,
    STRATA_SAVE_OK_MD,
    STRATA_STATUS_CTX_LINE,
    STRATA_STATUS_MODEL_LINE,
    STRATA_STATUS_OFF_MD,
    STRATA_STATUS_VISION_OFF,
    STRATA_STATUS_VISION_ON,
)
from utils.logger import get_logger

logger = get_logger("StrataAdmin")


def build_strata_status_md() -> str:
    """給管理頁的助理即時狀態（白話；不出現端點/進程等開發者字眼）。"""
    h = health()
    if h is None:
        return STRATA_STATUS_OFF_MD
    lines = [STRATA_MODEL_RUNNING]
    model = h.get("model")
    if model:
        lines.append(STRATA_STATUS_MODEL_LINE.format(model))
    ctx = h.get("max_context")
    if isinstance(ctx, (int, float)) and ctx > 0:
        lines.append(STRATA_STATUS_CTX_LINE.format(int(ctx)))
    st = full_status() or {}
    vision = st.get("vision")
    if isinstance(vision, dict):
        lines.append(STRATA_STATUS_VISION_ON if vision.get("enabled") else STRATA_STATUS_VISION_OFF)
    return "\n\n".join(lines) if len(lines) > 1 else lines[0]


class StrataAdminTab(BaseAdminTab):
    """
    Strata 助理的管理員設定：連線位址／金鑰＋助理即時狀態。
    其餘共用功能（維護切換、硬體面板、管理員名單…）由 BaseAdminTab 提供。
    """

    def __init__(self):
        super().__init__(tab_title=STRATA_ADMIN_TAB_TITLE)
        self.api_base_input: Optional[gr.Textbox] = None
        self.api_key_input: Optional[gr.Textbox] = None
        self.save_conn_btn: Optional[gr.Button] = None
        self.refresh_status_btn: Optional[gr.Button] = None
        self.strata_admin_msg: Optional[gr.Markdown] = None

    def render_custom_content(self, session_ctx: Any) -> None:
        cur = get_strata_settings()
        gr.Markdown(STRATA_ADMIN_HEADING_MD)
        gr.Markdown(STRATA_ADMIN_DESC_MD)
        with gr.Row():
            self.api_base_input = gr.Textbox(
                label=STRATA_API_BASE_LABEL,
                value=cur["base_url"],
                placeholder=STRATA_API_BASE_PLACEHOLDER,
                scale=6,
            )
            self.api_key_input = gr.Textbox(
                label=STRATA_API_KEY_LABEL,
                placeholder=STRATA_API_KEY_PLACEHOLDER,
                type="password",
                scale=4,
            )
        with gr.Row():
            self.save_conn_btn = gr.Button(STRATA_SAVE_CONN_BTN, variant="primary", scale=3)
            self.refresh_status_btn = gr.Button(STRATA_REFRESH_STATUS_BTN, variant="secondary", scale=2)
        self.strata_admin_msg = gr.Markdown(
            build_strata_status_md(), elem_classes=["backend-status-box"]
        )

    def register_custom_events(self, session_ctx: Any) -> None:
        def on_save(base_url, api_key, request: gr.Request = None):
            if not AdminManager.is_super_user(request):
                return STRATA_NO_PERM_MSG
            ok, msg = set_strata_settings(base_url, api_key)
            if ok:
                logger.warning("Strata connection settings updated by admin")
                msg = STRATA_SAVE_OK_MD.format(msg, build_strata_status_md())
            return msg

        self.save_conn_btn.click(
            on_save,
            inputs=[self.api_base_input, self.api_key_input],
            outputs=[self.strata_admin_msg],
        )
        self.refresh_status_btn.click(
            lambda: build_strata_status_md(),
            outputs=[self.strata_admin_msg],
        )

    def wire_page_load(self, blocks: gr.Blocks) -> None:
        """每次開頁從檔案重抓現值＋刷新助理狀態（規避 PAGE 單例建置期快照）。"""
        super().wire_page_load(blocks)

        def reload_strata_conn():
            cur = get_strata_settings()
            return (
                gr.update(value=cur["base_url"]),
                gr.update(value=cur["api_key"]),
                build_strata_status_md(),
            )

        blocks.load(
            reload_strata_conn,
            outputs=[self.api_base_input, self.api_key_input, self.strata_admin_msg],
            api_name=False,
        )

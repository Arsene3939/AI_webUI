"""
Header UI component with LAN IP, concise Device ID badge, and server status banner.
"""
from typing import Optional, Tuple
import gradio as gr
from config import (
    WEBUI_PORT,
    SERVER_STATUS_UPDATING,
    get_server_status,
    get_lan_ip,
)
from ui_text import (
    CHROME_HEADER_DEVICE_BADGE_HTML,
    CHROME_HEADER_MAINT_BANNER_HTML,
    CHROME_HEADER_PAGE_HTML,
    CHROME_HEADER_TITLE_MINIMAX,
    CHROME_ID_CANCEL_BTN,
    CHROME_ID_EDIT_BTN,
    CHROME_ID_INPUT_LABEL,
    CHROME_ID_INPUT_PLACEHOLDER,
    CHROME_ID_SAVE_BTN,
)


# 頁面主標（三個模組頁共用同一 header 元件，各自帶自己的產品名；
# 預值是 minimax，維持舊呼叫端/測試的既有行為）
# 文案已集中至 ui_text.chrome；此模組層級名稱保留給既有呼叫端按名取用。
DEFAULT_HEADER_TITLE = CHROME_HEADER_TITLE_MINIMAX


def build_header_html(device_id: Optional[str] = None, title: Optional[str] = None) -> str:
    """Builds top header banner HTML with LAN IP and device badge."""
    lan_ip = get_lan_ip()
    status_banner = ""
    if get_server_status() == SERVER_STATUS_UPDATING:
        status_banner = CHROME_HEADER_MAINT_BANNER_HTML

    if device_id:
        short_hash = device_id.split("_")[-1][:6]
        dev_str = CHROME_HEADER_DEVICE_BADGE_HTML.format(short_hash)
    else:
        dev_str = ""

    # {} 依序：主標、內網 IP、埠號、裝置徽章、維護橫幅（數字留呼叫端）
    return CHROME_HEADER_PAGE_HTML.format(
        title or DEFAULT_HEADER_TITLE, lan_ip, WEBUI_PORT, dev_str, status_banner
    )


class HeaderComponent:
    """Encapsulates header banner and manual Device ID switch row."""

    def __init__(self, header_title: str = DEFAULT_HEADER_TITLE):
        self.header_title = header_title
        self.header_html: Optional[gr.HTML] = None
        self.edit_id_btn: Optional[gr.Button] = None
        self.edit_id_row: Optional[gr.Row] = None
        self.manual_id_input: Optional[gr.Textbox] = None
        self.save_id_btn: Optional[gr.Button] = None
        self.cancel_id_btn: Optional[gr.Button] = None

    def render(self) -> "HeaderComponent":
        self.header_html = gr.HTML(build_header_html(title=self.header_title))
        self.edit_id_btn = gr.Button(CHROME_ID_EDIT_BTN, elem_id="edit-id-trigger-btn", elem_classes=["hidden-trigger-btn"])

        with gr.Row(visible=False) as self.edit_id_row:
            self.manual_id_input = gr.Textbox(
                label=CHROME_ID_INPUT_LABEL,
                placeholder=CHROME_ID_INPUT_PLACEHOLDER,
                scale=5,
            )
            self.save_id_btn = gr.Button(CHROME_ID_SAVE_BTN, variant="primary", scale=1)
            self.cancel_id_btn = gr.Button(CHROME_ID_CANCEL_BTN, variant="secondary", scale=1)
        return self

    def register_toggle_events(self):
        if self.edit_id_btn and self.edit_id_row and self.cancel_id_btn:
            self.edit_id_btn.click(lambda: gr.update(visible=True), outputs=[self.edit_id_row])
            self.cancel_id_btn.click(lambda: gr.update(visible=False), outputs=[self.edit_id_row])

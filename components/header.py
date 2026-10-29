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


def build_header_html(device_id: Optional[str] = None) -> str:
    """Builds top header banner HTML with LAN IP and device badge."""
    lan_ip = get_lan_ip()
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


class HeaderComponent:
    """Encapsulates header banner and manual Device ID switch row."""

    def __init__(self):
        self.header_html: Optional[gr.HTML] = None
        self.edit_id_btn: Optional[gr.Button] = None
        self.edit_id_row: Optional[gr.Row] = None
        self.manual_id_input: Optional[gr.Textbox] = None
        self.save_id_btn: Optional[gr.Button] = None
        self.cancel_id_btn: Optional[gr.Button] = None

    def render(self) -> "HeaderComponent":
        self.header_html = gr.HTML(build_header_html())
        self.edit_id_btn = gr.Button("✏️", elem_id="edit-id-trigger-btn", elem_classes=["hidden-trigger-btn"])

        with gr.Row(visible=False) as self.edit_id_row:
            self.manual_id_input = gr.Textbox(
                label="切換裝置 ID",
                placeholder="請輸入 6 位數代碼 (例如 71c8f5)...",
                scale=5,
            )
            self.save_id_btn = gr.Button("確認切換", variant="primary", scale=1)
            self.cancel_id_btn = gr.Button("取消", variant="secondary", scale=1)
        return self

    def register_toggle_events(self):
        if self.edit_id_btn and self.edit_id_row and self.cancel_id_btn:
            self.edit_id_btn.click(lambda: gr.update(visible=True), outputs=[self.edit_id_row])
            self.cancel_id_btn.click(lambda: gr.update(visible=False), outputs=[self.edit_id_row])

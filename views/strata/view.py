"""
Strata 智慧助理頁（Spec 2026-11-03 起為真實功能，之前為展示用 mock）。

結構與 comfy 兩頁一致：頁頂「啟動助理模型」toolbar（資源不足由既有系統
資源檢查擋下）＋智慧對話（串流出字、可选附件圖片、工作類型模板）。
對話一律採不拒絕的自由回答（2026-11-03 使用者決定移除濾網開關）。
使用者文案不出現顯存/API/端點等開發者字眼。
"""
from typing import Any, Optional

import gradio as gr

from components.strata_toolbar import StrataToolbarComponent
from core.base_view import BaseView
from core.strata_client import chat_stream, image_data_uri, is_up, vision_enabled
from ui_text import (
    STRATA_CHAT_TEMPLATES,
    STRATA_CHATBOT_LABEL,
    STRATA_CLEAR_BTN,
    STRATA_DEFAULT_CHAT_SYSTEM_PROMPT,
    STRATA_EMPTY_REPLY_NOTE,
    STRATA_IMAGE_ACCORDION,
    STRATA_IMAGE_LABEL,
    STRATA_IMAGE_NOTE,
    STRATA_MSG_INPUT_LABEL,
    STRATA_MSG_PLACEHOLDER,
    STRATA_NOT_UP_MSG,
    STRATA_PAGE_DESC_MD,
    STRATA_PAGE_TITLE_MD,
    STRATA_SEND_BTN,
    STRATA_SETTINGS_ACCORDION,
    STRATA_SYS_PROMPT_LABEL,
    STRATA_TAB_CHAT,
    STRATA_TEMP_LABEL,
    STRATA_TEMPLATE_DD_INFO,
    STRATA_TEMPLATE_DD_LABEL,
    STRATA_TEMPLATE_GENERAL,
)
from utils.logger import get_logger

from views.strata.admin_tab import StrataAdminTab

logger = get_logger("StrataView")

# 文案已集中至 ui_text.strata；以下模組層級名稱保留給測試與呼叫端按名取用。
DEFAULT_CHAT_SYSTEM_PROMPT = STRATA_DEFAULT_CHAT_SYSTEM_PROMPT
# 工作類型模板：選模板＝自動帶入對應的系統提示詞（使用者仍可手動修改）
CHAT_TEMPLATES = STRATA_CHAT_TEMPLATES
NOT_UP_MSG = STRATA_NOT_UP_MSG


class StrataView(BaseView):
    """
    Strata 智慧助理工作台：對話分頁（真實串流補完）＋ StrataAdminTab。
    """

    def __init__(self):
        super().__init__(name="strata", icon="💬", title="strata: 智慧助理")
        self.tabs: Optional[gr.Tabs] = None
        self.strata_toolbar: Optional[StrataToolbarComponent] = None
        self.strata_poll_timer: Optional[gr.Timer] = None
        self.chatbot: Optional[gr.Chatbot] = None
        self.msg_input: Optional[gr.Textbox] = None
        self.send_btn: Optional[gr.Button] = None
        self.clear_btn: Optional[gr.Button] = None
        self.image_input: Optional[gr.Image] = None
        self.system_prompt: Optional[gr.Textbox] = None
        self.template_dd: Optional[gr.Dropdown] = None
        self.temperature: Optional[gr.Slider] = None
        self.admin_tab = StrataAdminTab()

    def render(self, session_ctx: Any) -> gr.Column:
        # Routing refactor: view is the whole content of the /strata page (visible).
        with gr.Column() as self.container:
            # 助理模型啟動／停止 toolbar（與 shell 共用的 ComfyUI toolbar 文案區隔：
            # 「啟動後端模型」＝影片生成用，「啟動助理模型」＝對話與導演用）
            self.strata_toolbar = StrataToolbarComponent().render()
            self.strata_poll_timer = gr.Timer(value=5.0)

            with gr.Tabs() as self.tabs:
                with gr.Tab(STRATA_TAB_CHAT):
                    gr.Markdown(STRATA_PAGE_TITLE_MD)
                    gr.Markdown(STRATA_PAGE_DESC_MD)

                    with gr.Row():
                        with gr.Column(scale=4):
                            self.chatbot = gr.Chatbot(label=STRATA_CHATBOT_LABEL, height=480)
                            with gr.Row():
                                self.msg_input = gr.Textbox(
                                    placeholder=STRATA_MSG_PLACEHOLDER,
                                    label=STRATA_MSG_INPUT_LABEL,
                                    lines=2,
                                    scale=8,
                                )
                                self.send_btn = gr.Button(STRATA_SEND_BTN, variant="primary", scale=1)
                                self.clear_btn = gr.Button(STRATA_CLEAR_BTN, variant="secondary", scale=1)

                        with gr.Column(scale=1):
                            with gr.Accordion(STRATA_IMAGE_ACCORDION, open=False):
                                self.image_input = gr.Image(
                                    type="filepath", label=STRATA_IMAGE_LABEL, height=200,
                                )
                            with gr.Accordion(STRATA_SETTINGS_ACCORDION, open=True):
                                self.template_dd = gr.Dropdown(
                                    choices=list(CHAT_TEMPLATES.keys()),
                                    value=STRATA_TEMPLATE_GENERAL,
                                    label=STRATA_TEMPLATE_DD_LABEL,
                                    info=STRATA_TEMPLATE_DD_INFO,
                                    filterable=False,
                                )
                                self.system_prompt = gr.Textbox(
                                    label=STRATA_SYS_PROMPT_LABEL,
                                    value=DEFAULT_CHAT_SYSTEM_PROMPT,
                                    lines=4,
                                )
                                self.temperature = gr.Slider(
                                    minimum=0.1, maximum=1.5, value=0.7, step=0.05,
                                    label=STRATA_TEMP_LABEL,
                                )

                self.admin_tab.render(session_ctx)
        return self.container

    # ── 對話流程 ─────────────────────────────────────────────────────────
    def _build_openai_messages(self, history, sys_prompt, image_path):
        """把 Chatbot 歷史（最近 12 輪）轉成 OpenAI messages；系統提示詞永遠在第一位。
        回傳 (messages, image_note)：image_note 非空表示圖片被降成純文字的原因。"""
        messages = []
        sp = (sys_prompt or DEFAULT_CHAT_SYSTEM_PROMPT).strip()
        if sp:
            messages.append({"role": "system", "content": sp})

        turns = [h for h in (history or []) if isinstance(h, dict) and h.get("role") in ("user", "assistant")]
        for h in turns[-12:]:
            content = h.get("content")
            if isinstance(content, str) and content.strip():
                messages.append({"role": h["role"], "content": content})

        image_note = ""
        if image_path:
            if vision_enabled():
                uri = image_data_uri(image_path)
                if uri and messages and messages[-1]["role"] == "user":
                    messages[-1]["content"] = [
                        {"type": "text", "text": messages[-1]["content"]},
                        {"type": "image_url", "image_url": {"url": uri}},
                    ]
            else:
                image_note = STRATA_IMAGE_NOTE
                logger.info("Strata vision unavailable; text-only reply for attached image")
        return messages, image_note

    def _respond(self, history, sys_prompt, temp, image_path):
        """串流補完：先把空的助理氣泡放進歷史，逐段出字，出錯就以訊息收尾。
        回答模式固定為不拒絕的自由回答（filter_on=False → 引擎 projection on）。"""
        history = history or []
        if not is_up():
            history.append({"role": "assistant", "content": NOT_UP_MSG})
            yield history
            return

        messages, image_note = self._build_openai_messages(history, sys_prompt, image_path)
        history.append({"role": "assistant", "content": image_note})
        yield history

        for kind, text in chat_stream(
            messages,
            temperature=temp,
            filter_on=False,
        ):
            if kind == "delta":
                cur = history[-1]["content"]
                history[-1]["content"] = (cur + text) if cur else text.lstrip("\n")
                yield list(history)
            elif kind == "error":
                joined = history[-1]["content"]
                history[-1]["content"] = (joined + "\n\n" if joined else "") + text
                yield history
                return
        # 正常收完：沒有字（助理回空）→ 給个提示，不留空白氣泡
        if not (history[-1]["content"] or "").strip():
            history[-1]["content"] = STRATA_EMPTY_REPLY_NOTE
            yield history

    def register_events(self, session_ctx: Any) -> None:
        def user_send(user_msg, history):
            if not user_msg or not user_msg.strip():
                return "", history
            history = history or []
            history.append({"role": "user", "content": user_msg.strip()})
            return "", history

        respond_inputs = [
            self.chatbot, self.system_prompt, self.temperature,
            self.image_input,
        ]

        for trigger in (self.send_btn.click, self.msg_input.submit):
            trigger(
                user_send,
                inputs=[self.msg_input, self.chatbot],
                outputs=[self.msg_input, self.chatbot],
            ).then(
                self._respond,
                inputs=respond_inputs,
                outputs=[self.chatbot],
                api_name=False,
                concurrency_limit=None,
            )

        def clear_all():
            return [], None, gr.update()

        self.clear_btn.click(
            clear_all,
            outputs=[self.chatbot, self.image_input, self.msg_input],
        )

        # 工作類型模板 → 帶入對應角色設定
        self.template_dd.change(
            lambda tpl: gr.update(value=CHAT_TEMPLATES.get(tpl, DEFAULT_CHAT_SYSTEM_PROMPT)),
            inputs=[self.template_dd],
            outputs=[self.system_prompt],
        )

        # 助理模型 toolbar：狀態輪詢＋啟動／停止
        self.strata_toolbar.register_events(timer=self.strata_poll_timer)

        self.admin_tab.register_events(session_ctx)

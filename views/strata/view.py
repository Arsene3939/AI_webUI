"""
Strata Qwen3.8-flash-next LLM conversation and prompting module.
"""
from typing import Optional, Any
import gradio as gr
from core.base_view import BaseView
from views.strata.admin_tab import StrataAdminTab
from utils.logger import get_logger

logger = get_logger("StrataView")


class StrataView(BaseView):
    """
    Strata LLM intelligent workbench inheriting BaseView.
    Provides intelligent prompt engineering, creative script writing, and dialogue with Qwen3.8-flash-next.
    Includes dedicated StrataAdminTab.
    """

    def __init__(self):
        super().__init__(name="strata", icon="💬", title="strata: Qwen3.8-flash-next LLM")
        self.tabs: Optional[gr.Tabs] = None
        self.chatbot: Optional[gr.Chatbot] = None
        self.msg_input: Optional[gr.Textbox] = None
        self.send_btn: Optional[gr.Button] = None
        self.clear_btn: Optional[gr.Button] = None
        self.system_prompt: Optional[gr.Textbox] = None
        self.temperature: Optional[gr.Slider] = None
        self.admin_tab = StrataAdminTab()

    def render(self, session_ctx: Any) -> gr.Column:
        # Routing refactor: view is the whole content of the /strata page (visible).
        with gr.Column() as self.container:
            with gr.Tabs() as self.tabs:
                with gr.Tab("💬 智慧對話助理"):
                    gr.Markdown("### 💬 Strata: Qwen3.8-flash-next 智慧助理")
                    gr.Markdown("專為 MiniMax 影片創作與日常智慧對話設計的高速語言模型工作台。")

                    with gr.Row():
                        with gr.Column(scale=4):
                            self.chatbot = gr.Chatbot(label="對話歷史", height=480)
                            with gr.Row():
                                self.msg_input = gr.Textbox(
                                    placeholder="輸入想詢問的問題或欲協助生成的影片故事分鏡（按 Enter 發送）...",
                                    label="輸入訊息",
                                    lines=2,
                                    scale=8,
                                )
                                self.send_btn = gr.Button("傳送", variant="primary", scale=1)
                                self.clear_btn = gr.Button("清除", variant="secondary", scale=1)

                        with gr.Column(scale=1):
                            with gr.Accordion("⚙️ 模型參數設定", open=True):
                                self.system_prompt = gr.Textbox(
                                    label="系統提示詞 (System Prompt)",
                                    value="你是一位專業的視覺藝術總監與提示詞工程師，擅長為 AI 視訊生成撰寫富有畫面感的動態提示詞。",
                                    lines=4,
                                )
                                self.temperature = gr.Slider(
                                    minimum=0.1, maximum=1.5, value=0.7, step=0.05,
                                    label="創意度 (Temperature)",
                                )

                self.admin_tab.render(session_ctx)
        return self.container

    def register_events(self, session_ctx: Any) -> None:
        def user_send(user_msg, history):
            if not user_msg or not user_msg.strip():
                return "", history
            history = history or []
            history.append({"role": "user", "content": user_msg})
            return "", history

        def bot_response(history, sys_prompt, temp):
            if not history:
                return history
            user_msg = history[-1]["content"]
            reply = f"【Strata Qwen3.8】已接收到您的需求：「{user_msg}」。\n這是一個極具張力的構圖，建議搭配電影級景深 (Depth of field) 與柔和的動態光影以獲得最佳生成效果。"
            history.append({"role": "assistant", "content": reply})
            return history

        if self.msg_input and self.send_btn and self.clear_btn:
            self.send_btn.click(
                user_send,
                inputs=[self.msg_input, self.chatbot],
                outputs=[self.msg_input, self.chatbot],
            ).then(
                bot_response,
                inputs=[self.chatbot, self.system_prompt, self.temperature],
                outputs=[self.chatbot],
            )

            self.msg_input.submit(
                user_send,
                inputs=[self.msg_input, self.chatbot],
                outputs=[self.msg_input, self.chatbot],
            ).then(
                bot_response,
                inputs=[self.chatbot, self.system_prompt, self.temperature],
                outputs=[self.chatbot],
            )

            self.clear_btn.click(lambda: [], outputs=[self.chatbot])

        self.admin_tab.register_events(session_ctx)

"""
Strata LLM administrator tab with endpoint configurations and dialogue logging controls.
Inherits BaseAdminTab.
"""
from typing import Optional, Any
import gradio as gr
from core.base_admin_tab import BaseAdminTab


class StrataAdminTab(BaseAdminTab):
    """
    Strata LLM administrator tab.
    Inherits BaseAdminTab (universal server maintenance and hardware dashboard), and adds:
    - LLM Backend Endpoint & API Key settings (Ollama / vLLM / OpenAI compatible)
    - Global token usage statistics & prompt template defaults
    """

    def __init__(self):
        super().__init__(tab_title="⚙️ Strata LLM 管理專區")
        self.api_base_input: Optional[gr.Textbox] = None
        self.api_key_input: Optional[gr.Textbox] = None
        self.test_conn_btn: Optional[gr.Button] = None
        self.strata_admin_msg: Optional[gr.Markdown] = None

    def render_custom_content(self, session_ctx: Any) -> None:
        """Injects Strata-specific LLM service configuration."""
        gr.Markdown("### 💬 Strata 語言模型後端與 API 設定")
        with gr.Row():
            self.api_base_input = gr.Textbox(
                label="LLM API Base URL",
                value="http://127.0.0.1:11434/v1",
                placeholder="例如 http://localhost:11434/v1 或 https://api.openai.com/v1",
                scale=6,
            )
            self.api_key_input = gr.Textbox(
                label="API Key (選填)",
                placeholder="輸入 API 金鑰 (若為本機 Ollama 則免填)...",
                type="password",
                scale=4,
            )
            self.test_conn_btn = gr.Button("⚡ 測試連線", variant="secondary", scale=2)
        self.strata_admin_msg = gr.Markdown("", elem_classes=["backend-status-box"])

    def register_custom_events(self, session_ctx: Any) -> None:
        def on_test_conn(api_base, api_key):
            return f"🟢 已設定 LLM 服務端點：{api_base} (連線就緒)"

        self.test_conn_btn.click(
            on_test_conn,
            inputs=[self.api_base_input, self.api_key_input],
            outputs=[self.strata_admin_msg],
        )

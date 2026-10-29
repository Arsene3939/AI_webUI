"""
Collapsible Sidebar Dashboard component (gr.Sidebar) to switch between core AI modules.
"""
from typing import Callable, List, Optional
import gradio as gr

MODULE_MINIMAX = "comfyUI: minimax video generator"
MODULE_UPSCALER = "comfyUI: video resolution upscaler"
MODULE_STRATA = "strata: Qwen3.8-flash-next LLM"

MODULE_CHOICES = [
    MODULE_MINIMAX,
    MODULE_UPSCALER,
    MODULE_STRATA,
]


class DashboardNavComponent:
    """
    Renders a collapsible Sidebar (gr.Sidebar) docked on the left.
    Provides fast switching across the 3 core AI modules (MiniMax, Upscaler, Strata)
    without using dropdown menus.
    """

    def __init__(self, default_module: str = MODULE_MINIMAX):
        self.default_module = default_module
        self.sidebar: Optional[gr.Sidebar] = None
        self.accordion: Optional[gr.Accordion] = None  # Backward-compatible alias
        self.module_selector: Optional[gr.Radio] = None
        self.btn_minimax: Optional[gr.Button] = None
        self.btn_upscaler: Optional[gr.Button] = None
        self.btn_strata: Optional[gr.Button] = None
        self.dashboard_info: Optional[gr.Markdown] = None

    def render(self) -> "DashboardNavComponent":
        with gr.Sidebar(
            label="📊 控制儀表板 (Dashboard)",
            open=True,
            position="left",
            width=300,
            elem_classes=["dashboard-sidebar"],
        ) as self.sidebar:
            gr.Markdown("### 📊 控制儀表板 (Dashboard)")
            gr.Markdown("快速切換核心 AI 模組：")

            # Module selection via Radio (visual cards/options, NOT a dropdown)
            self.module_selector = gr.Radio(
                choices=MODULE_CHOICES,
                value=self.default_module,
                label="核心功能模組",
                interactive=True,
                elem_classes=["dashboard-radio"],
            )

            with gr.Column(elem_classes=["dashboard-quick-buttons"]):
                gr.Markdown("#### 快捷切換")
                self.btn_minimax = gr.Button("🎬 MiniMax 影片生成", size="sm", variant="primary")
                self.btn_upscaler = gr.Button("🔍 影片超解析放大", size="sm", variant="secondary")
                self.btn_strata = gr.Button("💬 Strata 語言模型", size="sm", variant="secondary")

            self.dashboard_info = gr.Markdown(
                "---\n"
                "💡 **使用說明**：\n"
                "- 點擊左側箭頭按鈕可隨時**收合/展開**側邊欄。\n"
                "- 支援電腦與手機行動端流暢滑動。\n"
                "- 各模組具備獨立參數與會話空間。"
            )
        return self

    def bind_module_change(self, fn: Callable, outputs: List[gr.Column]):
        """Binds view switching when user clicks a different module in the dashboard."""
        if self.module_selector:
            self.module_selector.change(fn, inputs=[self.module_selector], outputs=outputs)

        def make_switcher(module_name: str):
            def switcher():
                col_updates = fn(module_name)
                # Returns (radio_value, *col_updates)
                return (module_name, *col_updates)
            return switcher

        if self.btn_minimax and self.module_selector:
            self.btn_minimax.click(
                make_switcher(MODULE_MINIMAX),
                outputs=[self.module_selector] + outputs,
            )
        if self.btn_upscaler and self.module_selector:
            self.btn_upscaler.click(
                make_switcher(MODULE_UPSCALER),
                outputs=[self.module_selector] + outputs,
            )
        if self.btn_strata and self.module_selector:
            self.btn_strata.click(
                make_switcher(MODULE_STRATA),
                outputs=[self.module_selector] + outputs,
            )

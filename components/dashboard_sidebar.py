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
    Renders a clean, collapsible Sidebar (gr.Sidebar) docked on the left.
    Provides 3 simple options to switch between core AI modules without clutter.
    """

    def __init__(self, default_module: str = MODULE_MINIMAX):
        self.default_module = default_module
        self.sidebar: Optional[gr.Sidebar] = None
        self.accordion: Optional[gr.Accordion] = None  # Backward-compatible alias
        self.module_selector: Optional[gr.Radio] = None

    def render(self) -> "DashboardNavComponent":
        with gr.Sidebar(
            label="控制儀表板",
            open=False,
            position="left",
            width=260,
            elem_classes=["dashboard-sidebar"],
        ) as self.sidebar:
            gr.Markdown("### 📊 功能切換", elem_classes=["dashboard-title"])

            self.module_selector = gr.Radio(
                choices=MODULE_CHOICES,
                value=self.default_module,
                show_label=False,
                interactive=True,
                elem_classes=["dashboard-simple-radio"],
            )
        return self

    def bind_module_change(self, fn: Callable, outputs: List[gr.Column]):
        """Binds view switching when user clicks a different module in the dashboard."""
        if self.module_selector:
            self.module_selector.change(fn, inputs=[self.module_selector], outputs=outputs)

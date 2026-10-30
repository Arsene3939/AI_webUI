"""
Collapsible Sidebar Dashboard component (gr.Sidebar) to switch between core AI modules.

Routing refactor (Spec 2026-10-31, 方案A): the 3 modules now live at their own URL
paths (/minimax, /upscaler, /strata), so the sidebar is a set of plain page links
instead of an in-page radio switcher. The active page highlights its own link.
"""
from typing import Optional
import gradio as gr

MODULE_MINIMAX = "comfyUI: minimax video generator"
MODULE_UPSCALER = "comfyUI: video resolution upscaler"
MODULE_STRATA = "strata: Qwen3.8-flash-next LLM"

MODULE_CHOICES = [
    MODULE_MINIMAX,
    MODULE_UPSCALER,
    MODULE_STRATA,
]

# module key -> (sidebar label, url path). Order defines sidebar order.
MODULE_NAV_ITEMS = [
    (MODULE_MINIMAX, "/minimax", "🎬 影片生成"),
    (MODULE_UPSCALER, "/upscaler", "🔍 畫質放大"),
    (MODULE_STRATA, "/strata", "💬 智慧助理"),
]


class DashboardNavComponent:
    """
    Renders a clean, collapsible Sidebar (gr.Sidebar) docked on the left.
    Provides 3 page links (anchors) to jump between the 3 module pages.
    """

    def __init__(self, default_module: str = MODULE_MINIMAX, active_module: Optional[str] = None):
        self.default_module = default_module
        self.active_module = active_module or default_module
        self.sidebar: Optional[gr.Sidebar] = None
        self.accordion: Optional[gr.Accordion] = None  # Backward-compatible alias
        self.links_html: Optional[gr.HTML] = None

    def _build_links_html(self) -> str:
        parts = ['<div class="dashboard-nav-links">']
        for module_key, href, label in MODULE_NAV_ITEMS:
            active_cls = " active" if module_key == self.active_module else ""
            parts.append(f'<a class="dashboard-link{active_cls}" href="{href}">{label}</a>')
        parts.append("</div>")
        return "".join(parts)

    def render(self) -> "DashboardNavComponent":
        with gr.Sidebar(
            label="控制儀表板",
            open=False,
            position="left",
            width=260,
            elem_classes=["dashboard-sidebar"],
        ) as self.sidebar:
            gr.Markdown("### 📊 功能切換", elem_classes=["dashboard-title"])
            self.links_html = gr.HTML(self._build_links_html(), elem_classes=["dashboard-simple-radio"])
        return self

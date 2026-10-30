"""
Upscaler module page: the gr.Blocks mounted at /upscaler (tabs: upscale,
history, admin — see shell.TAB_SEGMENTS).
"""
import gradio as gr

from core.admin_manager import AdminManager
from views.upscaler.view import UpscalerView

from .shell import WebPageScaffold


class UpscalerPage(WebPageScaffold):
    module_key = "upscaler"

    def __init__(self):
        super().__init__(title="comfyUI: video resolution upscaler")
        self.upscaler_view: UpscalerView | None = None
        self.build()
        self._build_page()
        self.blocks.queue(default_concurrency_limit=None)

    def _build_page(self):
        with self.blocks:
            self.upscaler_view = UpscalerView()
            self.upscaler_view.render(self.session_ctx)

            # Register events (incl. admin tab) and wire the 1s task-progress poll
            self.upscaler_view.register_events(self.session_ctx, poll_timer=self.task_poll_timer)

            # Manual device ID switch (generic: no minimax-style form restoration)
            self.wire_generic_device_switch()

            # Super User dynamic visibility on page load
            def update_admin_tab_visibility(request: gr.Request):
                is_admin = AdminManager.is_super_user(request)
                # NOTE: single output -> must return the update dict DIRECTLY.
                # Wrapping it in a list hands the whole list to the Tab slot as a raw
                # prediction, which trips gradio's "Tab not a valid output" guard.
                return gr.update(visible=is_admin)

            self.blocks.load(
                update_admin_tab_visibility,
                outputs=[self.upscaler_view.admin_tab.tab],
            )


PAGE = UpscalerPage()

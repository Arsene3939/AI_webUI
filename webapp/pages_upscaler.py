"""
Upscaler module page: the gr.Blocks mounted at /upscaler (tabs: upscale,
history, admin — see shell.TAB_SEGMENTS).
"""
import gradio as gr

from core.admin_manager import AdminManager
from views.upscaler.view import UpscalerView
from ui_text import CHROME_HEADER_TITLE_UPSCALER, CHROME_PAGE_TITLE_UPSCALER

from .shell import WebPageScaffold


class UpscalerPage(WebPageScaffold):
    module_key = "upscaler"

    def __init__(self):
        super().__init__(
            title=CHROME_PAGE_TITLE_UPSCALER,                    # 瀏覽器分頁標題（任務 2）
            header_title=CHROME_HEADER_TITLE_UPSCALER,           # 頁內 header 主標（任務 4：三頁共用同一套介面元素）
        )
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

            # 裝置 ID 徽章/生成/IP 記錄 + 維護可見性閘門（Spec 任務 1/4/7）：
            # own_header=True → load 時统一由這個 handler 寫 header 與 device id
            self.wire_maintenance_gate(
                [self.upscaler_view.container, self.toolbar_comp.row, self.dashboard_comp.sidebar],
                own_header=True,
            )

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

            # 資源門檻滑桿：每次開頁從檔案重抓現值（任務 2）
            self.upscaler_view.admin_tab.wire_page_load(self.blocks)


PAGE = UpscalerPage()

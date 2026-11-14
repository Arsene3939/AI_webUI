"""
Strata LLM module page: the gr.Blocks mounted at /strata (tabs: chat, admin).
"""
import gradio as gr

from core.admin_manager import AdminManager
from views.strata.view import StrataView
from ui_text import CHROME_HEADER_TITLE_STRATA, CHROME_PAGE_TITLE_STRATA

from .shell import WebPageScaffold


class StrataPage(WebPageScaffold):
    module_key = "strata"

    def __init__(self):
        super().__init__(
            title=CHROME_PAGE_TITLE_STRATA,                      # 瀏覽器分頁標題（任務 2）
            header_title=CHROME_HEADER_TITLE_STRATA,             # 頁內 header 主標（任務 4）
        )
        self.strata_view: StrataView | None = None
        self.build()
        self._build_page()
        self.blocks.queue(default_concurrency_limit=None)

    def _build_page(self):
        with self.blocks:
            self.strata_view = StrataView()
            self.strata_view.render(self.session_ctx)

            self.strata_view.register_events(self.session_ctx)

            # Manual device ID switch (generic)
            self.wire_generic_device_switch()

            # 裝置 ID 徽章/生成/IP 記錄 + 維護可見性閘門（Spec 任務 1/4/7）
            self.wire_maintenance_gate(
                [self.strata_view.container, self.toolbar_comp.row, self.dashboard_comp.sidebar],
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
                outputs=[self.strata_view.admin_tab.tab],
            )

            # 資源門檻滑桿：每次開頁從檔案重抓現值（任務 2）
            self.strata_view.admin_tab.wire_page_load(self.blocks)


PAGE = StrataPage()

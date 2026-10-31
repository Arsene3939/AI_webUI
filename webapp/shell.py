"""
Shared page chrome for the three module pages (Spec 2026-10-31, 方案A).

Every module page is its own gr.Blocks mounted at /<module>; this module keeps
what must stay identical across pages:
- APP_THEME: the pinned-dark gradio theme (moved out of app.py)
- TAB_SEGMENTS: the <module>/<tab> pseudo-path table (design red line: a tab is
  a URL *segment*, never a separate mount)
- TAB_ROUTER_JS: client-side deep-link <-> tab-button bridge
- WebPageScaffold: the session/header/sidebar/toolbar/timers block every page shares
"""
import gradio as gr

from config import get_server_status, SERVER_STATUS_UPDATING
from core.admin_manager import AdminManager
from core.session_context import SessionContext
from components.header import HeaderComponent, DEFAULT_HEADER_TITLE
from components.dashboard_sidebar import DashboardNavComponent
from components.comfy_toolbar import ComfyToolbarComponent
from task_manager import task_manager

# Dark app theme: the entire UI chrome (header/sidebar/status boxes) is dark by design,
# so the gradio theme is pinned dark (light AND dark variants of each token) to stop
# a light-OS system from rendering black text on our dark backgrounds.
APP_THEME = gr.themes.Default(primary_hue="blue").set(
    body_background_fill="#0b1220", body_background_fill_dark="#0b1220",
    body_text_color="#e2e8f0", body_text_color_dark="#e2e8f0",
    body_text_color_subdued="#94a3b8", body_text_color_subdued_dark="#94a3b8",
    block_background_fill="#111c2e", block_background_fill_dark="#111c2e",
    block_border_color="#243550", block_border_color_dark="#243550",
    block_title_text_color="#e2e8f0", block_title_text_color_dark="#e2e8f0",
    block_label_text_color="#9fb3c8", block_label_text_color_dark="#9fb3c8",
    block_info_text_color="#94a3b8", block_info_text_color_dark="#94a3b8",
    input_background_fill="#16233b", input_background_fill_dark="#16233b",
    input_border_color="#334155", input_border_color_dark="#334155",
    input_placeholder_color="#64748b", input_placeholder_color_dark="#64748b",
    link_text_color="#38bdf8", link_text_color_dark="#38bdf8",
    code_background_fill="#16233b", code_background_fill_dark="#16233b",
)

# URL pseudo-routing table: /<module>/<tab-segment>. Order MUST match the on-page
# tab order — the router JS maps segment index -> the nth tab button to click.
TAB_SEGMENTS = {
    "minimax": ["i2v", "t2v", "r2v", "history", "admin"],
    "upscaler": ["upscale", "history", "admin"],
    "strata": ["chat", "admin"],
}

LAST_PAGE_STORAGE_KEY = "webui_last_page"

# Client-side tab router (mounted into every page's <head>):
#  1. remembers the last module visited (localStorage, read by the "/" redirector)
#  2. deep link -> tab: on load, if /<module>/<segment> was served (server rewrites
#     to the module index), click the matching tab button once the UI is ready
#  3. tab click -> URL: keep the address bar in sync via history.replaceState, so
#     refreshing or bookmarking lands back on the same tab
TAB_ROUTER_JS = """
<script>
(function () {
    var TAB_MAP = %TAB_MAP%;
    var SEG_RE = /^[a-z]+$/;
    function parts() { return location.pathname.split('/').filter(function (s) { return s.length; }); }
    function moduleName() {
        var p = parts();
        return (p.length && TAB_MAP[p[0]]) ? p[0] : null;
    }
    // 1. remember last visited module for the "/" redirect page
    try {
        var m = moduleName();
        if (m) localStorage.setItem('%STORAGE_KEY%', '/' + m);
    } catch (e) {}

    function tabButtons() {
        var navs = document.querySelectorAll('.tab-nav');
        if (!navs.length) return [];
        return Array.prototype.slice.call(navs[0].querySelectorAll('button'));
    }
    function applyDeepLink() {
        var m = moduleName();
        if (!m) return true;
        var p = parts();
        var idx = p.length >= 2 ? TAB_MAP[m].indexOf(p[1]) : -1;
        if (idx < 0) return true;            // no tab to apply (bare module url)
        var btns = tabButtons();
        if (btns.length <= idx) return false; // UI not ready yet, retry
        if (!btns[idx].classList.contains('selected')) btns[idx].click();
        return true;
    }
    function bindTabPush() {
        var nav = document.querySelector('.tab-nav');
        if (!nav) return false;
        if (nav.__webuiTabBound) return true;
        nav.__webuiTabBound = true;
        nav.addEventListener('click', function (ev) {
            var btn = ev.target && ev.target.closest ? ev.target.closest('button') : null;
            var m = moduleName();
            if (!btn || !m) return;
            var idx = tabButtons().indexOf(btn);
            if (idx < 0 || !TAB_MAP[m][idx]) return;
            history.replaceState(null, '', '/' + m + '/' + TAB_MAP[m][idx]);
        });
        return true;
    }
    var tries = 0;
    var iv = setInterval(function () {
        tries++;
        if ((applyDeepLink() && bindTabPush()) || tries > 30) clearInterval(iv);
    }, 200);
})();
</script>
"""


def build_tab_router_js() -> str:
    """Inject the segment table / storage key into the router template."""
    return (
        TAB_ROUTER_JS
        .replace("%TAB_MAP%", str(TAB_SEGMENTS).replace("'", '"'))
        .replace("%STORAGE_KEY%", LAST_PAGE_STORAGE_KEY)
    )


class WebPageScaffold:
    """
    The shared top-of-page block every module page renders identically:
    per-browser session states, header banner, sidebar nav (this page active),
    ComfyUI toolbar and the status/task poll timers.
    Each page owns its own SessionContext/gr.Blocks instance — BrowserStates are
    keyed by storage_key, so device IDs stay shared across pages by design.
    """

    module_key: str = ""

    def __init__(self, title: str = "MiniMax-H3 AI Video WebUI", header_title: str = DEFAULT_HEADER_TITLE):
        self.title = title
        self.header_title = header_title
        self.blocks: gr.Blocks | None = None
        self.session_ctx: SessionContext | None = None
        self.device_id_state = None
        self.session_task_state = None
        self.header_comp: HeaderComponent | None = None
        self.dashboard_comp: DashboardNavComponent | None = None
        self.toolbar_comp: ComfyToolbarComponent | None = None
        self.backend_poll_timer = None
        self.task_poll_timer = None

    def build(self) -> "WebPageScaffold":
        with gr.Blocks(title=self.title, fill_width=True) as self.blocks:
            # 1. Strictly isolated persistent states per browser/device LocalStorage
            self.session_ctx = SessionContext().render()
            self.device_id_state = self.session_ctx.device_id_state
            self.session_task_state = self.session_ctx.session_task_state

            # 2. Header Banner & Device ID Controls
            self.header_comp = HeaderComponent(header_title=self.header_title).render()

            # 3. Sidebar Dashboard (page links; this page is the active one)
            self.dashboard_comp = DashboardNavComponent(active_module=self.module_key).render()

            # 4. ComfyUI Backend Control Toolbar
            self.toolbar_comp = ComfyToolbarComponent().render()

            # 5. Auto poll timers for backend status and active task polling
            self.backend_poll_timer = gr.Timer(value=0.5)
            self.task_poll_timer = gr.Timer(value=1.0)
            self.toolbar_comp.register_events(timer=self.backend_poll_timer)
            self.header_comp.register_toggle_events()
        return self

    def wire_generic_device_switch(self):
        """
        Header 'save manual device id' wiring for pages without the minimax-style
        full state restoration: just retarget the BrowserStates and repaint the
        header; each page's own poll timer then re-syncs that device's tasks.
        """
        from components.header import build_header_html
        from core.session_context import SessionContext as _SC

        edit_row = self.header_comp.edit_id_row
        manual_input = self.header_comp.manual_id_input
        save_btn = self.header_comp.save_id_btn

        def switch_device_id(custom_id, current_device_id, request: gr.Request = None):
            val = (custom_id or "").strip()
            if not val:
                return (
                    gr.update(visible=False),
                    gr.update(),
                    gr.update(),
                    build_header_html(device_id=current_device_id, title=self.header_title),
                )
            target_id = _SC.ensure_device_id(val)
            client = getattr(request, "client", None)
            if client is not None:
                task_manager.record_device_ip(target_id, getattr(client, "host", ""))
            return gr.update(visible=False), target_id, "", build_header_html(device_id=target_id, title=self.header_title)

        outputs = [edit_row, self.device_id_state, self.session_task_state, self.header_comp.header_html]
        save_btn.click(switch_device_id, inputs=[manual_input, self.device_id_state], outputs=outputs)
        manual_input.submit(switch_device_id, inputs=[manual_input, self.device_id_state], outputs=outputs)

    def wire_maintenance_gate(self, gated: list, own_header: bool = False):
        """
        維護可見性閘門（Spec 2026-10-31 任務 7）：
        SERVER_STATUS=UPDATING 時，非管理員（is_super_user 為 False）在任何模組頁
        都只看到 header 的「🔧 伺服器維護/更新中」橫幅，gated 列出的所有頁面主體
        全部隱藏；維護結束的瞬間由 0.5s timer 自動恢復，不需重新整理。

        own_header=True（/upscaler、/strata 用）：同一個 load handler 順帶確保
        裝置 ID 存在、記錄連線 IP（任務 1）、重繪 header 裝置徽章（任務 4）——
        單一寫入者，不會和 minimax 那套 restore 重繪打架。
        own_header=False（/minimax 用）：ID／header／IP 都歸該頁自己的
        restore_device_state 管，這裡只做可見性閘門。
        """
        from components.header import build_header_html

        def is_blocked(request) -> bool:
            return get_server_status() == SERVER_STATUS_UPDATING and not AdminManager.is_super_user(request)

        def record_ip(dev_id, request):
            client = getattr(request, "client", None)
            if client is not None:
                task_manager.record_device_ip(dev_id, getattr(client, "host", ""))

        if own_header:
            def load_gate(device_id, request: gr.Request = None):
                target = SessionContext.ensure_device_id(device_id)
                record_ip(target, request)
                blocked = is_blocked(request)
                header = build_header_html(device_id=target, title=self.header_title)
                return (target, header, *(gr.update(visible=not blocked) for _ in gated))

            self.blocks.load(
                load_gate,
                inputs=[self.device_id_state],
                outputs=[self.device_id_state, self.header_comp.header_html, *gated],
                api_name=False,
            )
        else:
            def load_gate(device_id, request: gr.Request = None):
                record_ip(device_id, request)
                blocked = is_blocked(request)
                return tuple(gr.update(visible=not blocked) for _ in gated)

            self.blocks.load(
                load_gate,
                inputs=[self.device_id_state],
                outputs=list(gated),
                api_name=False,
            )

        # 維護開始/結束的即時切換：可見性狀態沒變就完全不寫輸出（避免每 0.5s 重繪）
        _last_blocked: dict = {}

        def tick_gate(device_id, request: gr.Request = None):
            blocked = is_blocked(request)
            if _last_blocked.get("state") == blocked:
                return (gr.update(), *(gr.update() for _ in gated))
            _last_blocked["state"] = blocked
            # 首次載入的競態防護：BrowserState 還沒寫回時不要蓋掉 restore 畫好的徽章
            header = build_header_html(device_id=device_id or None, title=self.header_title) if device_id else gr.update()
            return (header, *(gr.update(visible=not blocked) for _ in gated))

        self.backend_poll_timer.tick(
            tick_gate,
            inputs=[self.device_id_state],
            outputs=[self.header_comp.header_html, *gated],
            api_name=False,
        )

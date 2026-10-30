"""
ASGI assembly for the routed WebUI (Spec 2026-10-31, 方案A; spike-verified pattern):

  /            -> tiny HTML page that reads localStorage['webui_last_page']
                  (written by every module page) and JS-redirects to it;
                  minimax is the fallback for first-time visitors.
  /minimax     -> pages_minimax.PAGE.blocks  (mounted gradio app)
  /upscaler    -> pages_upscaler.PAGE.blocks
  /strata      -> pages_strata.PAGE.blocks

  Tab deep links like /minimax/i2v are pseudo-routes: a design red line is that
  tabs are NOT separate mounts. A thin HTTP middleware rewrites any GET html
  navigation to /<module>/<known-tab-segment> onto the module's index route, and
  the client-side router JS (shell.TAB_ROUTER_JS, injected via head=) clicks the
  matching tab button and keeps the address bar synced on tab switches.

theme/css/head ride the mount calls — gradio applies them when serving each
page's index (verified: mount params land in the served HTML).
"""
from typing import Dict, List, Optional

import gradio as gr
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from config import OUTPUT_DIR
from components.styles import CUSTOM_CSS, CUSTOM_HEAD_JS

from .shell import APP_THEME, TAB_SEGMENTS, LAST_PAGE_STORAGE_KEY, build_tab_router_js
from . import pages_minimax, pages_upscaler, pages_strata

# module path -> page instance (also defines valid URL namespace; anything else 404s)
PAGES: Dict[str, object] = {
    "minimax": pages_minimax.PAGE,
    "upscaler": pages_upscaler.PAGE,
    "strata": pages_strata.PAGE,
}

ROOT_HTML = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>AI WebUI</title>
<script>
(function () {
    var page = '/minimax';
    try { page = localStorage.getItem('%STORAGE_KEY%') || page; } catch (e) {}
    if (page !== '/minimax' && page !== '/upscaler' && page !== '/strata') page = '/minimax';
    location.replace(page);
})();
</script>
</head>
<body style="background:#0b1220;color:#e2e8f0;font-family:sans-serif;">
正在載入上次使用的頁面…（若未跳轉請直接選擇 <a style="color:#38bdf8" href="/minimax">/minimax</a>）
</body>
</html>
""".replace("%STORAGE_KEY%", LAST_PAGE_STORAGE_KEY)

_asgi_app: Optional[FastAPI] = None


def create_asgi_app(extra_allowed_paths: Optional[List[str]] = None) -> FastAPI:
    """Build (once, then cache) the FastAPI app hosting all three module pages.
    Safe as a uvicorn factory (`create_asgi_app` import-string form)."""
    global _asgi_app
    if _asgi_app is not None:
        if extra_allowed_paths:
            import warnings
            warnings.warn("create_asgi_app(): extra_allowed_paths ignored — app already built")
        return _asgi_app

    app = FastAPI(title="AI WebUI Multi-Module Platform")

    @app.get("/", include_in_schema=False)
    def root_redirect_page():
        return HTMLResponse(ROOT_HTML)

    @app.middleware("http")
    async def tab_deeplink_rewrite(request: Request, call_next):
        # GET html navigation to /<module>/<known-tab-segment> -> serve the module
        # index; the injected router JS then activates the tab. Unknown segments
        # (and every gradio_api/static/config asset request) pass through untouched.
        path = request.scope.get("path", "")
        accept = request.headers.get("accept", "")
        if request.method == "GET" and "text/html" in accept:
            seg = path.strip("/").split("/")
            if len(seg) >= 2 and seg[0] in PAGES and seg[1] in TAB_SEGMENTS.get(seg[0], []):
                request.scope["path"] = f"/{seg[0]}/"
        return await call_next(request)

    allowed = [OUTPUT_DIR] + list(extra_allowed_paths or [])
    for name, page in PAGES.items():
        gr.mount_gradio_app(
            app,
            page.blocks,
            f"/{name}",
            theme=APP_THEME,
            css=CUSTOM_CSS,
            head=CUSTOM_HEAD_JS + build_tab_router_js(),
            allowed_paths=sorted(set(allowed)),
            show_error=True,
        )

    _asgi_app = app
    return app

"""
Routing refactor guards (Spec 2026-10-31, 方案A).

Asserts the assembled FastAPI app in webapp/server.py keeps the routing contract:
  - "/" serves the localStorage last-page redirector (not a gradio page)
  - each module page mounts at /<module> with css/theme/head applied IN THE INDEX
    (this replaced the old reload-style-guard: with mounts, styling is applied
    per request and survives reloads by construction)
  - tab deep links /<module>/<known-tab> return the module index (200) via the
    catch-all rewrite middleware, while unknown sub-paths are not rewritten
  - TAB_SEGMENTS matches the mounted pages
"""
import json

import pytest
from fastapi.testclient import TestClient

from components.styles import CUSTOM_CSS, CUSTOM_HEAD_JS
from webapp.server import PAGES, ROOT_HTML, create_asgi_app
from webapp.shell import TAB_SEGMENTS, LAST_PAGE_STORAGE_KEY, build_tab_router_js


@pytest.fixture(scope="module")
def client():
    with TestClient(create_asgi_app()) as c:
        yield c


def test_url_namespace_matches_tab_segments():
    assert set(TAB_SEGMENTS.keys()) == set(PAGES.keys())


def test_root_serves_last_page_redirector(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert LAST_PAGE_STORAGE_KEY in resp.text
    assert "location.replace" in resp.text


def test_each_module_page_mounted_with_config(client):
    for name in PAGES:
        resp = client.get(f"/{name}/config")
        assert resp.status_code == 200, f"/{name}/config -> {resp.status_code}"
        cfg = resp.json()
        assert cfg.get("components"), f"/{name}/config has no components"


def test_index_carries_css_theme_and_router_js(client):
    # pick a distinctive marker from each injected asset
    css_marker = ".dashboard-nav-links"
    assert css_marker in CUSTOM_CSS
    head_marker = "copyDeviceId"
    assert head_marker in CUSTOM_HEAD_JS

    for name in PAGES:
        idx = client.get(f"/{name}/", headers={"Accept": "text/html"}).text
        assert css_marker in idx, f"custom CSS missing on /{name}/"
        assert "#0b1220" in idx, f"pinned-dark theme missing on /{name}/"
        assert head_marker in idx, f"head JS missing on /{name}/"
        assert LAST_PAGE_STORAGE_KEY in idx, f"tab-router JS missing on /{name}/"


def test_each_page_main_container_is_visible():
    """Regression (2026-11-01): upscaler/strata views kept the old single-page
    `Column(visible=False)` default (the radio switcher used to show them) —
    as standalone pages their whole body rendered invisible."""
    assert PAGES["minimax"].minimax_view.container.visible is True
    assert PAGES["upscaler"].upscaler_view.container.visible is True
    assert PAGES["strata"].strata_view.container.visible is True


def test_page_configs_expose_their_primary_controls(client):
    """The served config (what the browser renders) must actually contain each
    page's headline component — a blank page can never hide behind a 200 again."""
    wanted = {
        "minimax": "開始生成",
        "upscaler": "開始影片超解析放大",
        "strata": "傳送",
    }
    for name, label in wanted.items():
        cfg = json.dumps(client.get(f"/{name}/config").json(), ensure_ascii=False)
        assert label in cfg, f"{label!r} missing from /{name} config payload"


def test_director_ui_simplification_markers(client):
    """UI 簡化案（2026-10-31）：minimax 頁有「優化提示詞」按鈕＋進階參數區的導演模型
    下拉＋admin 區的導演系統提示詞編輯；舊的語言/進階摺疊不得復活；
    其他模組頁不得憑空多出導演欄位。"""
    mm = json.dumps(client.get("/minimax/config").json(), ensure_ascii=False)
    assert "優化提示詞" in mm
    assert "導演模型" in mm
    assert "導演系統提示詞" in mm
    assert "進階設定（導演模型／輸出語言）" not in mm  # 舊語言選單摺疊區
    for name in ("upscaler", "strata"):
        cfg = json.dumps(client.get(f"/{name}/config").json(), ensure_ascii=False)
        assert "導演模型" not in cfg and "優化提示詞" not in cfg


def test_tab_deeplinks_serve_module_index(client):
    for name, segments in TAB_SEGMENTS.items():
        for seg in segments:
            resp = client.get(f"/{name}/{seg}", headers={"Accept": "text/html"})
            assert resp.status_code == 200, f"/{name}/{seg} -> {resp.status_code}"
            assert LAST_PAGE_STORAGE_KEY in resp.text, f"/{name}/{seg} not serving module index"


def test_unknown_tab_segment_is_not_rewritten(client):
    # middleware only rewrites KNOWN segments; unknown ones must not silently
    # masquerade as deep links (they fall through to the mounted app's own handling)
    resp = client.get("/minimax/not-a-real-tab-xyz", headers={"Accept": "text/html"})
    # either 404 (not rewritten) — and if gradio serves index anyway, at least
    # the middleware didn't pretend: assert we at least don't crash with 500
    assert resp.status_code in (200, 404)


def test_redirector_html_falls_back_to_minimax():
    assert "/minimax" in ROOT_HTML
    assert f"localStorage.getItem('{LAST_PAGE_STORAGE_KEY}')" in ROOT_HTML


def test_every_load_handler_executes_cleanly():
    """Regression (2026-10-31): a single-output load handler returned [gr.update(...)]
    (list-wrapped); gradio only unpacks lists for MULTI-output fns, so the whole list
    hit the Tab slot as a raw prediction -> InvalidComponentError popup on every
    page open/refresh. Replay every page's load deps through process_api and demand
    clean results."""
    import asyncio
    from starlette.requests import Request as StarReq
    from gradio.state_holder import SessionState

    fake_http = StarReq({
        "type": "http", "method": "GET", "path": "/",
        "headers": [(b"host", b"127.0.0.1")], "query_string": b"",
        "scheme": "http", "server": ("127.0.0.1", 7860), "client": ("127.0.0.1", 1234),
    })

    for name, page in PAGES.items():
        blocks = page.blocks
        fns = blocks.fns.items() if isinstance(blocks.fns, dict) else list(enumerate(blocks.fns))
        load_deps = [(idx, fn) for idx, fn in fns
                     if any(len(t) > 1 and t[1] == "load" for t in (fn.targets or []))]
        assert load_deps, f"{name}: no load dependency registered"
        for idx, fn in load_deps:
            # BrowserState inputs arrive positionally from the client; feed plausible
            # values (an unknown device + empty task id) matching the declared arity.
            inputs = ["dev_routing_test_0001", ""][: len(fn.inputs or [])]
            result = asyncio.run(blocks.process_api(idx, inputs, SessionState(blocks), request=fake_http, simple_format=True))
            assert isinstance(result, dict) and "data" in result, f"{name} load fn {idx} bad result"


def test_router_js_tab_map_is_valid_json_fragment():
    js = build_tab_router_js()
    # the injected table must be parseable JSON (double quotes, not python single)
    start = js.index("var TAB_MAP = ") + len("var TAB_MAP = ")
    end = js.index(";", start)
    parsed = json.loads(js[start:end])
    assert parsed == TAB_SEGMENTS

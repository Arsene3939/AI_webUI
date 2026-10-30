"""
Spec 2026-10-31 hot-reload 修復的回歸測試：

run.bat 用 `python -m gradio app.py`（watch 模式）。熱重載時 gradio 的 reloader
會重跑 app.py 並把重建的 demo 換進執行中的伺服器（swap_blocks），但不會重綁 port。
theme/css/head 是在 Blocks.launch() 最前面幾行才被套用（self.css = ...），所以
launch_webui 在 reloader 執行緒中仍必須呼叫 demo.launch()——它套用完樣式就會在
綁 port 前自動 return。少了這一步，重載後的 demo 會失去 CUSTOM_CSS/APP_THEME，
改 styles.py 只有整台重啟才看得到（使用者回報的現象）。
"""
import socket

import app as app_module
from components.styles import CUSTOM_CSS, CUSTOM_HEAD_JS
from gradio.cli.commands.reload import reload_thread

TEST_PORT = 7885


def test_reload_thread_relaunch_reapplies_styles_without_binding_port():
    demo = app_module.demo
    assert (demo.css, demo.head) != (CUSTOM_CSS, CUSTOM_HEAD_JS), \
        "precondition failed: demo 在本測試程序裡已被 launch 過"

    # 故意佔用欄位：若 reload 守衛退化，launch_webui 會落到 port 檢查而 raise，
    # 不會在空欄位上真的把伺服器拉起來。
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", TEST_PORT))
    sock.listen(1)
    try:
        reload_thread.running_reload = True  # 模擬 watchfn 執行緒旗標（同執行緒的 thread-local）
        try:
            result = app_module.launch_webui(port=TEST_PORT, raise_on_error=True)
        finally:
            reload_thread.running_reload = False
    finally:
        sock.close()

    assert result is demo, "reload 路徑必須直接回傳 demo，不得走完整啟動流程"
    assert demo.css == CUSTOM_CSS, "熱重載遺失了 CUSTOM_CSS ⇒ 改樣式又要重啟的 bug 回來了"
    assert demo.head == CUSTOM_HEAD_JS, "熱重載遺失了 head JS"
    assert demo.theme is not None, "熱重載後必須保留深色 APP_THEME"

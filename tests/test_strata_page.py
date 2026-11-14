"""
/strata 頁重建（Spec 2026-11-03）測試：設定檔持久化、strata_client（health／
SSE 串流／濾網欄位／啟動停止 subprocess 參數）、助理 toolbar 流程
（維護／已在運作／資源不足擋下→不啟動）、對話 handler（沒開→提示、串流組裝）、
UI 標記。全部走 mock，不碰真的 Strata 服務。
"""
import gradio as gr
import pytest

import config
from core import strata_client as sc


class TestStrataSettingsPersistence:
    def _file(self, monkeypatch, tmp_path):
        p = tmp_path / "strata_settings.json"
        monkeypatch.setattr(config, "STRATA_SETTINGS_FILE", str(p))
        return p

    def test_defaults_without_file(self, monkeypatch, tmp_path):
        self._file(monkeypatch, tmp_path)
        vals = config.get_strata_settings()
        assert vals["base_url"] == config._normalize_strata_base_url(config.STRATA_DEFAULT_BASE_URL)
        assert "api_key" in vals

    def test_save_roundtrip_and_url_normalization(self, monkeypatch, tmp_path):
        self._file(monkeypatch, tmp_path)
        ok, msg = config.set_strata_settings("http://127.0.0.1:9090/v1/", "kk")
        assert ok
        vals = config.get_strata_settings()
        assert vals["base_url"] == "http://127.0.0.1:9090"  # 尾斜線與 /v1 都剝掉
        assert vals["api_key"] == "kk"

    def test_rejects_bad_url(self, monkeypatch, tmp_path):
        self._file(monkeypatch, tmp_path)
        ok, _ = config.set_strata_settings("", "k")
        assert not ok
        ok2, _ = config.set_strata_settings("127.0.0.1:8080", "k")
        assert not ok2
        assert config.get_strata_settings()["base_url"] != "127.0.0.1:8080"

    def test_broken_file_falls_back_to_defaults(self, monkeypatch, tmp_path):
        p = self._file(monkeypatch, tmp_path)
        p.write_text("{ not json", encoding="utf-8")
        vals = config.get_strata_settings()
        assert vals["base_url"] == config._normalize_strata_base_url(config.STRATA_DEFAULT_BASE_URL)


class _FakeResp:
    def __init__(self, status_code=200, payload=None, lines=None):
        self.status_code = status_code
        self._payload = payload
        self._lines = lines or []

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def iter_lines(self):
        return iter(self._lines)

    def close(self):
        pass


class TestStrataClientHTTP:
    def test_health_down_returns_none(self, monkeypatch):
        def boom(*a, **k):
            raise ConnectionError("refused")
        monkeypatch.setattr(sc.requests, "get", boom)
        assert sc.health() is None

    def test_health_parses_dict(self, monkeypatch):
        sc._health_cache["ts"], sc._health_cache["data"] = 0.0, None
        monkeypatch.setattr(sc.requests, "get",
                            lambda url, timeout=None: _FakeResp(200, {"status": "ok", "model": "iq3_s"}))
        assert sc.health()["model"] == "iq3_s"

    def test_projection_field_mapping(self):
        # 濾網開 → projection off(False)；濾網關 → projection on(True)；未指定 → 不帶欄位
        assert sc.build_chat_payload([{}], filter_on=True)[sc._PROJECTION_FIELD] is False
        assert sc.build_chat_payload([{}], filter_on=False)[sc._PROJECTION_FIELD] is True
        assert sc._PROJECTION_FIELD not in sc.build_chat_payload([{}])

    def test_sse_stream_parses_deltas_and_done(self, monkeypatch):
        lines = [
            b': keep-alive',
            b'',
            b'data: {"choices":[{"delta":{"content":"\\u4f60\\u597d"}}]}',
            b'data: broken json {',
            b'data: {"choices":[{"delta":{"content":"\\u4e16\\u754c"}}]}',
            b'data: [DONE]',
        ]
        monkeypatch.setattr(sc.requests, "post",
                            lambda url, json=None, headers=None, stream=None, timeout=None: _FakeResp(200, lines=lines))
        events = list(sc.chat_stream([{"role": "user", "content": "x"}]))
        deltas = [t for k, t in events if k == "delta"]
        assert deltas == ["你好", "世界"]  # 壞行跳過、註解行跳過
        assert events[-1] == ("done", "")

    def test_sse_429_friendly(self, monkeypatch):
        monkeypatch.setattr(sc.requests, "post",
                            lambda *a, **k: _FakeResp(429, {"error": {"message": "admission_full"}}))
        events = list(sc.chat_stream([{}]))
        assert events[0][0] == "error" and "其他問題" in events[0][1]

    def test_connection_failure_friendly_not_raises(self, monkeypatch):
        def boom(*a, **k):
            raise ConnectionError("refused")
        monkeypatch.setattr(sc.requests, "post", boom)
        events = list(sc.chat_stream([{}]))
        assert events[0][0] == "error" and "啟動助理模型" in events[0][1]

    def test_chat_collect_error_carries_message(self, monkeypatch):
        monkeypatch.setattr(sc.requests, "post", lambda *a, **k: _FakeResp(500, {"error": "engine_died"}))
        ok, text, err = sc.chat_collect([{}])
        assert not ok and err

    def test_chat_collect_empty_answer_is_error(self, monkeypatch):
        monkeypatch.setattr(sc.requests, "post",
                            lambda *a, **k: _FakeResp(200, lines=[b"data: [DONE]"]))
        ok, _, err = sc.chat_collect([{}])
        assert not ok and "沒有回答" in err

    def test_start_backend_launches_runtime_profile_and_waits(self, monkeypatch, tmp_path):
        cli = tmp_path / "strata.cmd"
        cli.write_text("rem", encoding="utf-8")
        monkeypatch.setattr(sc, "STRATA_CLI_PATH", str(cli))
        monkeypatch.setattr(sc, "health", lambda timeout=3: None)  # 啟動前未在運作
        seen = {}
        monkeypatch.setattr(sc.subprocess, "Popen",
                            lambda cmd, **k: seen.setdefault("cmd", list(cmd)))
        monkeypatch.setattr(sc, "wait_ready", lambda timeout=None: True)
        ok, msg = sc.start_backend()
        assert ok and "上線" in msg
        assert seen["cmd"][1:] == ["runtime", "start", "--profile", sc.STRATA_LAUNCH_PROFILE]

    def test_start_backend_missing_cli(self, monkeypatch):
        monkeypatch.setattr(sc, "STRATA_CLI_PATH", r"Z:\nope\strata.cmd")
        monkeypatch.setattr(sc, "health", lambda timeout=3: None)
        ok, msg = sc.start_backend()
        assert not ok and "找不到" in msg

    def test_stop_backend_argv_and_rc(self, monkeypatch, tmp_path):
        cli = tmp_path / "strata.cmd"
        cli.write_text("rem", encoding="utf-8")
        monkeypatch.setattr(sc, "STRATA_CLI_PATH", str(cli))

        class R:
            returncode = 0
            stderr = b""
        seen = {}
        def fake_run(cmd, **k):
            seen["cmd"] = list(cmd)
            return R()
        monkeypatch.setattr(sc.subprocess, "run", fake_run)
        ok, msg = sc.stop_backend()
        assert ok and "已關閉" in msg
        assert seen["cmd"][1:] == ["runtime", "stop", "--profile", sc.STRATA_LAUNCH_PROFILE]

        class R2:
            returncode = 3
            stderr = b"not running"
        monkeypatch.setattr(sc.subprocess, "run", lambda cmd, **k: R2())
        ok2, _ = sc.stop_backend()
        assert not ok2


class _ToolbarModule:
    """components.strata_toolbar 的載入捷徑＋常用錨點（方便 monkeypatch）。"""

    def load(self, monkeypatch):
        import components.strata_toolbar as st
        monkeypatch.setattr(st, "get_server_status", lambda: config.SERVER_STATUS_OK)
        return st


class TestStrataToolbar:
    def test_maintenance_blocks_start(self, monkeypatch):
        st = _ToolbarModule().load(monkeypatch)
        monkeypatch.setattr(st, "get_server_status", lambda: config.SERVER_STATUS_UPDATING)
        tb = st.StrataToolbarComponent()
        updates = list(tb.on_start_backend())
        assert "維護" in updates[-1][1]

    def test_already_running_short_circuit(self, monkeypatch):
        st = _ToolbarModule().load(monkeypatch)
        monkeypatch.setattr(st, "is_up", lambda: True)
        started = []
        monkeypatch.setattr(st, "start_backend", lambda: started.append(1) or (True, ""))
        tb = st.StrataToolbarComponent()
        updates = list(tb.on_start_backend())
        assert "已經在運作中" in updates[-1][1]
        assert not started

    def test_resource_check_failure_prevents_start(self, monkeypatch):
        st = _ToolbarModule().load(monkeypatch)
        monkeypatch.setattr(st, "is_up", lambda: False)
        monkeypatch.setattr(st, "check_system_resources",
                            lambda: (False, "⚠️ 伺服器運算資源不足：可用 GPU 顯存 2.0 GB (需 > 6.0 GB)", {}))
        started = []
        monkeypatch.setattr(st, "start_backend", lambda: started.append(1) or (True, ""))
        tb = st.StrataToolbarComponent()
        updates = list(tb.on_start_backend())
        assert not started  # 資源不夠 → 一顆 start 都不呼叫
        assert "資源不足" in updates[-1][1] and "啟動後端模型" in updates[-1][1]  # 加了一句可操作提示

    def test_start_success_flow(self, monkeypatch):
        st = _ToolbarModule().load(monkeypatch)
        flags = {"up": False}
        monkeypatch.setattr(st, "is_up", lambda: flags["up"])
        monkeypatch.setattr(st, "check_system_resources", lambda: (True, "", {}))

        def fake_start():
            flags["up"] = True
            return True, "🟢 助理模型已上線，可以開始對話與導演"
        monkeypatch.setattr(st, "start_backend", fake_start)
        tb = st.StrataToolbarComponent()
        updates = list(tb.on_start_backend())
        assert "正在啟動助理模型" in updates[0][1]
        assert "上線" in updates[-1][1]
        assert tb._is_backend_starting is False
        assert tb.poll_backend_status()["value"] == "🟢 助理模型運作中"


class TestStrataChatHandlers:
    def _mod(self, monkeypatch):
        import views.strata.view as vw
        monkeypatch.setattr(vw, "is_up", lambda: False)
        return vw

    def test_not_up_yields_hint(self, monkeypatch):
        vw = self._mod(monkeypatch)
        view = vw.StrataView()
        history = [{"role": "user", "content": "hi"}]
        out = list(view._respond(list(history), "sys", 0.7, None))
        assert out[-1][-1] == {"role": "assistant", "content": vw.NOT_UP_MSG}

    def test_stream_appends_deltas(self, monkeypatch):
        vw = self._mod(monkeypatch)
        monkeypatch.setattr(vw, "is_up", lambda: True)
        captured = {}

        def fake_stream(messages, temperature=None, filter_on=None):
            captured["filter_on"] = filter_on
            return iter([("delta", "第一段"), ("delta", "第二段"), ("done", "")])
        monkeypatch.setattr(vw, "chat_stream", fake_stream)
        view = vw.StrataView()
        history = [{"role": "user", "content": "hi"}]
        out = list(view._respond(list(history), "sys", 0.7, None))
        assert out[-1][-1]["content"] == "第一段第二段"
        # 固定採不拒絕的自由回答（2026-11-03 使用者決定移除濾網開關）
        assert captured["filter_on"] is False

    def test_stream_error_keeps_partial_text(self, monkeypatch):
        vw = self._mod(monkeypatch)
        monkeypatch.setattr(vw, "is_up", lambda: True)
        monkeypatch.setattr(vw, "chat_stream",
                            lambda messages, temperature=None, filter_on=None: iter([
                                ("delta", "半段"), ("error", "⚠️ 中斷"),
                            ]))
        view = vw.StrataView()
        out = list(view._respond([{"role": "user", "content": "hi"}], "sys", 0.7, None))
        final = out[-1][-1]["content"]
        assert "半段" in final and "中斷" in final

    def test_image_downgrade_note_when_vision_off(self, monkeypatch):
        vw = self._mod(monkeypatch)
        monkeypatch.setattr(vw, "is_up", lambda: True)
        monkeypatch.setattr(vw, "vision_enabled", lambda: False)
        captured = {}

        def fake_stream(messages, temperature=None, filter_on=None):
            captured["messages"] = messages
            return iter([("delta", "ok"), ("done", "")])
        monkeypatch.setattr(vw, "chat_stream", fake_stream)
        view = vw.StrataView()
        out = list(view._respond([{"role": "user", "content": "看這張圖"}], "sys", 0.7, "Z:/nope.png"))
        assert captured["messages"][-1]["content"] == "看這張圖"  # 沒變成多模態 part
        assert "圖片未解讀" in out[-1][-1]["content"]

    def test_history_trimmed_to_recent_turns(self, monkeypatch):
        vw = self._mod(monkeypatch)
        monkeypatch.setattr(vw, "is_up", lambda: True)
        captured = {}
        monkeypatch.setattr(vw, "chat_stream",
                            lambda messages, temperature=None, filter_on=None: captured.setdefault("m", messages)
                            and iter([("delta", "x"), ("done", "")]))
        view = vw.StrataView()
        history = [{"role": "user", "content": f"t{i}"} for i in range(20)]
        list(view._respond(history, "S", 0.7, None))
        non_system = [m for m in captured["m"] if m["role"] != "system"]
        assert len(non_system) == 12
        assert captured["m"][0] == {"role": "system", "content": "S"}


class TestStrataPageUI:
    def test_view_renders_toolbar_chat_and_controls(self, monkeypatch):
        from core.session_context import SessionContext
        import views.strata.admin_tab as adm
        import views.strata.view as vw
        monkeypatch.setattr(adm, "health", lambda timeout=3: None)  # 建置期不打真網路
        with gr.Blocks():
            view = vw.StrataView()
            ctx = SessionContext().render()
            view.render(ctx)
            view.register_events(ctx)
            assert view.strata_toolbar.start_btn is not None
            assert view.strata_toolbar.stop_btn is not None
            assert view.strata_poll_timer is not None
            assert view.chatbot is not None
            assert not hasattr(view, "censor_filter")  # 濾網開關已移除，一律不拒絕
            assert view.image_input is not None
            assert len(view.template_dd.choices) == len(vw.CHAT_TEMPLATES)

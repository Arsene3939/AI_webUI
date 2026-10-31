"""
Unit tests for the Film Director pipeline (config scan, workflow builder,
history text extraction, client call flow) — Spec 2026-11-01 task 1.
"""
import json

import pytest

import config
import task_manager
from core import director_client as dc
from core.director_builder import build_director_workflow, split_director_output


class TestDirectorModelScan:
    def test_scan_filters_and_orders(self, tmp_path, monkeypatch):
        (tmp_path / "qwen3vl_8b_nvfp4.safetensors").write_bytes(b"x")
        (tmp_path / "qwen3vl_4b_fp8_scaled.safetensors").write_bytes(b"x")
        # H3 conditioning checkpoint: truncated (no lm_head) -> must NEVER be offered
        (tmp_path / "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors").write_bytes(b"x")
        (tmp_path / "umt5_xxl_fp8.safetensors").write_bytes(b"x")
        models = config.get_director_models(str(tmp_path))
        assert "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors" not in models
        assert "umt5_xxl_fp8.safetensors" not in models
        assert models == ["qwen3vl_8b_nvfp4.safetensors", "qwen3vl_4b_fp8_scaled.safetensors"]  # default first

    def test_empty_dir_yields_empty(self, tmp_path):
        assert config.get_director_models(str(tmp_path / "nope")) == []


class TestDirectorGraph:
    def test_graph_without_image(self):
        g = build_director_workflow(brief="讓她轉頭", clip_name="qwen3vl_8b_nvfp4.safetensors")
        assert g["1"]["class_type"] == "CLIPLoader"
        assert g["1"]["inputs"]["clip_name"] == "qwen3vl_8b_nvfp4.safetensors"
        assert g["1"]["inputs"]["type"] == config.DIRECTOR_CLIP_TYPE
        assert g["1"]["inputs"]["device"] == config.DIRECTOR_CLIP_DEVICE
        gen = g["9"]
        assert gen["class_type"] == "TextGenerate"
        assert gen["inputs"]["clip"] == ["1", 0]
        assert "image" not in gen["inputs"]
        assert "讓她轉頭" in gen["inputs"]["prompt"]
        # DynamicCombo API 格式：combo 值＝選項鍵＋子欄位點分鍵（live spike 實測修正）
        assert gen["inputs"]["sampling_mode"] == "on"
        assert gen["inputs"]["sampling_mode.top_k"] == 64
        assert gen["inputs"]["sampling_mode.temperature"] == 0.7
        # graph must terminate in an output node or ComfyUI rejects with prompt_no_outputs
        assert g["10"]["class_type"] == "PreviewAny"
        assert g["10"]["inputs"]["source"] == ["9", 0]

    def test_graph_with_image_link(self):
        g = build_director_workflow(brief="x", clip_name="m.safetensors", image_filename="in/upload.png")
        assert g["2"]["class_type"] == "LoadImage"
        assert g["2"]["inputs"]["image"] == "in/upload.png"
        assert g["9"]["inputs"]["image"] == ["2", 0]

    def test_language_switch_selects_persona(self):
        g_en = build_director_workflow(brief="walk", clip_name="m.safetensors", language="en")
        assert "Film Director" in g_en["9"]["inputs"]["prompt"]
        g_zh = build_director_workflow(brief="walk", clip_name="m.safetensors", language="zh_en")
        assert "影片導演" in g_zh["9"]["inputs"]["prompt"]

    def test_graph_is_json_serializable(self):
        json.dumps(build_director_workflow(brief="x", clip_name="m.safetensors", image_filename="f"))


class TestOutputSplitting:
    def test_well_formed_zh_en(self):
        raw = "【導演筆記】逆光推近鏡頭\n【English Prompt】A woman slowly turns her head, camera pushing in, backlit golden hour."
        note, prompt = split_director_output(raw)
        assert note == "逆光推近鏡頭"
        assert prompt.startswith("A woman slowly turns")

    def test_well_formed_en_note(self):
        raw = "【Director Note】推拉鏡頭\n【English Prompt】neon rain slides down glass"
        note, prompt = split_director_output(raw)
        assert note == "推拉鏡頭"
        assert prompt == "neon rain slides down glass"

    def test_unformatted_reply_never_loses_prompt(self):
        note, prompt = split_director_output("just a plain paragraph the model dumped")
        assert note == ""
        assert prompt == "just a plain paragraph the model dumped"

    def test_empty(self):
        assert split_director_output("   ") == ("", "")


class TestHistoryTextExtraction:
    def test_classic_text_output(self):
        entry = {"outputs": {"9": {"text": ["【導演筆記】x\n【English Prompt】abc"]}}}
        assert "abc" in dc.extract_generated_text(entry)

    def test_generated_text_key(self):
        entry = {"outputs": {"5": {"generated_text": "hello"}}}
        assert dc.extract_generated_text(entry) == "hello"

    def test_empty_outputs(self):
        assert dc.extract_generated_text({"outputs": {}}) == ""
        assert dc.extract_generated_text({}) == ""


class TestDirectorModelAutoRefresh:
    """定時重掃目錄 → 只在清單真的變化時推更新給前端（免重啟網頁出現新模型）。"""

    def _scan(self, monkeypatch, models):
        import components.director_block as db
        monkeypatch.setattr(db, "get_director_models", lambda: list(models))
        return db

    def test_no_change_is_fully_noop(self, monkeypatch):
        db = self._scan(monkeypatch, ["qwen3vl_8b_nvfp4.safetensors"])
        seen = ["qwen3vl_8b_nvfp4.safetensors"]
        d, out, st, state = db.refresh_model_choices("qwen3vl_8b_nvfp4.safetensors", seen)
        assert "choices" not in d and "value" not in d and "interactive" not in d
        assert "visible" not in out
        assert "value" not in st
        assert state is seen  # scan state untouched → no churn

    def test_empty_to_empty_also_noop(self, monkeypatch):
        db = self._scan(monkeypatch, [])
        d, out, st, state = db.refresh_model_choices(None, [])
        assert "choices" not in d and state == []

    def test_new_model_appears_without_restart(self, monkeypatch):
        db = self._scan(monkeypatch, ["qwen3vl_8b_nvfp4.safetensors"])
        d, out, st, state = db.refresh_model_choices(None, [])
        assert d["choices"] == ["qwen3vl_8b_nvfp4.safetensors"]
        assert d["value"] == "qwen3vl_8b_nvfp4.safetensors" and d["interactive"] is True
        assert out["visible"] is True and st == ""
        assert state == ["qwen3vl_8b_nvfp4.safetensors"]

    def test_user_selection_survives_scan(self, monkeypatch):
        db = self._scan(monkeypatch, ["qwen3vl_8b_nvfp4.safetensors", "qwen3vl_4b_fp8_scaled.safetensors"])
        d, _, _, _ = db.refresh_model_choices(
            "qwen3vl_4b_fp8_scaled.safetensors", ["qwen3vl_8b_nvfp4.safetensors"]
        )
        assert d["value"] == "qwen3vl_4b_fp8_scaled.safetensors"  # 不被預設值蓋掉

    def test_model_removal_returns_to_not_ready(self, monkeypatch):
        db = self._scan(monkeypatch, [])
        d, out, st, state = db.refresh_model_choices("qwen3vl_8b_nvfp4.safetensors", ["qwen3vl_8b_nvfp4.safetensors"])
        assert d["value"] is None and d["interactive"] is False
        assert out["visible"] is False and db.NOT_READY in st
        assert state == []


class TestCallDirectorFlow:
    def _patch_env(self, monkeypatch, models=("qwen3vl_8b_nvfp4.safetensors",), server_ok=True):
        monkeypatch.setattr(dc, "get_director_models", lambda: list(models))
        monkeypatch.setattr(dc, "get_server_status", lambda: config.SERVER_STATUS_OK)
        monkeypatch.setattr(dc, "check_server", lambda u=None: (server_ok, "" if server_ok else "down"))
        monkeypatch.setattr(dc, "upload_media_file", lambda p, u=None: "inputs/up.png")
        dc._director_cache.clear()

    def test_maintenance_blocks(self, monkeypatch):
        monkeypatch.setattr(dc, "get_server_status", lambda: config.SERVER_STATUS_UPDATING)
        ok, note, msg = dc.call_director("hi")
        assert not ok and "維護" in msg

    def test_no_model_ready_message(self, monkeypatch):
        self._patch_env(monkeypatch, models=())
        ok, _, msg = dc.call_director("hi")
        assert not ok and "下載導演模型" in msg

    def test_backend_offline(self, monkeypatch):
        self._patch_env(monkeypatch, server_ok=False)
        ok, _, msg = dc.call_director("hi")
        assert not ok and "沒上線" in msg

    def test_happy_path_and_cache(self, monkeypatch):
        self._patch_env(monkeypatch)
        calls = {"queue": 0}

        def fake_queue(graph, client_id, server_url=None):
            calls["queue"] += 1
            return "pid-1"

        class FakeResp:
            status_code = 200
            def json(self):
                return {"pid-1": {"outputs": {"9": {"text": ["【導演筆記】思路\n【English Prompt】a cinematic shot"]}}, "status": {"status_str": "success"}}}

        monkeypatch.setattr(dc, "queue_prompt", fake_queue)
        monkeypatch.setattr(dc.requests, "get", lambda url, timeout=None: FakeResp())

        ok, note, prompt = dc.call_director("給她一個微笑", image_path=None, timeout=5)
        assert ok and note == "思路" and prompt == "a cinematic shot"
        assert calls["queue"] == 1

        # second identical call hits cache (no new queue)
        ok2, _, prompt2 = dc.call_director("給她一個微笑", image_path=None, timeout=5)
        assert ok2 and prompt2 == prompt and calls["queue"] == 1

    def test_oom_gets_actionable_hint(self, monkeypatch):
        self._patch_env(monkeypatch)
        monkeypatch.setattr(dc, "queue_prompt", lambda g, c, server_url=None: "pid-oom")

        class FakeResp:
            status_code = 200
            def json(self):
                return {"pid-oom": {"outputs": {}, "status": {"status_str": "error", "messages": [
                    ["execution_error", {"exception_message": "CUDA out of memory. Tried to allocate 6 GiB"}]]}}}

        monkeypatch.setattr(dc.requests, "get", lambda url, timeout=None: FakeResp())
        ok, _, msg = dc.call_director("hi", timeout=4)
        assert not ok and "显存不夠" in msg

    def test_queue_failure_friendly(self, monkeypatch):
        self._patch_env(monkeypatch)
        def boom(*a, **k):
            raise RuntimeError("conn refused")
        monkeypatch.setattr(dc, "queue_prompt", boom)
        ok, _, msg = dc.call_director("hi", timeout=2)
        assert not ok and "送件失敗" in msg

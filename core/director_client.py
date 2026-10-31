"""
Director invocation client (Spec 2026-11-01 task 1).

Lightweight synchronous call: upload the reference image, queue the
director graph, poll /history for the TextGenerate text output. Deliberately
NOT routed through TaskManager — director drafts are not video jobs and must
not pollute task history or the serial queue semantics.
"""
import hashlib
import os
import time
import uuid
from typing import Optional, Tuple

import requests

from config import (
    DIRECTOR_TIMEOUT_SECONDS,
    DEFAULT_DIRECTOR_MODEL,
    get_director_models,
    get_server_status,
    SERVER_STATUS_UPDATING,
)
from core.comfy_client import check_server, queue_prompt, upload_media_file
from utils.logger import get_logger

from .director_builder import build_director_workflow, split_director_output

logger = get_logger("Director")

# (image_hash, draft prompt, model) -> (note, prompt) — cheap re-runs are common
_director_cache: dict = {}
DIRECTOR_CACHE_LIMIT = 60


def _image_fingerprint(path: Optional[str]) -> str:
    if not path or not os.path.exists(path):
        return "noimg"
    st = os.stat(path)
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"{h.hexdigest()}:{st.st_size}"


def extract_generated_text(history_entry: dict) -> str:
    """Pulls TextGenerate's STRING output out of a /history entry (robust to
    both classic ('outputs'->{'text': [...]}) and newer result shapes)."""
    outputs = (history_entry or {}).get("outputs") or {}
    chunks = []
    for node_out in outputs.values():
        if not isinstance(node_out, dict):
            continue
        for key in ("text", "generated_text", "result"):
            val = node_out.get(key)
            if isinstance(val, str):
                chunks.append(val)
            elif isinstance(val, list):
                for v in val:
                    if isinstance(v, str):
                        chunks.append(v)
                    elif isinstance(v, dict) and isinstance(v.get("text"), str):
                        chunks.append(v["text"])
    return "\n".join(chunks).strip()


def call_director(
    brief: str,
    image_path: Optional[str] = None,
    model_name: Optional[str] = None,
    timeout: Optional[int] = None,
    force_refresh: bool = False,
    server_url: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """
    Returns (ok, note, prompt_or_error_message). All failures come back as
    (False, "", user-friendly Chinese sentence) — never raises to the UI.
    `note` stays empty under the unified single-paragraph output contract; it is
    kept only so legacy two-section outputs still split cleanly.
    """
    if get_server_status() == SERVER_STATUS_UPDATING:
        return False, "", "⚠️ 伺服器維護中，導演暫時休息，請稍後再試"

    models = get_director_models()
    model = model_name if (model_name and model_name in models) else (models[0] if models else None)
    if not model:
        return False, "", "導演尚未就緒：請先下載導演模型（qwen3vl 8B/4B）放到模型的 text_encoders 資料夾"

    if not brief or not brief.strip():
        return False, "", "請先在提示詞欄寫下你的想法，再讓導演幫你打磨"

    available, _ = check_server(server_url)
    if not available:
        return False, "", "後端伺服器沒上線，導演無法工作，請先啟動後端"

    cache_key = (_image_fingerprint(image_path), brief.strip(), model)
    if not force_refresh and cache_key in _director_cache:
        note, prompt = _director_cache[cache_key]
        return True, note, prompt

    try:
        image_fn = upload_media_file(image_path, server_url) if image_path and os.path.exists(image_path) else None
    except Exception as e:
        logger.warning("Director image upload failed: %s", e)
        return False, "", "參考圖片上傳失敗，請確認後端是否正常後再試一次"

    graph = build_director_workflow(
        brief=brief,
        clip_name=model,
        image_filename=image_fn,
        seed=int(uuid.uuid4().int % (2 ** 31)),
    )

    try:
        prompt_id = queue_prompt(graph, str(uuid.uuid4()), server_url)
    except Exception as e:
        logger.warning("Director queue failed: %s", e)
        return False, "", "導演工作送件失敗，請稍後再試"

    deadline = time.time() + (timeout or DIRECTOR_TIMEOUT_SECONDS)
    while time.time() < deadline:
        time.sleep(1.0)
        try:
            resp = requests.get(f"{server_url or _default_server()}/history/{prompt_id}", timeout=3)
            if resp.status_code == 200:
                entry = (resp.json() or {}).get(prompt_id)
                if entry:
                    status_info = (entry.get("status") or {})
                    raw = extract_generated_text(entry)
                    if raw:
                        note, prompt = split_director_output(raw)
                        if len(_director_cache) >= DIRECTOR_CACHE_LIMIT:
                            _director_cache.clear()
                        _director_cache[cache_key] = (note, prompt)
                        logger.info("Director draft ready (%d chars) model=%s", len(raw), model)
                        return True, note, prompt
                    if status_info.get("status_str") == "error":
                        # 12GB 显存 + 其他常駐程式是常見情境：給出可操作的建議而非制式錯誤
                        if "out of memory" in str(status_info).lower():
                            return False, "", "显存不夠，導演無法上工：請先關閉佔用显存的程式再試，或請管理員改用較小的導演模型"
                        return False, "", "導演執行時發生問題，請洽管理員查看後端記錄"
                    # entry present but no text yet? (execution finished w/o output) -> keep polling briefly
        except requests.RequestException:
            continue
    return False, "", "導演思考太久沒回應（可能模型太大或後端太忙），請稍後再試或改用較小的導演模型"


def _default_server() -> str:
    from config import COMFY_SERVER_URL
    return COMFY_SERVER_URL

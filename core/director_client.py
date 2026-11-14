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
    DIRECTOR_STRATA_LABEL,
    DIRECTOR_TIMEOUT_SECONDS,
    DEFAULT_DIRECTOR_MODEL,
    get_director_models,
    get_server_status,
    SERVER_STATUS_UPDATING,
)
from core import strata_client as sc
from core.comfy_client import check_server, queue_prompt, upload_media_file
from ui_text import (
    DIRECTOR_MSG_BACKEND_OFFLINE,
    DIRECTOR_MSG_IMAGE_UPLOAD_FAILED,
    DIRECTOR_MSG_MAINTENANCE,
    DIRECTOR_MSG_NO_MODEL,
    DIRECTOR_MSG_OOM,
    DIRECTOR_MSG_QUEUE_FAILED,
    DIRECTOR_MSG_RUNTIME,
    DIRECTOR_MSG_STRATA_FAILED,
    DIRECTOR_MSG_STRATA_FAILED_FMT,
    DIRECTOR_MSG_STRATA_OFFLINE,
    DIRECTOR_MSG_TIMEOUT,
    DIRECTOR_NEED_BRIEF,
)
from utils.logger import get_logger

from .director_builder import build_director_workflow, load_director_system_prompt, split_director_output

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
        return False, "", DIRECTOR_MSG_MAINTENANCE

    models = get_director_models()

    # 方案 B（Spec 2026-11-03）：下拉一律有「Strata 智慧助理」選項。選到它就走
    # 助理對話補完（完全不碰 ComfyUI，也不做任何顯存讓位）；沒開就請使用者
    # 先去 💬 Strata 頁啟動。ComfyUI 導演模型的路徑完全不動。
    if model_name == DIRECTOR_STRATA_LABEL or (not models and not model_name):
        return _call_director_strata(brief, image_path, force_refresh)

    model = model_name if (model_name and model_name in models) else (models[0] if models else None)
    if not model:
        return False, "", DIRECTOR_MSG_NO_MODEL

    if not brief or not brief.strip():
        return False, "", DIRECTOR_NEED_BRIEF

    available, _ = check_server(server_url)
    if not available:
        return False, "", DIRECTOR_MSG_BACKEND_OFFLINE

    cache_key = (_image_fingerprint(image_path), brief.strip(), model)
    if not force_refresh and cache_key in _director_cache:
        note, prompt = _director_cache[cache_key]
        return True, note, prompt

    try:
        image_fn = upload_media_file(image_path, server_url) if image_path and os.path.exists(image_path) else None
    except Exception as e:
        logger.warning("Director image upload failed: %s", e)
        return False, "", DIRECTOR_MSG_IMAGE_UPLOAD_FAILED

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
        return False, "", DIRECTOR_MSG_QUEUE_FAILED

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
                            return False, "", DIRECTOR_MSG_OOM
                        return False, "", DIRECTOR_MSG_RUNTIME
                    # entry present but no text yet? (execution finished w/o output) -> keep polling briefly
        except requests.RequestException:
            continue
    return False, "", DIRECTOR_MSG_TIMEOUT


def _default_server() -> str:
    from config import COMFY_SERVER_URL
    return COMFY_SERVER_URL


def _call_director_strata(
    brief: str,
    image_path: Optional[str],
    force_refresh: bool,
) -> Tuple[bool, str, str]:
    """
    Strata 導演路徑（方案 B）：同一套統一導演系統提示詞，走助理的對話補完；
    有第一幀參考圖且助理能看圖時附圖。回呼式失敗（(False, "", 中文訊息)），
    不假設 ComfyUI 在跑、也不做顯存讓位。
    """
    if not brief or not brief.strip():
        return False, "", DIRECTOR_NEED_BRIEF

    if sc.health() is None:
        return False, "", DIRECTOR_MSG_STRATA_OFFLINE

    cache_key = (_image_fingerprint(image_path), brief.strip(), DIRECTOR_STRATA_LABEL)
    if not force_refresh and cache_key in _director_cache:
        note, prompt = _director_cache[cache_key]
        return True, note, prompt

    user_text = f"【使用者提示詞草稿】\n{brief.strip()}"
    content = user_text
    if image_path and os.path.exists(image_path):
        if sc.vision_enabled():
            uri = sc.image_data_uri(image_path)
            if uri:
                content = [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": uri}},
                ]
        else:
            logger.info("Strata director: image attached but picture-reading is off; text-only draft")

    messages = [
        {"role": "system", "content": load_director_system_prompt()},
        {"role": "user", "content": content},
    ]
    # filter_on=False → 創作模式（不去濾鏡），與 ComfyUI 導演路徑的 behave 一致
    ok, text, err = sc.chat_collect(
        messages, temperature=0.7, filter_on=False, timeout=DIRECTOR_TIMEOUT_SECONDS,
    )
    if not ok:
        return False, "", DIRECTOR_MSG_STRATA_FAILED_FMT.format(err) if err else DIRECTOR_MSG_STRATA_FAILED

    note, prompt = split_director_output(text)
    if len(_director_cache) >= DIRECTOR_CACHE_LIMIT:
        _director_cache.clear()
    _director_cache[cache_key] = (note, prompt)
    logger.info("Strata director draft ready (%d chars)", len(text))
    return True, note, prompt

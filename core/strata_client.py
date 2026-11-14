"""
Strata 智慧助理客戶端（Spec 2026-11-03）。

封裝本機 Strata 推理服務的一切接觸面：
  - /health、/v1/status：免鑰狀態查詢（localhost，開銷可忽略）
  - /v1/chat/completions：OpenAI 相容對話補完，SSE 串流逐段出字
  - 啟動／停止：`strata runtime start|stop --profile …`（背景服務，視窗不閃）

設計紅線：所有失敗一律以 (ok, 友善中文訊息) 或 ("error", 訊息) 回來，
任何例外都不准竄到 UI 層；對話頁／導演只看這些訊息。
"""
import base64
import json
import mimetypes
import os
import subprocess
import time
from typing import Any, Dict, Generator, List, Optional, Tuple

import requests

from config import (
    STRATA_CLI_PATH,
    STRATA_LAUNCH_PROFILE,
    STRATA_START_TIMEOUT_S,
    get_strata_settings,
)
from ui_text import (
    STRATA_ALREADY_RUNNING_MSG,
    STRATA_ERR_BUSY,
    STRATA_ERR_CLI_MISSING,
    STRATA_ERR_EMPTY_ANSWER,
    STRATA_ERR_NOT_CONNECTED,
    STRATA_ERR_START_FAILED,
    STRATA_ERR_STOP_FAILED,
    STRATA_ERR_STOP_UNABLE,
    STRATA_ERR_STREAM_CUT,
    STRATA_ERR_STREAM_GENERIC,
    STRATA_ERR_TIMEOUT,
    STRATA_ERR_UNAVAILABLE,
    STRATA_START_LATE_MSG,
    STRATA_START_ONLINE_MSG,
    STRATA_STOPPED_MSG,
)
from utils.logger import get_logger

logger = get_logger("Strata")

# /health 的短效快取：toolbar 的 5s 輪詢與對話前檢查共用，
# 避免同一次操作內對本機重複發 HTTP（快取兩秒就過期，狀態顯示仍即時）。
_health_cache: Dict[str, Any] = {"ts": 0.0, "data": None}
_HEALTH_CACHE_TTL_S = 2.0

# 敏感內容開關已從 UI 移除（2026-11-03 使用者追加決定）：對話與導演一律
# 傳 filter_on=False ＝引擎 projection on＝預設不拒絕的自由回答。
# filter_on=None＝完全不帶該欄位，交給引擎預設（同樣是 on）。
_PROJECTION_FIELD = "experimental_speed_projection"


def _base_url() -> str:
    return get_strata_settings()["base_url"].rstrip("/")


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = get_strata_settings().get("api_key", "")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def health(timeout: int = 3) -> Optional[dict]:
    """GET /health（免鑰）。回 dict（含 status/model/max_context）或 None（沒上線）。"""
    try:
        resp = requests.get(f"{_base_url()}/health", timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, dict) else {"status": "ok"}
    except Exception:
        pass
    return None


def cached_health(max_age: float = _HEALTH_CACHE_TTL_S) -> Optional[dict]:
    now = time.time()
    if now - _health_cache["ts"] < max_age:
        return _health_cache["data"]
    data = health()
    _health_cache["ts"] = now
    _health_cache["data"] = data
    return data


def is_up() -> bool:
    return cached_health() is not None


def full_status(timeout: int = 4) -> Optional[dict]:
    """GET /v1/status：較詳細的即時狀態（vision.enabled 等）。失敗回 None。"""
    try:
        resp = requests.get(f"{_base_url()}/v1/status", headers=_headers(), timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, dict) else None
    except Exception:
        pass
    return None


def vision_enabled() -> bool:
    """助理目前能不能看圖（圖片解讀是 CPU 線，不吃顯存，通常常駐開啟）。"""
    st = full_status()
    if not st:
        return False
    vision = st.get("vision")
    return bool(isinstance(vision, dict) and vision.get("enabled"))


def image_data_uri(path: Optional[str]) -> Optional[str]:
    """把本機圖片檔轉成 OpenAI image_url 用的 data URI；讀不到回 None。"""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read()
        mime = mimetypes.guess_type(path)[0] or "image/png"
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
    except Exception as e:
        logger.warning("Strata image attach failed: %s", e)
        return None


def build_chat_payload(
    messages: List[dict],
    temperature: Optional[float] = None,
    filter_on: Optional[bool] = None,
    stream: bool = True,
    extra: Optional[dict] = None,
) -> dict:
    """組成 /v1/chat/completions request body（此 body 會原樣流進引擎 sampling）。"""
    payload: Dict[str, Any] = {"model": "strata", "messages": messages, "stream": stream}
    if temperature is not None:
        payload["temperature"] = float(temperature)
    if filter_on is not None:
        payload[_PROJECTION_FIELD] = (not filter_on)
    if extra:
        payload.update(extra)
    return payload


def chat_stream(
    messages: List[dict],
    temperature: Optional[float] = None,
    filter_on: Optional[bool] = None,
    timeout: int = 180,
) -> Generator[Tuple[str, str], None, None]:
    """
    串流對話補完。yield 事件元組：
      ("delta", 文字片段)… 逐段出字
      ("error", 友善中文訊息) 任何失敗（之後直接結束）
      ("done", "") 正常收完
    SSE 解析容忍 keep-alive 註解行與不完整的 JSON 行（跳過不中斷）。
    """
    payload = build_chat_payload(messages, temperature=temperature, filter_on=filter_on, stream=True)
    try:
        resp = requests.post(
            f"{_base_url()}/v1/chat/completions",
            json=payload,
            headers=_headers(),
            stream=True,
            timeout=(10, timeout),
        )
    except requests.Timeout:
        yield "error", STRATA_ERR_TIMEOUT
        return
    except Exception:
        yield "error", STRATA_ERR_NOT_CONNECTED
        return

    try:
        if resp.status_code == 429:
            yield "error", STRATA_ERR_BUSY
            return
        if resp.status_code != 200:
            detail = ""
            try:
                err = (resp.json() or {}).get("error")
                if isinstance(err, dict):
                    detail = str(err.get("message") or "")
                elif isinstance(err, str):
                    detail = err
            except Exception:
                pass
            logger.warning("Strata chat HTTP %s: %s", resp.status_code, detail)
            yield "error", STRATA_ERR_UNAVAILABLE
            return
        got_done = False
        for raw in resp.iter_lines():
            if not raw:
                continue  # SSE 空行（事件分隔）
            if not raw.startswith(b"data:"):
                continue  # ": keep-alive" 等註解行
            chunk = raw[5:].strip()
            if chunk == b"[DONE]":
                got_done = True
                break
            try:
                obj = json.loads(chunk.decode("utf-8", "replace"))
            except Exception:
                continue
            choices = obj.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            delta = (choices[0] or {}).get("delta") or {}
            piece = delta.get("content")
            if isinstance(piece, str) and piece:
                yield "delta", piece
        if not got_done:
            # 沒收到 [DONE] 卻自然結束：多半是引擎中途斷線，已出的字保留、不補錯誤
            pass
        yield "done", ""
    except requests.RequestException as e:
        logger.warning("Strata chat stream interrupted: %s", e)
        yield "error", STRATA_ERR_STREAM_CUT
    except Exception as e:
        logger.warning("Strata chat stream unexpected: %s", e)
        yield "error", STRATA_ERR_STREAM_GENERIC
    finally:
        try:
            resp.close()
        except Exception:
            pass


def chat_collect(
    messages: List[dict],
    temperature: Optional[float] = None,
    filter_on: Optional[bool] = None,
    timeout: int = 180,
) -> Tuple[bool, str, str]:
    """把 chat_stream 收整成一次成品的非串流版。回 (ok, 全文, 錯誤訊息)。"""
    pieces: List[str] = []
    err = ""
    for kind, text in chat_stream(messages, temperature=temperature, filter_on=filter_on, timeout=timeout):
        if kind == "delta":
            pieces.append(text)
        elif kind == "error":
            err = text
            break
    full = "".join(pieces).strip()
    if err:
        return False, full, err
    if not full:
        return False, "", STRATA_ERR_EMPTY_ANSWER
    return True, full, ""


def wait_ready(timeout: Optional[int] = None) -> bool:
    """輪詢 /health 直到助理上線或時間到（啟動流程用）。"""
    deadline = time.time() + (timeout if timeout is not None else STRATA_START_TIMEOUT_S)
    while time.time() < deadline:
        if health(timeout=2) is not None:
            return True
        time.sleep(2.0)
    return health(timeout=2) is not None


def _no_window_flags() -> int:
    # Windows：啟動／停止助理模型時不要閃出黑色命令視窗
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def start_backend() -> Tuple[bool, str]:
    """
    背景啟動助理模型（`strata runtime start --profile …`；這是會在自己身後
    繼續執行的背景服務，不需要命令視窗留著），之後輪詢 /health 直到就緒。
    回 (ok, 給 toolbar 狀態列的中文訊息)。
    """
    if health() is not None:
        return True, STRATA_ALREADY_RUNNING_MSG
    if not os.path.exists(STRATA_CLI_PATH):
        logger.error("Strata CLI missing: %s", STRATA_CLI_PATH)
        return False, STRATA_ERR_CLI_MISSING
    try:
        subprocess.Popen(
            [STRATA_CLI_PATH, "runtime", "start", "--profile", STRATA_LAUNCH_PROFILE],
            creationflags=_no_window_flags(),
        )
    except Exception as e:
        logger.error("Strata runtime start failed: %s", e)
        return False, STRATA_ERR_START_FAILED
    logger.warning("Strata runtime start issued (profile=%s), waiting for health...", STRATA_LAUNCH_PROFILE)
    if wait_ready():
        return True, STRATA_START_ONLINE_MSG
    return False, STRATA_START_LATE_MSG


def stop_backend() -> Tuple[bool, str]:
    """停止助理模型（drain 後關閉背景服務）。回 (ok, 中文訊息)。"""
    if not os.path.exists(STRATA_CLI_PATH):
        return False, STRATA_ERR_CLI_MISSING
    try:
        proc = subprocess.run(
            [STRATA_CLI_PATH, "runtime", "stop", "--profile", STRATA_LAUNCH_PROFILE],
            creationflags=_no_window_flags(),
            capture_output=True,
            timeout=90,
        )
    except Exception as e:
        logger.error("Strata runtime stop failed: %s", e)
        return False, STRATA_ERR_STOP_FAILED
    if proc.returncode == 0:
        _health_cache["ts"], _health_cache["data"] = 0.0, None  # 狀態立刻刷新給按鈕
        logger.warning("Strata runtime stopped (profile=%s)", STRATA_LAUNCH_PROFILE)
        return True, STRATA_STOPPED_MSG
    tail = ""
    try:
        tail = (proc.stderr or b"").decode("utf-8", "replace").strip()[:200]
    except Exception:
        pass
    logger.warning("Strata runtime stop rc=%s: %s", proc.returncode, tail)
    return False, STRATA_ERR_STOP_UNABLE

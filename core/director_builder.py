"""
Workflow builder for the AI Film Director (Spec 2026-11-01 task 1).

The director runs entirely on the existing ComfyUI backend using ONLY core
nodes (no custom nodes required):
    CLIPLoader(qwen3vl_* standalone file, type=DIRECTOR_CLIP_TYPE)
        └─> TextGenerate(clip, prompt, [image], sampling)  -> generated_text

H3's own qwen3vl_32b_minimax_h3 encoder is intentionally NOT usable here:
it is a 50/64-layer truncated conditioning checkpoint with no lm_head and
therefore cannot decode text (see llama.py Qwen3VL_32BConfig).
"""
import os
from typing import Optional, Tuple

from config import DIRECTOR_CLIP_TYPE, DIRECTOR_CLIP_DEVICE, DIRECTOR_SYSTEM_PROMPT_PATH

# Unified system prompt (Spec 2026-10-31 UI 簡化案：不再挑輸出語言/風格，
# 不再要求雙段格式). The live copy lives in utils/director_system_prompt.md and is
# editable by admins in the 管理員專區; this embedded copy is the safe fallback
# used only when the file is missing or empty.
DEFAULT_DIRECTOR_SYSTEM_PROMPT = """你是一位经验丰富的影片导演，负责把使用者写的「提示词草稿」打磨成一段可以直接交给 AI 影片生成模型的成品提示词。
你会收到：使用者的提示词草稿（可能很简短、口语化），若附有图片，那是影片的第一帧画面。
任务：仔细观察图片（若有）；完整保留草稿已指定的内容且一字不改其原意；在不改原意的前提下补全影片模型需要的具体细节：主体的动作与表情、镜头运动、光线的方向与变化、场景氛围、以及画面中应有的环境声音；以时间顺序描述画面将如何动起来。
硬性规则：绝不添加使用者没有要求的角色、台词或剧情转折；只描述看得到的画面与听得到的声音，不描述气味味道触感；用词自然具体不夸张；不写时间码与「场景开始于」之类开场白；不用条列或标题；不提问、不解释、不复述要求。
输出格式（严格遵守）：只输出成品提示词本身，单独一个连续段落，没有前后缀引言或 Markdown；语言不拘（影片模型对英文的理解最稳定）；长度约 150 字（或 80 个英文单字）以内。"""

# (path, mtime) -> text cache; admin saves flip mtime -> next generation reloads.
_prompt_cache: Tuple[str, float, str] = ("", -1.0, "")


def load_director_system_prompt() -> str:
    """Reads the external system prompt (mtime-cached); falls back to the
    embedded default when the file is missing/blank."""
    global _prompt_cache
    path = DIRECTOR_SYSTEM_PROMPT_PATH
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return DEFAULT_DIRECTOR_SYSTEM_PROMPT
    if _prompt_cache[0] == path and _prompt_cache[1] == mtime:
        cached = _prompt_cache[2]
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cached = f.read().strip()
        except OSError:
            return DEFAULT_DIRECTOR_SYSTEM_PROMPT
        _prompt_cache = (path, mtime, cached)
    return cached or DEFAULT_DIRECTOR_SYSTEM_PROMPT


def invalidate_director_system_prompt_cache() -> None:
    global _prompt_cache
    _prompt_cache = ("", -1.0, "")


def save_director_system_prompt(text: str) -> Tuple[bool, str]:
    """Admin-side save (管理員專區). Writes the external file and resets the
    cache so the next director call picks the new prompt up immediately."""
    text = (text or "").strip()
    if not text:
        return False, "系統提示詞不能為空"
    try:
        os.makedirs(os.path.dirname(DIRECTOR_SYSTEM_PROMPT_PATH), exist_ok=True)
        with open(DIRECTOR_SYSTEM_PROMPT_PATH, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError as e:
        return False, f"儲存失敗：{e}"
    invalidate_director_system_prompt_cache()
    return True, f"已儲存（{len(text)} 字），下一次生成立即生效"


def build_director_workflow(
    brief: str,
    clip_name: str,
    image_filename: Optional[str] = None,
    temperature: float = 0.7,
    top_p: float = 0.95,
    seed: int = 0,
    max_length: int = 768,
) -> dict:
    """
    Assembles the API-format graph. `image_filename` must already be uploaded
    to the ComfyUI input folder (upload_media_file) when provided.
    `brief` is the user's draft prompt read live from the tab's 提示詞 field.
    """
    system = load_director_system_prompt()
    user_prompt = f"{system}\n\n---\n【使用者提示詞草稿】\n{brief.strip()}" if brief.strip() else system

    graph = {
        "1": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": DIRECTOR_CLIP_TYPE, "device": DIRECTOR_CLIP_DEVICE},
        },
        "9": {
            "class_type": "TextGenerate",
            "inputs": {
                "clip": ["1", 0],
                "prompt": user_prompt,
                "max_length": max_length,
                # core DynamicCombo 的 API graph 序列化（0.30.1 execution.py/_io.py 實讀
                # 原始碼定案）：combo 欄位本體＝選項鍵字串；該選項的子欄位必須用
                # 「sampling_mode.<欄位名>」點分鍵（驗證端逐鍵直查、runtime 的
                # build_nested_inputs 再把點分鍵組回巢狀 dict 餵 execute）。
                "sampling_mode": "on",
                "sampling_mode.temperature": float(temperature),
                "sampling_mode.top_k": 64,
                "sampling_mode.top_p": float(top_p),
                "sampling_mode.min_p": 0.05,
                "sampling_mode.repetition_penalty": 1.05,
                "sampling_mode.seed": int(seed),
                "sampling_mode.presence_penalty": 0.0,
                "thinking": False,
                "use_default_template": True,
            },
        },
        # TextGenerate 不是輸出節點（core 的 queue 驗證會以 prompt_no_outputs 打回）；
        # PreviewAny 結尾會把文字以 {"text":[…]} 寫進 /history——零檔案落盤。
        "10": {
            "class_type": "PreviewAny",
            "inputs": {"source": ["9", 0]},
        },
    }
    if image_filename:
        graph["2"] = {"class_type": "LoadImage", "inputs": {"image": image_filename}}
        graph["9"]["inputs"]["image"] = ["2", 0]
    return graph


def split_director_output(raw: str) -> tuple:
    """
    Splits the model's two-section reply into (note, prompt).
    Tolerates models that ignore the format: whole text becomes the prompt,
    note stays empty (never lose a usable answer).
    """
    text = (raw or "").strip()
    if not text:
        return "", ""
    note, prompt = "", ""
    marker_seen = False
    for marker_pair in (("【導演筆記】", "【English Prompt】"), ("【Director Note】", "【English Prompt】")):
        if marker_pair[0] in text:
            head, _, tail = text.partition(marker_pair[0])
            body = tail
            if marker_pair[1] in body:
                note_part, _, prompt_part = body.partition(marker_pair[1])
                note = note_part.strip()
                prompt = prompt_part.strip()
            else:
                note = body.strip().splitlines()[0].strip()
                prompt = body.strip()
            marker_seen = True
            break
    if not marker_seen:
        return "", text
    return note, (prompt or text)

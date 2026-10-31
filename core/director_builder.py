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
from typing import Optional

from config import DIRECTOR_CLIP_TYPE, DIRECTOR_CLIP_DEVICE

# Director personas. The model receives: [system persona] + user brief (+ image).
# Output contract is enforced in-text so the UI can split/explain cheaply.
DIRECTOR_SYSTEM_ZH_EN = """你現在是「影片導演」，替本地端無審查影片模型 MiniMax-H3 撰寫生成提示詞。
任務：仔細觀察附上的圖片（首幀），融合使用者的口語需求，產出一段可直接使用的英文生成提示詞。
規則：
- 描述具體的畫面動態、角色動作、鏡頭運動、光線與氛圍；用現在進行式英文。
- 只描述畫面與聲音，不描述 smell/taste/touch；不使用夸张形容詞；不編造使用者沒要求的角色或對白。
- 使用者需求與圖片衝突時，以使用者需求為主，但維持與圖片的視覺連續性。
- 嚴格輸出格式（兩行開始）：
第一行以「【導演筆記】」開頭，用一句不超過 25 個字的中文說明你的導演思路。
第二行起以「【English Prompt】」開頭，接著 ONLY 一段連貫的英文提示詞（單一段落，無條列、無換行標題）。
不要輸出其他任何內容，不要提問。"""

DIRECTOR_SYSTEM_EN = """You are the "Film Director" writing prompts for the local uncensored video model MiniMax-H3.
Study the attached image (first frame) and fuse it with the user's casual request into ONE ready-to-use English prompt.
Rules:
- Concrete motion, character action, camera movement, lighting, mood; present-progressive English.
- Visuals and audio only; no invented characters or dialogue the user did not ask for.
- If the request conflicts with the image, follow the user but keep visual continuity.
- STRICT format: first line starts with "【Director Note】" plus one short Traditional-Chinese sentence (max 25 chars) explaining your direction. Second line starts with "【English Prompt】" followed by ONLY one coherent English paragraph. Nothing else. Never ask questions."""

LANGUAGE_SYSTEMS = {
    "zh_en": DIRECTOR_SYSTEM_ZH_EN,
    "en": DIRECTOR_SYSTEM_EN,
}


def build_director_workflow(
    brief: str,
    clip_name: str,
    image_filename: Optional[str] = None,
    language: str = "zh_en",
    temperature: float = 0.7,
    top_p: float = 0.95,
    seed: int = 0,
    max_length: int = 768,
) -> dict:
    """
    Assembles the API-format graph. `image_filename` must already be uploaded
    to the ComfyUI input folder (upload_media_file) when provided.
    """
    system = LANGUAGE_SYSTEMS.get(language, DIRECTOR_SYSTEM_ZH_EN)
    user_prompt = f"{system}\n\n使用者需求：{brief.strip()}" if brief.strip() else system

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

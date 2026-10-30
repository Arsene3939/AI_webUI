"""
Configuration and helper functions for MiniMax-H3 ComfyUI Gradio WebUI.
"""
import socket
import os
import math
import re
from typing import Tuple, Dict, Any, Union, Optional, List
from PIL import Image

# Server connection
if "NO_PROXY" not in os.environ:
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
elif "127.0.0.1" not in os.environ["NO_PROXY"]:
    os.environ["NO_PROXY"] = f"127.0.0.1,localhost,{os.environ['NO_PROXY']}"

COMFY_SERVER_URL = os.environ.get("COMFY_SERVER_URL", "http://127.0.0.1:8188")
COMFY_WS_URL = COMFY_SERVER_URL.replace("http://", "ws://").replace("https://", "wss://")

# Gradio WebUI Host and Port
WEBUI_HOST = os.environ.get("WEBUI_HOST", "0.0.0.0")
WEBUI_PORT = int(os.environ.get("WEBUI_PORT", "7860"))

# Server Operation Status Flag
SERVER_STATUS_OK = "OK"
SERVER_STATUS_UPDATING = "UPDATING"
SERVER_STATUS = SERVER_STATUS_OK
SERVER_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".server_status")

def get_server_status() -> str:
    """Returns current server operation status ('OK' or 'UPDATING')."""
    test_override = os.environ.get("TEST_OVERRIDE_STATUS")
    if test_override in (SERVER_STATUS_OK, SERVER_STATUS_UPDATING):
        return test_override
    if os.path.exists(SERVER_STATUS_FILE):
        try:
            with open(SERVER_STATUS_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content in (SERVER_STATUS_OK, SERVER_STATUS_UPDATING):
                    return content
        except Exception:
            pass
    return os.environ.get("SERVER_STATUS", SERVER_STATUS)

def set_server_status(status: str):
    """Sets current server operation status ('OK' or 'UPDATING')."""
    global SERVER_STATUS
    SERVER_STATUS = status
    os.environ["SERVER_STATUS"] = status
    try:
        with open(SERVER_STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(status)
    except Exception:
        pass


# Startup System Resource Thresholds (Spec Task 2)
MIN_STARTUP_RAM_GB = float(os.environ.get("MIN_STARTUP_RAM_GB", "50.0"))
MAX_STARTUP_GPU_UTIL = float(os.environ.get("MAX_STARTUP_GPU_UTIL", "20.0"))
MIN_STARTUP_VRAM_GB = float(os.environ.get("MIN_STARTUP_VRAM_GB", "9.5"))

# Default Models (MiniMax-H3)
DEFAULT_UNET = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
DEFAULT_CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
DEFAULT_VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
DEFAULT_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"

# Aspect Ratios and Megapixels calculation
ORIGINAL_RATIO_LABEL = "原圖比例 (自動對齊)"

ASPECT_RATIOS: Dict[str, Tuple[int, int]] = {
    "16:9 (橫向風景)": (16, 9),
    "9:16 (直向手機)": (9, 16),
    "1:1 (正方形)": (1, 1),
    "4:3 (標準比例)": (4, 3),
    "3:4 (直向比例)": (3, 4),
    "21:9 (超寬電影)": (21, 9),
}

# Image-based generation choices (I2V, R2V): defaults to auto-aligning original image ratio
I2V_ASPECT_RATIOS: list[str] = [
    ORIGINAL_RATIO_LABEL,
    "16:9 (橫向風景)",
    "9:16 (直向手機)",
    "1:1 (正方形)",
    "4:3 (標準比例)",
    "3:4 (直向比例)",
    "21:9 (超寬電影)",
]

# Text-based generation choices (T2V): standard fixed ratios
T2V_ASPECT_RATIOS: list[str] = [
    "16:9 (橫向風景)",
    "9:16 (直向手機)",
    "1:1 (正方形)",
    "4:3 (標準比例)",
    "3:4 (直向比例)",
    "21:9 (超寬電影)",
]

MEGAPIXEL_CHOICES = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
DEFAULT_MEGAPIXELS = 1.0
DEFAULT_MULTIPLE = 32

# Quality Levels mapping (1~10 corresponding to 0.2MP~2.0MP)
QUALITY_LEVEL_TO_MP: Dict[int, float] = {
    1: 0.2,
    2: 0.4,
    3: 0.6,
    4: 0.8,
    5: 1.0,
    6: 1.2,
    7: 1.4,
    8: 1.6,
    9: 1.8,
    10: 2.0,
}

QUALITY_CHOICES = [
    "1 (0.2 MP - 極速預覽)",
    "2 (0.4 MP - 快速生成)",
    "3 (0.6 MP - 流暢體驗)",
    "4 (0.8 MP - 均衡畫質)",
    "5 (1.0 MP - 標準推薦)",
    "6 (1.2 MP - 高畫質)",
    "7 (1.4 MP - 優質畫質)",
    "8 (1.6 MP - 超高畫質)",
    "9 (1.8 MP - 旗艦細緻)",
    "10 (2.0 MP - 極致高解析)",
]
DEFAULT_QUALITY_LEVEL = "1 (0.2 MP - 極速預覽)"


def normalize_quality_choice(val: Any) -> str:
    """
    Normalizes any quality value (string descriptor, legacy preset string,
    megapixels float, or level int) to a guaranteed valid element of QUALITY_CHOICES.
    """
    if not val:
        return DEFAULT_QUALITY_LEVEL

    # 1. Exact match with current choices
    if isinstance(val, str) and val in QUALITY_CHOICES:
        return val

    # 2. Integer level matching (1..10)
    if isinstance(val, int) and 1 <= val <= len(QUALITY_CHOICES):
        return QUALITY_CHOICES[val - 1]

    val_str = str(val).strip()

    # 3. Plain integer string e.g. "1" .. "10"
    if val_str.isdigit():
        num = int(val_str)
        if 1 <= num <= len(QUALITY_CHOICES):
            return QUALITY_CHOICES[num - 1]

    # 4. Extract MP float from string or number and find closest choice.
    #    NB: quality_level_to_mp() silently falls back to 1.0 MP for garbage, which used to
    #    make the DEFAULT fallback below unreachable for strings (garbage mapped to the 1.0 MP
    #    tier regardless of DEFAULT_QUALITY_LEVEL). Parse strictly here instead so unknown
    #    values actually land on the configured default.
    mp = _parse_mp_strict(val)
    if mp is not None:
        return min(QUALITY_CHOICES, key=lambda c: abs(quality_level_to_mp(c) - mp))

    return DEFAULT_QUALITY_LEVEL


def _parse_mp_strict(val: Any) -> Optional[float]:
    """MP interpretation that returns None (not a silent 1.0) for unrecognizable values."""
    if isinstance(val, float):
        return val
    if isinstance(val, str):
        # Explicit MP mention, e.g. "1.0 MP" or legacy "3 (1.0 MP - 標準)"
        m = re.search(r"(\d+(?:\.\d+)?)\s*MP", val, re.IGNORECASE)
        if m:
            return float(m.group(1))
        cleaned = val.strip()
        try:
            return float(cleaned)  # bare MP number e.g. "1.5"
        except ValueError:
            return None
    return None


def normalize_aspect_ratio(val: Any, default_ar: str = "16:9 (橫向風景)", allow_original: bool = True) -> str:
    """
    Normalizes any aspect ratio string (exact key, prefix, legacy format, or dimension)
    to a guaranteed valid element of ASPECT_RATIOS.keys() or ORIGINAL_RATIO_LABEL.
    """
    if not val:
        return default_ar

    val_str = str(val).strip()

    # 0. Check for Original Ratio / Auto-alignment label
    if allow_original and (val_str == ORIGINAL_RATIO_LABEL or "原圖" in val_str or "自動" in val_str):
        return ORIGINAL_RATIO_LABEL

    # 1. Exact match with standard ratios
    if val_str in ASPECT_RATIOS:
        return val_str

    # 2. Check if starts with rw:rh e.g. "16:9", "9:16", "1:1", etc.
    for k, (rw, rh) in ASPECT_RATIOS.items():
        if val_str.startswith(f"{rw}:{rh}"):
            return k

    # 3. Legacy resolution presets (e.g., "16:9 橫向風景 (1344 x 768)")
    for k in ASPECT_RATIOS:
        prefix = k.split()[0]  # e.g. "16:9"
        if prefix in val_str:
            return k

    return default_ar


def normalize_sampler(val: Any) -> str:
    """Guarantees returned sampler is in SAMPLER_CHOICES."""
    if val and isinstance(val, str) and val in SAMPLER_CHOICES:
        return val
    return SAMPLER_CHOICES[0]


def normalize_scheduler(val: Any) -> str:
    """Guarantees returned scheduler is in SCHEDULER_CHOICES."""
    if val and isinstance(val, str) and val in SCHEDULER_CHOICES:
        return val
    return SCHEDULER_CHOICES[0]


def set_comfy_server_url(url: str):
    """Dynamically updates the ComfyUI server URL and syncs imported references.

    Attribute-name scan (not a hardcoded module list): after the core/ + task_manager/
    package splits, `from config import COMFY_SERVER_URL` copies live in
    core.comfy_client, components.comfy_toolbar and every task_manager submodule —
    a fixed name list silently went stale and e2e traffic hit the default 8188.
    Scanning loaded modules keeps working no matter where files move next."""
    global COMFY_SERVER_URL, COMFY_WS_URL
    COMFY_SERVER_URL = url
    COMFY_WS_URL = url.replace("http://", "ws://").replace("https://", "wss://")
    import sys
    for mod in list(sys.modules.values()):
        if mod is None or getattr(mod, "__name__", "") == __name__:
            continue
        mod_vars = getattr(mod, "__dict__", None)
        if not isinstance(mod_vars, dict):
            continue
        if "COMFY_SERVER_URL" in mod_vars:
            mod_vars["COMFY_SERVER_URL"] = url
        if "COMFY_WS_URL" in mod_vars:
            mod_vars["COMFY_WS_URL"] = COMFY_WS_URL



def quality_level_to_mp(level_val: Any) -> float:
    """Converts a quality level (1~10 or string descriptor) or float to megapixels float."""
    # If float passed directly (e.g. 1.0, 0.5, 1.25)
    if isinstance(level_val, float):
        return level_val

    # If int 1..10 passed
    if isinstance(level_val, int) and level_val in QUALITY_LEVEL_TO_MP:
        return QUALITY_LEVEL_TO_MP[level_val]

    if isinstance(level_val, str):
        # Check if contains MP e.g. "1.0 MP", "5 (1.0 MP - 標準推薦)"
        m = re.search(r"(\d+(?:\.\d+)?)\s*MP", level_val, re.IGNORECASE)
        if m:
            return float(m.group(1))
        # Plain digit string e.g. "1".."10"
        cleaned = level_val.strip()
        if cleaned.isdigit() and int(cleaned) in QUALITY_LEVEL_TO_MP:
            return QUALITY_LEVEL_TO_MP[int(cleaned)]
        try:
            return float(cleaned)
        except Exception:
            pass

    return 1.0


def calculate_dimensions_adaptive_ratio(
    orig_w: int,
    orig_h: int,
    target_mp: Any = 1.0,
    multiple: int = DEFAULT_MULTIPLE,
) -> Tuple[int, int]:
    """
    Given original image width and height, calculates legal video output dimensions (w, h)
    whose aspect ratio matches orig_w / orig_h with minimal distortion (typically < 0.3% error),
    while strictly aligning w and h to multiples of `multiple` (default 32) and targeting `target_mp`.
    """
    if orig_w <= 0 or orig_h <= 0:
        return calculate_dimensions("16:9 (橫向風景)", target_mp, multiple)

    r = float(orig_w) / float(orig_h)
    mp_float = quality_level_to_mp(target_mp)
    target_area = float(mp_float) * 1_000_000.0

    raw_h = math.sqrt(target_area / r)
    raw_w = raw_h * r

    base_w_m = round(raw_w / multiple)
    base_h_m = round(raw_h / multiple)

    best_w, best_h = None, None
    best_score = float("inf")

    # Grid search across neighboring multiples within +/- 3 steps
    for dw in range(-3, 4):
        w = int((base_w_m + dw) * multiple)
        if w < multiple:
            continue
        for dh in range(-3, 4):
            h = int((base_h_m + dh) * multiple)
            if h < multiple:
                continue
            area = float(w * h)
            area_err = abs(area - target_area) / target_area
            # Allow up to 18% variance around the target area to find best aspect match
            if area_err > 0.18:
                continue
            ratio_err = abs((float(w) / float(h)) - r) / r
            score = ratio_err * 100.0 + area_err
            if score < best_score:
                best_score = score
                best_w, best_h = w, h

    if best_w is None:
        best_w = max(multiple, int(round(raw_w / multiple) * multiple))
        best_h = max(multiple, int(round(raw_h / multiple) * multiple))

    return best_w, best_h


def calculate_dimensions_from_image(
    image_input: Any,
    quality_level: Any = 1.0,
    multiple: int = DEFAULT_MULTIPLE,
) -> Tuple[int, int]:
    """
    Extracts width and height from an image (filepath, PIL Image, or tuple (w, h)),
    and returns mathematically optimal, distortion-free output video dimensions.
    """
    if not image_input:
        return calculate_dimensions("16:9 (橫向風景)", quality_level, multiple)

    orig_w, orig_h = None, None
    if isinstance(image_input, (tuple, list)) and len(image_input) >= 2:
        orig_w, orig_h = int(image_input[0]), int(image_input[1])
    elif hasattr(image_input, "size"):  # PIL Image
        orig_w, orig_h = image_input.size
    elif isinstance(image_input, str) and os.path.exists(image_input):
        try:
            with Image.open(image_input) as im:
                orig_w, orig_h = im.size
        except Exception:
            pass

    if orig_w and orig_h and orig_w > 0 and orig_h > 0:
        return calculate_dimensions_adaptive_ratio(orig_w, orig_h, quality_level, multiple)

    return calculate_dimensions("16:9 (橫向風景)", quality_level, multiple)


def calculate_dimensions(
    aspect_ratio: str,
    megapixels: Any = 1.0,
    multiple: int = DEFAULT_MULTIPLE,
    image_input: Any = None,
) -> Tuple[int, int]:
    """
    Calculates width and height from aspect ratio string and megapixels (or quality level 1~10),
    snapping dimensions to the nearest multiple (typically 32 for MiniMax-H3).
    If aspect_ratio is '原圖比例 (自動對齊)', extracts image_input dimensions and computes adaptive match.
    """
    if aspect_ratio == ORIGINAL_RATIO_LABEL or "原圖" in str(aspect_ratio) or "自動" in str(aspect_ratio):
        if image_input is not None:
            return calculate_dimensions_from_image(image_input, megapixels, multiple)
        # If no image provided yet, default to standard 16:9 canvas
        aspect_ratio = "16:9 (橫向風景)"

    ratio_val = None
    for k, (rw, rh) in ASPECT_RATIOS.items():
        if aspect_ratio == k or aspect_ratio.startswith(f"{rw}:{rh}"):
            ratio_val = rw / rh
            break

    if ratio_val is None:
        try:
            clean_ar = aspect_ratio.split()[0]
            parts = clean_ar.split(":")
            ratio_val = float(parts[0]) / float(parts[1])
        except Exception:
            ratio_val = 16.0 / 9.0

    mp_float = quality_level_to_mp(megapixels)
    total_pixels = float(mp_float) * 1_000_000
    raw_h = math.sqrt(total_pixels / ratio_val)
    raw_w = raw_h * ratio_val

    w = max(multiple, int(round(raw_w / multiple) * multiple))
    h = max(multiple, int(round(raw_h / multiple) * multiple))
    return w, h


def find_nearest_aspect_ratio(orig_w: int, orig_h: int) -> str:
    """Given raw image dimensions, finds the closest standard aspect ratio preset."""
    if orig_h <= 0:
        return "16:9 (橫向風景)"
    target_ratio = orig_w / orig_h
    best_key = "16:9 (橫向風景)"
    min_diff = float("inf")
    for key, (rw, rh) in ASPECT_RATIOS.items():
        std_ratio = rw / rh
        diff = abs(target_ratio - std_ratio)
        if diff < min_diff:
            min_diff = diff
            best_key = key
    return best_key


# Legacy Resolution Presets for backward compatibility
RESOLUTION_PRESETS = {
    "16:9 橫向風景 (1344 x 768)": (1344, 768),
    "9:16 直向手機 (768 x 1344)": (768, 1344),
    "16:9 中解析 (1152 x 640)": (1152, 640),
    "9:16 中解析 (640 x 1152)": (640, 1152),
    "1:1 正方形 (1024 x 1024)": (1024, 1024),
    "4:3 標準比例 (1024 x 768)": (1024, 768),
    "3:4 直向比例 (768 x 1024)": (768, 1024),
    "自訂尺寸 (使用下方滑桿)": (None, None),
}

# Sampler & Scheduler Options
SAMPLER_CHOICES = ["res_multistep", "euler", "heun", "dpmpp_2m"]
SCHEDULER_CHOICES = ["simple", "beta", "normal"]

# Output directory for locally saved generated videos
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
try:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
except Exception:
    pass


def get_lan_ip() -> str:
    """Get the primary local area network IPv4 address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def align_frame_count(frame_count: int) -> int:
    """MiniMax H3 model snaps frame length to 17k + 5 at 24 fps."""
    n = max(5, frame_count)
    while n % 17 != 5:
        n += 1
    return n


def duration_to_frames(duration_seconds: float, fps: int = 24) -> int:
    """Convert duration in seconds to aligned frame count."""
    raw_frames = round(duration_seconds * fps)
    return align_frame_count(raw_frames)



# Video Resolution Upscaler Constants & Model Discovery
DEFAULT_UPSCALE_MODELS_DIR = os.environ.get(
    "UPSCALE_MODELS_DIR", r"F:\Comfy_models\upscale_models"
)


def get_upscale_models(models_dir: Optional[str] = None) -> List[str]:
    """
    Scans the upscale models directory and returns a sorted list of model filenames.
    Defaults to F:\\Comfy_models\\upscale_models.
    """
    path = models_dir or DEFAULT_UPSCALE_MODELS_DIR
    valid_exts = (".safetensors", ".pth", ".pt", ".bin", ".onnx")
    models = []
    if os.path.exists(path) and os.path.isdir(path):
        try:
            for f in os.listdir(path):
                if any(f.endswith(ext) for ext in valid_exts):
                    models.append(f)
        except Exception:
            pass
    if not models:
        # Fallback presets if directory is inaccessible or empty
        models = [
            "4x-AnimeSharp.safetensors",
            "4x-UltraSharp.safetensors",
            "RealESRGAN_x4plus.safetensors",
        ]
    return sorted(models)

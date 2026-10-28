"""
Configuration and helper functions for MiniMax-H3 ComfyUI Gradio WebUI.
"""
import socket
import os
import math
import re
from typing import Tuple, Dict, Any, Union

# Server connection
COMFY_SERVER_URL = os.environ.get("COMFY_SERVER_URL", "http://127.0.0.1:8188")
COMFY_WS_URL = COMFY_SERVER_URL.replace("http://", "ws://").replace("https://", "wss://")

# Gradio WebUI Host and Port
WEBUI_HOST = os.environ.get("WEBUI_HOST", "0.0.0.0")
WEBUI_PORT = int(os.environ.get("WEBUI_PORT", "7860"))

# Default Models (MiniMax-H3)
DEFAULT_UNET = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
DEFAULT_CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
DEFAULT_VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
DEFAULT_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"

# Aspect Ratios and Megapixels calculation
ASPECT_RATIOS: Dict[str, Tuple[int, int]] = {
    "16:9 (橫向風景)": (16, 9),
    "9:16 (直向手機)": (9, 16),
    "1:1 (正方形)": (1, 1),
    "4:3 (標準比例)": (4, 3),
    "3:4 (直向比例)": (3, 4),
    "21:9 (超寬電影)": (21, 9),
}

MEGAPIXEL_CHOICES = [0.5, 0.75, 1.0, 1.25, 1.5]
DEFAULT_MEGAPIXELS = 1.0
DEFAULT_MULTIPLE = 32

# Quality Levels mapping (1~5 corresponding to Megapixels)
QUALITY_LEVEL_TO_MP: Dict[int, float] = {
    1: 0.5,
    2: 0.75,
    3: 1.0,
    4: 1.25,
    5: 1.5,
}

QUALITY_CHOICES = [
    "1 (0.5 MP - 極速)",
    "2 (0.75 MP - 流暢)",
    "3 (1.0 MP - 標準推薦)",
    "4 (1.25 MP - 高畫質)",
    "5 (1.5 MP - 超高畫質)",
]
DEFAULT_QUALITY_LEVEL = "3 (1.0 MP - 標準推薦)"


def quality_level_to_mp(level_val: Any) -> float:
    """Converts a quality level (1~5 or string descriptor) or float to megapixels float."""
    # If float passed directly (e.g. 1.0, 0.5, 1.25)
    if isinstance(level_val, float):
        return level_val

    # If int 1..5 passed
    if isinstance(level_val, int) and level_val in QUALITY_LEVEL_TO_MP:
        return QUALITY_LEVEL_TO_MP[level_val]

    if isinstance(level_val, str):
        # Check if contains MP e.g. "1.0 MP", "3 (1.0 MP - 標準推薦)"
        m = re.search(r"(\d+(?:\.\d+)?)\s*MP", level_val, re.IGNORECASE)
        if m:
            return float(m.group(1))
        # Plain digit string e.g. "1", "2", "3", "4", "5"
        cleaned = level_val.strip()
        if cleaned.isdigit() and int(cleaned) in QUALITY_LEVEL_TO_MP:
            return QUALITY_LEVEL_TO_MP[int(cleaned)]
        try:
            return float(cleaned)
        except Exception:
            pass

    return 1.0


def calculate_dimensions(
    aspect_ratio: str,
    megapixels: Any = 1.0,
    multiple: int = DEFAULT_MULTIPLE,
) -> Tuple[int, int]:
    """
    Calculates width and height from aspect ratio string and megapixels (or quality level 1~5),
    snapping dimensions to the nearest multiple (typically 16 for diffusion models).
    """
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

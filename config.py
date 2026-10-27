"""
Configuration and helper functions for MiniMax-H3 ComfyUI Gradio WebUI.
"""
import socket
import os

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

# Resolution Presets (Name -> (width, height))
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

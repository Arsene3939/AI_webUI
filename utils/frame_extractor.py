"""
Video last-frame extraction utility.
Extracts the final video frame as a PNG still for user download.
Primary path: PyAV (in-process decode, same library family as ComfyUI's video IO).
Fallback path: system ffmpeg via subprocess (-sseof rewind + -update 1 keeps overwriting
the output with each decoded frame, so what remains on disk is the true last frame).
"""
import os
import shutil
import subprocess
from typing import Optional

from config import OUTPUT_DIR
from utils.logger import get_logger

logger = get_logger("FrameExtractor")


def _frames_dir() -> str:
    """Returns (creating if needed) the derived-frame output directory inside allowed paths."""
    path = os.path.join(OUTPUT_DIR, "frames")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def _output_path(video_path: str) -> str:
    stem = os.path.splitext(os.path.basename(video_path))[0]
    return os.path.join(_frames_dir(), f"{stem}_lastframe.png")


def _extract_with_pyav(video_path: str, out_path: str) -> bool:
    """Decodes the whole video in memory-light fashion and keeps the last video frame."""
    import av

    with av.open(video_path) as container:
        stream = next((s for s in container.streams if s.type == "video"), None)
        if stream is None:
            logger.warning("[FrameExtractor] No video stream in '%s'", os.path.basename(video_path))
            return False
        last_frame = None
        for frame in container.decode(stream):
            last_frame = frame
        if last_frame is None:
            return False
        last_frame.to_image().save(out_path, format="PNG")
    return True


def _extract_with_ffmpeg(video_path: str, out_path: str) -> bool:
    """ffmpeg fallback: rewind near the end, then overwrite the same PNG per decoded frame."""
    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        return False
    cmd = [
        ffmpeg_exe, "-y", "-loglevel", "error",
        "-sseof", "-10",
        "-i", video_path,
        "-update", "1",
        out_path,
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)
        if result.returncode == 0 and os.path.exists(out_path):
            return True
        logger.warning("[FrameExtractor] ffmpeg fallback failed: %s",
                       (result.stderr or b"").decode("utf-8", errors="replace")[:200])
    except Exception as e:
        logger.warning("[FrameExtractor] ffmpeg fallback exception: %s", e)
    return False


def extract_last_frame(video_path: Optional[str]) -> Optional[str]:
    """
    Extracts the last frame of the given video file into outputs/frames/<stem>_lastframe.png.
    Returns the PNG path on success, or None when the video is missing/undecodable.
    """
    if not video_path or not isinstance(video_path, str) or not os.path.exists(video_path):
        logger.warning("[FrameExtractor] Video file not found: %s", video_path)
        return None

    out_path = _output_path(video_path)
    try:
        if _extract_with_pyav(video_path, out_path):
            logger.info("[FrameExtractor] Last frame extracted via PyAV -> %s", out_path)
            return out_path
    except Exception as e:
        logger.warning("[FrameExtractor] PyAV extraction failed (%s), trying ffmpeg fallback...", e)

    try:
        if _extract_with_ffmpeg(video_path, out_path):
            logger.info("[FrameExtractor] Last frame extracted via ffmpeg -> %s", out_path)
            return out_path
    except Exception as e:
        logger.warning("[FrameExtractor] ffmpeg extraction failed: %s", e)

    return None

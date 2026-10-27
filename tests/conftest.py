"""
Pytest configuration and shared fixtures for MiniMax-H3 WebUI tests.
"""
import os
import sys
import tempfile
import shutil
import pytest

# Ensure project root is at the head of sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config
import task_manager


@pytest.fixture(autouse=True)
def isolated_test_env(tmp_path, monkeypatch):
    """
    Isolates task manager outputs and history to a temporary directory
    for each test run, preventing pollution of real outputs.
    """
    temp_output = tmp_path / "test_outputs"
    temp_output.mkdir(parents=True, exist_ok=True)
    temp_inputs = temp_output / "inputs"
    temp_inputs.mkdir(parents=True, exist_ok=True)
    temp_history = temp_output / "task_history.json"

    # Patch module paths
    monkeypatch.setattr(config, "OUTPUT_DIR", str(temp_output))
    monkeypatch.setattr(task_manager, "OUTPUT_DIR", str(temp_output))
    monkeypatch.setattr(task_manager, "INPUTS_ARCHIVE_DIR", str(temp_inputs))
    monkeypatch.setattr(task_manager, "HISTORY_FILE", str(temp_history))

    # Reset task manager in-memory tasks
    with task_manager.task_manager._lock:
        task_manager.task_manager._tasks.clear()

    yield {
        "output_dir": str(temp_output),
        "inputs_dir": str(temp_inputs),
        "history_file": str(temp_history),
    }

    # Clean up after test
    with task_manager.task_manager._lock:
        task_manager.task_manager._tasks.clear()


@pytest.fixture
def dummy_image_file(tmp_path):
    """Generates a dummy 1x1 PNG file for media upload testing."""
    # 1x1 transparent PNG bytes
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img_path = tmp_path / "test_image.png"
    img_path.write_bytes(png_bytes)
    return str(img_path)


@pytest.fixture
def dummy_video_file(tmp_path):
    """Generates a dummy .mp4 file."""
    video_path = tmp_path / "test_video.mp4"
    video_path.write_bytes(b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2mp41")
    return str(video_path)


@pytest.fixture
def dummy_audio_file(tmp_path):
    """Generates a dummy .wav file."""
    audio_path = tmp_path / "test_audio.wav"
    # Basic RIFF WAVE header
    audio_path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    return str(audio_path)

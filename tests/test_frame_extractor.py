"""
Unit tests for the video last-frame extractor and its MiniMax player-card UI wiring.
Spec task 3: MiniMax pages offer a 'download last frame' flow backed by server-side extraction.
"""
import os
import shutil
import subprocess
import pytest
import gradio as gr
from PIL import Image

import frame_extractor
from frame_extractor import extract_last_frame
from components.media_player import VideoPlayerCardComponent

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg required to synthesize test videos",
)


def make_two_tone_video(tmp_path) -> str:
    """Synthesizes a 2-second video: first half pure RED, second half pure BLUE."""
    out_path = str(tmp_path / "twotone_input.mp4")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=red:s=64x64:d=1:r=10",
        "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=1:r=10",
        "-filter_complex", "[0][1]concat=n=2:v=1:a=0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_path,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)
    assert os.path.exists(out_path)
    return out_path


class TestFrameExtraction:
    def test_extracts_true_last_frame(self, tmp_path):
        """The extracted still must be the tail (BLUE) frame, not the head (RED) frame."""
        video = make_two_tone_video(tmp_path)
        frame_path = extract_last_frame(video)

        assert frame_path is not None, "Extraction returned None"
        assert os.path.exists(frame_path) and frame_path.endswith(".png")
        assert os.path.dirname(frame_path).endswith("frames"), "Frame must live in an outputs/frames dir"

        with Image.open(frame_path) as im:
            r, g, b = im.convert("RGB").getpixel((32, 32))
        assert b > 150 and r < 90, f"Last frame should be BLUE but got RGB=({r},{g},{b})"

    def test_missing_or_empty_input_returns_none(self, tmp_path):
        assert extract_last_frame(None) is None
        assert extract_last_frame("") is None
        assert extract_last_frame(str(tmp_path / "does_not_exist.mp4")) is None

    def test_pyav_failure_falls_back_to_ffmpeg(self, tmp_path, monkeypatch):
        """With the PyAV path broken, the ffmpeg fallback must still produce the BLUE tail frame."""
        video = make_two_tone_video(tmp_path)

        def broken_pyav(video_path, out_path):
            raise RuntimeError("simulated decoder failure")

        monkeypatch.setattr(frame_extractor, "_extract_with_pyav", broken_pyav)
        frame_path = extract_last_frame(video)

        assert frame_path is not None, "ffmpeg fallback failed to produce a frame"
        with Image.open(frame_path) as im:
            r, g, b = im.convert("RGB").getpixel((32, 32))
        assert b > 150 and r < 90, f"Fallback last frame should be BLUE but got RGB=({r},{g},{b})"

    def test_undecodable_file_returns_none(self, tmp_path):
        bogus = tmp_path / "broken.mp4"
        bogus.write_bytes(b"this is definitely not a video")
        assert extract_last_frame(str(bogus)) is None


class TestPlayerCardFrameUI:
    def test_player_card_renders_frame_controls_hidden_by_default(self):
        """MiniMax player cards expose extract button + download button; download starts hidden."""
        with gr.Blocks():
            card = VideoPlayerCardComponent(label="生成影片").render()
            assert card.frame_btn is not None
            assert card.frame_download is not None
            assert card.frame_msg is not None
            assert card.frame_download.visible is False

    def test_reset_frame_updates_clears_stale_offer(self):
        """Starting a new generation must hide a previously prepared frame download."""
        with gr.Blocks():
            card = VideoPlayerCardComponent().render()
            dl_update, msg_update = card.reset_frame_updates()
            assert dl_update.get("visible") is False
            assert msg_update.get("value") == ""

    def test_mini_max_view_registers_frame_events_on_all_tabs(self):
        """MiniMaxView wires last-frame events on each of the three player cards."""
        from views.minimax.view import MiniMaxView
        from core.session_context import SessionContext

        with gr.Blocks():
            session_ctx = SessionContext().render()
            view = MiniMaxView()
            view.render(session_ctx)
            view.register_events(session_ctx)

            for tab in (view.i2v_tab, view.t2v_tab, view.r2v_tab):
                assert tab.player_card.frame_btn is not None
                assert tab.player_card.frame_download is not None

"""
Unit tests for config.py helper functions and preset definitions.
"""
import re
import pytest
from config import (
    align_frame_count,
    duration_to_frames,
    get_lan_ip,
    RESOLUTION_PRESETS,
    SAMPLER_CHOICES,
    SCHEDULER_CHOICES,
    DEFAULT_UNET,
    DEFAULT_CLIP,
    DEFAULT_VIDEO_VAE,
    DEFAULT_AUDIO_VAE,
)


class TestConfigCalculations:
    def test_align_frame_count_exact_matches(self):
        """MiniMax-H3 requires frame count to satisfy n % 17 == 5, n >= 5."""
        assert align_frame_count(5) == 5
        assert align_frame_count(22) == 22
        assert align_frame_count(39) == 39
        assert align_frame_count(56) == 56
        assert align_frame_count(73) == 73

    def test_align_frame_count_snapping(self):
        """Values between 17k+5 should snap up to the next valid frame count."""
        assert align_frame_count(1) == 5
        assert align_frame_count(4) == 5
        assert align_frame_count(6) == 22
        assert align_frame_count(20) == 22
        assert align_frame_count(23) == 39
        assert align_frame_count(40) == 56

    def test_align_frame_count_invariants(self):
        """Property-based check: result % 17 must be 5, and result >= input."""
        for val in range(0, 150):
            res = align_frame_count(val)
            assert res % 17 == 5
            assert res >= max(5, val)

    def test_duration_to_frames(self):
        """Tests converting duration in seconds to aligned frames."""
        # 2.0s at 24fps -> 48 raw frames -> snaps to 56
        assert duration_to_frames(2.0, fps=24) == 56
        # 3.0s at 24fps -> 72 raw frames -> snaps to 73
        assert duration_to_frames(3.0, fps=24) == 73
        # 1.0s at 24fps -> 24 raw frames -> snaps to 39
        assert duration_to_frames(1.0, fps=24) == 39


class TestConfigPresets:
    def test_resolution_presets_structure(self):
        """Ensures all resolution presets have (w, h) tuples."""
        assert len(RESOLUTION_PRESETS) >= 5
        for name, dims in RESOLUTION_PRESETS.items():
            assert isinstance(dims, tuple)
            assert len(dims) == 2
            w, h = dims
            if "自訂" in name:
                assert w is None and h is None
            else:
                assert isinstance(w, int) and w > 0
                assert isinstance(h, int) and h > 0
                # ComfyUI dimensions must be multiples of 8 or 16
                assert w % 8 == 0
                assert h % 8 == 0

    def test_sampler_and_scheduler_choices(self):
        """Checks valid sampler and scheduler definitions."""
        assert "res_multistep" in SAMPLER_CHOICES
        assert "euler" in SAMPLER_CHOICES
        assert "simple" in SCHEDULER_CHOICES
        assert "beta" in SCHEDULER_CHOICES

    def test_model_defaults(self):
        """Ensures default model filenames are non-empty strings."""
        assert DEFAULT_UNET.endswith(".safetensors")
        assert DEFAULT_CLIP.endswith(".safetensors")
        assert DEFAULT_VIDEO_VAE.endswith(".safetensors")
        assert DEFAULT_AUDIO_VAE.endswith(".safetensors")

    def test_get_lan_ip_format(self):
        """Checks LAN IP detection returns a valid IPv4 address."""
        ip = get_lan_ip()
        assert isinstance(ip, str)
        # Verify valid IPv4 regex
        ipv4_regex = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
        assert re.match(ipv4_regex, ip) is not None

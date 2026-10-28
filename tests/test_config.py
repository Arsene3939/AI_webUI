"""
Unit tests for config.py helper functions and preset definitions.
"""
import re
import pytest
from config import (
    align_frame_count,
    duration_to_frames,
    get_lan_ip,
    calculate_dimensions,
    find_nearest_aspect_ratio,
    quality_level_to_mp,
    QUALITY_CHOICES,
    QUALITY_LEVEL_TO_MP,
    DEFAULT_QUALITY_LEVEL,
    ASPECT_RATIOS,
    MEGAPIXEL_CHOICES,
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


class TestResolutionAndAspectRatio:
    def test_aspect_ratios_and_megapixels_definitions(self):
        """Ensures aspect ratios and megapixels choices are valid."""
        assert "16:9 (橫向風景)" in ASPECT_RATIOS
        assert "9:16 (直向手機)" in ASPECT_RATIOS
        assert "1:1 (正方形)" in ASPECT_RATIOS
        assert 1.0 in MEGAPIXEL_CHOICES
        assert len(QUALITY_CHOICES) == 10
        assert len(QUALITY_LEVEL_TO_MP) == 10

    def test_quality_level_to_mp(self):
        """Tests converting quality levels 1~10 to corresponding megapixels float."""
        assert quality_level_to_mp(1) == 0.2
        assert quality_level_to_mp(5) == 1.0
        assert quality_level_to_mp(10) == 2.0
        # String representations
        assert quality_level_to_mp("1 (0.2 MP - 極速預覽)") == 0.2
        assert quality_level_to_mp("5 (1.0 MP - 標準推薦)") == 1.0
        assert quality_level_to_mp("10 (2.0 MP - 極致高解析)") == 2.0
        assert quality_level_to_mp("1.0 MP") == 1.0

    def test_calculate_dimensions_standard_ratios(self):
        """Tests standard 1.0 MP resolution calculations snapped to multiple 32."""
        # 16:9 at Level 5 (1.0 MP) -> 1344 x 736 (multiples of 32)
        w, h = calculate_dimensions("16:9 (橫向風景)", megapixels=5)
        assert (w, h) == (1344, 736)
        assert w % 32 == 0 and h % 32 == 0

        # 9:16 at Level 5 (1.0 MP) -> 736 x 1344 (multiples of 32)
        w, h = calculate_dimensions("9:16 (直向手機)", megapixels="5 (1.0 MP - 標準推薦)")
        assert (w, h) == (736, 1344)
        assert w % 32 == 0 and h % 32 == 0

        # 1:1 at Level 5 (1.0 MP) -> 992 x 992 (multiples of 32)
        w, h = calculate_dimensions("1:1 (正方形)", megapixels=1.0)
        assert (w, h) == (992, 992)
        assert w % 32 == 0 and h % 32 == 0

    def test_calculate_dimensions_multiples_invariant(self):
        """Dimensions must always strictly be divisible by the multiple requested."""
        for ar in ASPECT_RATIOS.keys():
            for mp in MEGAPIXEL_CHOICES:
                for mult in [16, 32, 64]:
                    w, h = calculate_dimensions(ar, megapixels=mp, multiple=mult)
                    assert w % mult == 0, f"Width {w} not divisible by {mult}"
                    assert h % mult == 0, f"Height {h} not divisible by {mult}"
                    assert w > 0 and h > 0

    def test_find_nearest_aspect_ratio(self):
        """Tests matching arbitrary input image dimensions to closest aspect ratio preset."""
        assert find_nearest_aspect_ratio(1920, 1080) == "16:9 (橫向風景)"
        assert find_nearest_aspect_ratio(3840, 2160) == "16:9 (橫向風景)"
        assert find_nearest_aspect_ratio(1080, 1920) == "9:16 (直向手機)"
        assert find_nearest_aspect_ratio(1000, 1000) == "1:1 (正方形)"
        assert find_nearest_aspect_ratio(1024, 768) == "4:3 (標準比例)"
        assert find_nearest_aspect_ratio(768, 1024) == "3:4 (直向比例)"
        assert find_nearest_aspect_ratio(2560, 1080) == "21:9 (超寬電影)"
        # Edge cases
        assert find_nearest_aspect_ratio(1920, 0) == "16:9 (橫向風景)"
        assert find_nearest_aspect_ratio(0, 1080) == "9:16 (直向手機)"

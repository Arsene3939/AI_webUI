"""
Tests for admin-only model selection (Spec 2026-11-02):
folder scanning (list_comfy_models), enforcement gate (resolve_model_names),
and the admin model-select UI markers in the shared params card.
"""
import os
import gradio as gr
import pytest

import config
from config import (
    list_comfy_models,
    resolve_model_names,
    DEFAULT_UNET,
    DEFAULT_CLIP,
    DEFAULT_VIDEO_VAE,
    DEFAULT_AUDIO_VAE,
)
from components.video_params import VideoParamsComponent


@pytest.fixture()
def fake_models_root(tmp_path, monkeypatch):
    """Fake F:/Comfy_models tree mirroring extra_model_paths.yaml layout."""
    root = tmp_path / "models"

    def mk(rel):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")

    mk("diffusion_models/minimax_unet.safetensors")
    mk("diffusion_models/sub/seedvr2.safetensors")     # subfolder -> relative-name format
    mk("unet/minimax_unet.safetensors")                # duplicate across roots
    mk("unet/old_weights.pt")
    mk("text_encoders/qwen3vl.safetensors")
    mk("clip/legacy_clip.safetensors")
    mk("vae/video_vae.safetensors")
    mk("vae/not_a_model.txt")                          # must be filtered out
    monkeypatch.setattr(config, "COMFY_MODELS_DIR", str(root))
    return root


class TestModelScanning:
    def test_multi_root_scan_with_subfolders_and_dedupe(self, fake_models_root):
        models = list_comfy_models("unet")
        assert "minimax_unet.safetensors" in models
        assert "sub/seedvr2.safetensors" in models      # ComfyUI relative format
        assert "old_weights.pt" in models
        assert models.count("minimax_unet.safetensors") == 1  # deduped across roots
        assert models == sorted(models)

    def test_preferred_model_sorted_first(self, fake_models_root):
        models = list_comfy_models("unet", preferred="sub/seedvr2.safetensors")
        assert models[0] == "sub/seedvr2.safetensors"

    def test_clip_and_vae_roots(self, fake_models_root):
        clips = list_comfy_models("clip")
        assert "qwen3vl.safetensors" in clips and "legacy_clip.safetensors" in clips
        vaes = list_comfy_models("vae")
        assert vaes == ["video_vae.safetensors"]  # .txt filtered

    def test_missing_folder_returns_empty(self, monkeypatch):
        monkeypatch.setattr(config, "COMFY_MODELS_DIR", r"Z:\does\not\exist")
        assert list_comfy_models("unet") == []


class TestModelAccessEnforcement:
    def test_non_admin_always_gets_defaults(self, fake_models_root):
        # even valid filenames are ignored for non-admins -> hardcoded defaults
        got = resolve_model_names("sub/seedvr2.safetensors", "qwen3vl.safetensors",
                                  "video_vae.safetensors", "video_vae.safetensors",
                                  is_admin=False)
        assert got == {"unet": DEFAULT_UNET, "clip": DEFAULT_CLIP,
                       "video_vae": DEFAULT_VIDEO_VAE, "audio_vae": DEFAULT_AUDIO_VAE}

    def test_admin_valid_choice_passes_through(self, fake_models_root):
        got = resolve_model_names("sub/seedvr2.safetensors", "qwen3vl.safetensors",
                                  "video_vae.safetensors", "video_vae.safetensors",
                                  is_admin=True)
        assert got == {"unet": "sub/seedvr2.safetensors", "clip": "qwen3vl.safetensors",
                       "video_vae": "video_vae.safetensors", "audio_vae": "video_vae.safetensors"}

    def test_admin_invalid_or_injected_value_rejected(self, fake_models_root):
        got = resolve_model_names("../../etc/passwd", "not_scanned.safetensors",
                                  None, "", is_admin=True)
        assert got == {"unet": DEFAULT_UNET, "clip": DEFAULT_CLIP,
                       "video_vae": DEFAULT_VIDEO_VAE, "audio_vae": DEFAULT_AUDIO_VAE}

    def test_real_comfy_models_dir_finds_current_defaults(self):
        """On this machine the real model roots exist and must contain the pinned defaults."""
        assert DEFAULT_UNET in list_comfy_models("unet", preferred=DEFAULT_UNET)
        assert DEFAULT_CLIP in list_comfy_models("clip", preferred=DEFAULT_CLIP)
        assert DEFAULT_VIDEO_VAE in list_comfy_models("vae", preferred=DEFAULT_VIDEO_VAE)
        assert DEFAULT_AUDIO_VAE in list_comfy_models("vae", preferred=DEFAULT_AUDIO_VAE)


class TestModelSelectorUI:
    def test_params_card_model_widgets_present_and_hidden_at_build(self, fake_models_root):
        with gr.Blocks():
            card = VideoParamsComponent(include_model_selectors=True)
            card.render()
            assert card.model_row is not None
            assert card.model_row.visible is False  # load-time super-user check decides
            for attr, kind in (("model_unet", "unet"), ("model_clip", "clip"),
                               ("model_video_vae", "vae"), ("model_audio_vae", "vae")):
                dd = getattr(card, attr)
                assert isinstance(dd, gr.Dropdown)
                assert kind and dd.value  # build-time default value set
                assert len(dd.choices) >= 1

    def test_default_card_has_no_model_widgets(self):
        with gr.Blocks():
            card = VideoParamsComponent()  # upscaler/strata-style: no selectors
            card.render()
            assert card.model_row is None
            assert card.model_unet is None

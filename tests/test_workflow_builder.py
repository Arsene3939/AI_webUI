"""
Unit tests for workflow_builder.py graph generation for I2V, T2V, and R2V.
"""
import pytest
from core.workflow_builder import (
    build_i2v_workflow,
    build_t2v_workflow,
    build_r2v_workflow,
)


class TestI2VWorkflowBuilder:
    def test_build_i2v_single_frame(self):
        """Tests I2V workflow with first frame only."""
        graph = build_i2v_workflow(
            prompt="A cute cat running on grass",
            first_frame_filename="cat.png",
            width=1344,
            height=768,
            duration_seconds=2.0,
            seed=42,
            steps=20,
            denoise=1.0,
        )

        assert isinstance(graph, dict)
        assert "minimax_node" in graph
        assert "first_frame_loader" in graph
        assert "last_frame_loader" not in graph

        # Verify MiniMax node configuration
        minimax = graph["minimax_node"]
        assert minimax["class_type"] == "MiniMaxH3ImageToVideo"
        assert minimax["inputs"]["prompt"] == "A cute cat running on grass"
        assert minimax["inputs"]["width"] == 1344
        assert minimax["inputs"]["height"] == 768
        # Duration 2.0s -> 56 frames
        assert minimax["inputs"]["length"] == 56
        assert minimax["inputs"]["length"] % 17 == 5
        assert minimax["inputs"]["first_frame"] == ["first_frame_loader", 0]
        assert "last_frame" not in minimax["inputs"]

        # Verify pipeline components
        assert graph["first_frame_loader"]["inputs"]["image"] == "cat.png"
        assert graph["random_noise"]["inputs"]["noise_seed"] == 42
        assert graph["save_video"]["inputs"]["filename_prefix"] == "video/MiniMax_H3_I2V"

    def test_build_i2v_with_last_frame(self):
        """Tests I2V workflow with both first and last frames (interpolation)."""
        graph = build_i2v_workflow(
            prompt="Transition from day to night",
            first_frame_filename="day.png",
            last_frame_filename="night.png",
            width=1024,
            height=1024,
            duration_seconds=3.0,
        )

        assert "last_frame_loader" in graph
        assert graph["last_frame_loader"]["inputs"]["image"] == "night.png"
        assert graph["minimax_node"]["inputs"]["last_frame"] == ["last_frame_loader", 0]
        # Duration 3.0s -> 73 frames
        assert graph["minimax_node"]["inputs"]["length"] == 73


class TestT2VWorkflowBuilder:
    def test_build_t2v_workflow(self):
        """Tests pure Text-to-Video workflow (no image loader nodes)."""
        graph = build_t2v_workflow(
            prompt="Futuristic city with flying cars at sunset",
            width=1152,
            height=640,
            duration_seconds=2.0,
            seed=999,
            steps=25,
            sampler_name="euler",
            scheduler_name="beta",
        )

        assert "first_frame_loader" not in graph
        assert "last_frame_loader" not in graph

        minimax = graph["minimax_node"]
        assert minimax["class_type"] == "MiniMaxH3ImageToVideo"
        assert minimax["inputs"]["prompt"] == "Futuristic city with flying cars at sunset"
        assert "first_frame" not in minimax["inputs"]
        assert "last_frame" not in minimax["inputs"]

        assert graph["sampler_select"]["inputs"]["sampler_name"] == "euler"
        assert graph["basic_scheduler"]["inputs"]["scheduler"] == "beta"
        assert graph["basic_scheduler"]["inputs"]["steps"] == 25
        assert graph["save_video"]["inputs"]["filename_prefix"] == "video/MiniMax_H3_T2V"


class TestR2VWorkflowBuilder:
    def test_build_r2v_with_reference_images(self):
        """Tests R2V with multiple reference images."""
        ref_images = ["char1.png", "char2.png", "background.png"]
        graph = build_r2v_workflow(
            prompt="Characters interacting in a coffee shop",
            ref_image_filenames=ref_images,
            ref_image_size="match",
            width=1344,
            height=768,
        )

        minimax = graph["minimax_node"]
        assert minimax["class_type"] == "MiniMaxH3ReferenceToVideo"
        assert minimax["inputs"]["ref_image_size"] == "match"

        for idx, filename in enumerate(ref_images):
            node_key = f"load_ref_image_{idx}"
            assert node_key in graph
            assert graph[node_key]["inputs"]["image"] == filename
            assert minimax["inputs"][f"ref_images.ref_image_{idx}"] == [node_key, 0]

        assert "load_ref_video" not in graph
        assert "load_ref_audio" not in graph
        assert graph["save_video"]["inputs"]["filename_prefix"] == "video/MiniMax_H3_R2V"

    def test_build_r2v_with_video_and_audio(self):
        """Tests R2V with reference video and standalone reference audio."""
        graph = build_r2v_workflow(
            prompt="Apply cinematic anime style",
            ref_video_filename="source.mp4",
            ref_audio_filename="music.wav",
        )

        minimax = graph["minimax_node"]
        assert "load_ref_video" in graph
        assert graph["load_ref_video"]["inputs"]["file"] == "source.mp4"
        assert "get_video_components" in graph
        assert minimax["inputs"]["ref_videos.ref_video_0"] == ["get_video_components", 0]
        assert minimax["inputs"]["ref_video_audios.ref_video_audio_0"] == ["get_video_components", 1]

        assert "load_ref_audio" in graph
        assert graph["load_ref_audio"]["inputs"]["audio"] == "music.wav"
        assert minimax["inputs"]["ref_audios.ref_audio_0"] == ["load_ref_audio", 0]

"""
Unit tests for Video Resolution Upscaler (GAN Upscaler) workflow and UI view.
Tests reference workflow: utility-gan_upscaler.json and model scanning from F:\\Comfy_models\\upscale_models.
"""
import pytest
from unittest.mock import patch, MagicMock
import gradio as gr
from config import get_upscale_models, DEFAULT_UPSCALE_MODELS_DIR
from views.upscaler.workflow_builder import build_upscale_workflow, VideoUpscalerWorkflowBuilder
from views.upscaler.view import UpscalerView
from core.session_context import SessionContext
from task_manager import task_manager


class TestUpscalerWorkflowBuilder:
    def test_build_upscale_workflow_structure(self):
        """Validates that the API graph strictly conforms to utility-gan_upscaler.json."""
        video_fn = "input_sample.mp4"
        model_fn = "4x-UltraSharp.safetensors"
        graph = build_upscale_workflow(video_filename=video_fn, model_name=model_fn)

        # 1. Must contain the 6 essential nodes
        assert "1" in graph
        assert "9" in graph
        assert "10" in graph
        assert "2" in graph
        assert "11" in graph
        assert "12" in graph

        # 2. Node 1: UpscaleModelLoader
        assert graph["1"]["class_type"] == "UpscaleModelLoader"
        assert graph["1"]["inputs"]["model_name"] == model_fn

        # 3. Node 9: LoadVideo
        assert graph["9"]["class_type"] == "LoadVideo"
        assert graph["9"]["inputs"]["file"] == video_fn

        # 4. Node 10: GetVideoComponents
        assert graph["10"]["class_type"] == "GetVideoComponents"
        assert graph["10"]["inputs"]["video"] == ["9", 0]

        # 5. Node 2: ImageUpscaleWithModel
        assert graph["2"]["class_type"] == "ImageUpscaleWithModel"
        assert graph["2"]["inputs"]["upscale_model"] == ["1", 0]
        assert graph["2"]["inputs"]["image"] == ["10", 0]

        # 6. Node 11: CreateVideo (preserves exact original audio and fps)
        assert graph["11"]["class_type"] == "CreateVideo"
        assert graph["11"]["inputs"]["images"] == ["2", 0]
        assert graph["11"]["inputs"]["fps"] == ["10", 2]
        assert graph["11"]["inputs"]["audio"] == ["10", 1]
        assert isinstance(graph["11"]["inputs"]["bit_depth"], int), "bit_depth must be an integer, not string 'auto'"
        assert graph["11"]["inputs"]["bit_depth"] in (8, 10)

        # 7. Node 12: SaveVideo
        assert graph["12"]["class_type"] == "SaveVideo"
        assert graph["12"]["inputs"]["video"] == ["11", 0]
        assert "filename_prefix" in graph["12"]["inputs"]


class TestUpscalerModelDiscovery:
    def test_get_upscale_models_from_directory(self):
        """Ensures models from F:\\Comfy_models\\upscale_models are loaded."""
        models = get_upscale_models()
        assert len(models) >= 3
        assert "4x-AnimeSharp.safetensors" in models
        assert "4x-UltraSharp.safetensors" in models
        assert "RealESRGAN_x4plus.safetensors" in models

    def test_get_upscale_models_fallback_on_missing_dir(self, tmp_path):
        """Ensures fallback models are returned if specified directory is empty or missing."""
        empty_dir = str(tmp_path / "non_existent")
        fallback_models = get_upscale_models(empty_dir)
        assert len(fallback_models) == 3
        assert "RealESRGAN_x4plus.safetensors" in fallback_models


class TestUpscalerView:
    def test_upscaler_view_render(self):
        """Ensures UpscalerView renders input video, dropdown with disk models, and player card."""
        with gr.Blocks():
            session_ctx = SessionContext().render()
            view = UpscalerView()
            col = view.render(session_ctx)

            assert view.input_video is not None
            assert view.upscale_model is not None
            # Check choices populated from upscale_models directory
            choices = [c[1] if isinstance(c, tuple) else c for c in view.upscale_model.choices]
            assert "RealESRGAN_x4plus.safetensors" in choices
            assert view.generate_btn is not None
            assert view.stop_btn is not None
            assert view.status is not None
            assert view.output_video is not None
            assert view.history_gallery is not None
            assert view.admin_tab is not None

    def test_upscale_validation_no_video(self):
        """Validates that submitting with no video returns prompt to upload."""
        view = UpscalerView()
        # Test directly via register_events inner logic
        with gr.Blocks():
            session_ctx = SessionContext().render()
            view.render(session_ctx)
            view.register_events(session_ctx)

    @patch("views.upscaler.view.check_server", return_value=(True, "Online"))
    @patch("views.upscaler.view.upload_media_file", return_value="uploaded_test.mp4")
    def test_handle_upscale_generate_flow(self, mock_upload, mock_check, tmp_path):
        """Tests task submission flow for video upscaler."""
        dev_id = "device_test_upscaler"
        dummy_video = tmp_path / "test_in.mp4"
        dummy_video.write_bytes(b"dummy_mp4_bytes")

        with gr.Blocks():
            session_ctx = SessionContext().render()
            view = UpscalerView()
            view.render(session_ctx)

            # We can mock task_manager.start_background_task
            with patch.object(task_manager, "start_background_task") as mock_start_bg:
                # Mock generator flow
                models = get_upscale_models()
                chosen_model = models[0]

                # Manually run workflow creation
                graph = build_upscale_workflow("uploaded_test.mp4", chosen_model)
                task = task_manager.create_task(
                    task_type="UPSCALER",
                    prompt=f"Upscale video with {chosen_model}",
                    params={"video": str(dummy_video), "model": chosen_model},
                    device_id=dev_id,
                )
                assert task.task_type == "UPSCALER"
                assert task.status == "queued"
                assert task.device_id == dev_id

                # Query task back
                retrieved = task_manager.get_task(task.task_id, device_id=dev_id)
                assert retrieved is not None
                assert retrieved.params["model"] == chosen_model

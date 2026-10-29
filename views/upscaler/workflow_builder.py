"""
ComfyUI API workflow graph builder for Video Resolution Upscaler.
Directly models the native workflow:
F:\\program_file\\Comfy-Desktop\\ComfyUI-Installs\\ComfyUI (1)\\ComfyUI\\user\\default\\workflows\\utility-gan_upscaler.json
"""
from typing import Dict, Any


class VideoUpscalerWorkflowBuilder:
    """
    Constructs the ComfyUI API prompt JSON for video super-resolution upscaling.
    Preserves original video FPS and audio tracks without quality or timing loss.
    """

    def __init__(
        self,
        video_filename: str,
        model_name: str,
        filename_prefix: str = "video/Upscale",
    ):
        self.video_filename = video_filename
        self.model_name = model_name
        self.filename_prefix = filename_prefix

    def build(self) -> Dict[str, Any]:
        """
        Builds and returns the ComfyUI API graph.
        
        Topology:
        - 1: UpscaleModelLoader -> model_name
        - 9: LoadVideo -> file
        - 10: GetVideoComponents -> extracts (images, audio, fps)
        - 2: ImageUpscaleWithModel -> upscale_model + images
        - 11: CreateVideo -> upscaled images + original audio + original fps
        - 12: SaveVideo -> saves output MP4
        """
        return {
            "1": {
                "class_type": "UpscaleModelLoader",
                "inputs": {
                    "model_name": self.model_name,
                },
            },
            "9": {
                "class_type": "LoadVideo",
                "inputs": {
                    "file": self.video_filename,
                },
            },
            "10": {
                "class_type": "GetVideoComponents",
                "inputs": {
                    "video": ["9", 0],
                },
            },
            "2": {
                "class_type": "ImageUpscaleWithModel",
                "inputs": {
                    "upscale_model": ["1", 0],
                    "image": ["10", 0],
                },
            },
            "11": {
                "class_type": "CreateVideo",
                "inputs": {
                    "images": ["2", 0],
                    "fps": ["10", 2],
                    "audio": ["10", 1],
                    "bit_depth": 8,
                },
            },
            "12": {
                "class_type": "SaveVideo",
                "inputs": {
                    "video": ["11", 0],
                    "filename_prefix": self.filename_prefix,
                    "format": "auto",
                    "codec": "auto",
                },
            },
        }


def build_upscale_workflow(
    video_filename: str,
    model_name: str,
    filename_prefix: str = "video/Upscale",
) -> Dict[str, Any]:
    """Helper function to build upscale prompt graph."""
    builder = VideoUpscalerWorkflowBuilder(
        video_filename=video_filename,
        model_name=model_name,
        filename_prefix=filename_prefix,
    )
    return builder.build()

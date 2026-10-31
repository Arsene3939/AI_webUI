"""
ComfyUI API workflow graph builder for Video Resolution Upscaler.
Directly models the native workflow:
F:\\program_file\\Comfy-Desktop\\ComfyUI-Installs\\ComfyUI (1)\\ComfyUI\\user\\default\\workflows\\utility-gan_upscaler.json
"""
from typing import Dict, Any, Optional


class VideoUpscalerWorkflowBuilder:
    """
    Constructs the ComfyUI API prompt JSON for video super-resolution upscaling.
    Preserves original video FPS and audio tracks without quality or timing loss.

    進階輸出參數（Spec 2026-10-31 任務 6；預設值產出的圖與舊版完全相同）：
    - output_format: SaveVideo 的容器格式（"auto"|"mp4"；ComfyUI 0.30 VideoContainer）
    - bit_depth: CreateVideo 位元深度（8|10；10-bit 漸層較不易色帶，部分播放器不支援）
    - post_scale: 模型放大後再插一個核心 ImageScaleBy（area 縮放）的縮放倍率。
      None/0 代表不縮放（模型原生倍率；本機模型皆為 4x），0.5=淨 2x、0.25=淨 1x。
      對應官方 workflow 註記的建議：「先放大、再用 resize 節點降到目標解析度」。
    """

    def __init__(
        self,
        video_filename: str,
        model_name: str,
        filename_prefix: str = "video/Upscale",
        output_format: str = "auto",
        bit_depth: int = 8,
        post_scale: Optional[float] = None,
    ):
        self.video_filename = video_filename
        self.model_name = model_name
        self.filename_prefix = filename_prefix
        self.output_format = output_format if output_format in ("auto", "mp4") else "auto"
        self.bit_depth = int(bit_depth) if int(bit_depth) in (8, 10) else 8
        self.post_scale = float(post_scale) if post_scale else None

    def build(self) -> Dict[str, Any]:
        """
        Builds and returns the ComfyUI API graph.

        Topology:
        - 1: UpscaleModelLoader -> model_name
        - 9: LoadVideo -> file
        - 10: GetVideoComponents -> extracts (images, audio, fps)
        - 2: ImageUpscaleWithModel -> upscale_model + images
        - (13: ImageScaleBy -> 選用的輸出縮放，post_scale 有值時才存在)
        - 11: CreateVideo -> upscaled images + original audio + original fps
        - 12: SaveVideo -> saves output MP4
        """
        image_source: Any = ["2", 0]
        graph: Dict[str, Any] = {}
        if self.post_scale is not None:
            graph["13"] = {
                "class_type": "ImageScaleBy",
                "inputs": {
                    "image": ["2", 0],
                    "upscale_method": "area",
                    "scale_by": self.post_scale,
                },
            }
            image_source = ["13", 0]
        graph.update({
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
                    "images": image_source,
                    "fps": ["10", 2],
                    "audio": ["10", 1],
                    "bit_depth": self.bit_depth,
                },
            },
            "12": {
                "class_type": "SaveVideo",
                "inputs": {
                    "video": ["11", 0],
                    "filename_prefix": self.filename_prefix,
                    "format": self.output_format,
                    "codec": "auto",
                },
            },
        })
        return graph


def build_upscale_workflow(
    video_filename: str,
    model_name: str,
    filename_prefix: str = "video/Upscale",
    output_format: str = "auto",
    bit_depth: int = 8,
    post_scale: Optional[float] = None,
) -> Dict[str, Any]:
    """Helper function to build upscale prompt graph."""
    builder = VideoUpscalerWorkflowBuilder(
        video_filename=video_filename,
        model_name=model_name,
        filename_prefix=filename_prefix,
        output_format=output_format,
        bit_depth=bit_depth,
        post_scale=post_scale,
    )
    return builder.build()

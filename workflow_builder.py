"""
Workflow builders for MiniMax-H3 ComfyUI API prompts.
Produces native ComfyUI prompt graphs for I2V, T2V, and R2V tasks.
"""
from typing import Optional, List, Dict, Any
from config import (
    DEFAULT_UNET,
    DEFAULT_CLIP,
    DEFAULT_VIDEO_VAE,
    DEFAULT_AUDIO_VAE,
    duration_to_frames,
)


def build_i2v_workflow(
    prompt: str,
    first_frame_filename: str,
    last_frame_filename: Optional[str] = None,
    width: int = 1344,
    height: int = 768,
    duration_seconds: float = 2.0,
    seed: int = 1,
    steps: int = 20,
    denoise: float = 1.0,
    sampler_name: str = "res_multistep",
    scheduler_name: str = "simple",
    fps: float = 24.0,
    unet_name: str = DEFAULT_UNET,
    clip_name: str = DEFAULT_CLIP,
    video_vae_name: str = DEFAULT_VIDEO_VAE,
    audio_vae_name: str = DEFAULT_AUDIO_VAE,
) -> Dict[str, Any]:
    """Builds a prompt graph for Image-to-Video (I2V / 圖+文生影片)."""
    length = duration_to_frames(duration_seconds, int(fps))

    prompt_graph = {
        "unet_loader": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet_name, "weight_dtype": "default"},
        },
        "clip_loader": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": "minimax", "device": "default"},
        },
        "video_vae_loader": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": video_vae_name},
        },
        "audio_vae_loader": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": audio_vae_name},
        },
        "first_frame_loader": {
            "class_type": "LoadImage",
            "inputs": {"image": first_frame_filename},
        },
        "random_noise": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": int(seed)},
        },
        "sampler_select": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": sampler_name},
        },
        "basic_scheduler": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["unet_loader", 0],
                "scheduler": scheduler_name,
                "steps": int(steps),
                "denoise": float(denoise),
            },
        },
    }

    minimax_inputs: Dict[str, Any] = {
        "clip": ["clip_loader", 0],
        "vae": ["video_vae_loader", 0],
        "prompt": prompt,
        "width": int(width),
        "height": int(height),
        "length": int(length),
        "first_frame": ["first_frame_loader", 0],
    }

    if last_frame_filename:
        prompt_graph["last_frame_loader"] = {
            "class_type": "LoadImage",
            "inputs": {"image": last_frame_filename},
        }
        minimax_inputs["last_frame"] = ["last_frame_loader", 0]

    prompt_graph["minimax_node"] = {
        "class_type": "MiniMaxH3ImageToVideo",
        "inputs": minimax_inputs,
    }

    prompt_graph["basic_guider"] = {
        "class_type": "BasicGuider",
        "inputs": {
            "model": ["unet_loader", 0],
            "conditioning": ["minimax_node", 0],
        },
    }

    prompt_graph["sampler_custom_advanced"] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {
            "noise": ["random_noise", 0],
            "guider": ["basic_guider", 0],
            "sampler": ["sampler_select", 0],
            "sigmas": ["basic_scheduler", 0],
            "latent_image": ["minimax_node", 1],
        },
    }

    prompt_graph["vae_decode_video"] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["sampler_custom_advanced", 0],
            "vae": ["video_vae_loader", 0],
        },
    }

    prompt_graph["vae_decode_audio"] = {
        "class_type": "VAEDecodeAudio",
        "inputs": {
            "samples": ["sampler_custom_advanced", 0],
            "vae": ["audio_vae_loader", 0],
        },
    }

    prompt_graph["create_video"] = {
        "class_type": "CreateVideo",
        "inputs": {
            "images": ["vae_decode_video", 0],
            "audio": ["vae_decode_audio", 0],
            "fps": float(fps),
            "bit_depth": 8,
        },
    }

    prompt_graph["save_video"] = {
        "class_type": "SaveVideo",
        "inputs": {
            "video": ["create_video", 0],
            "filename_prefix": "video/MiniMax_H3_I2V",
            "format": "auto",
            "codec": "auto",
        },
    }

    return prompt_graph


def build_t2v_workflow(
    prompt: str,
    width: int = 1344,
    height: int = 768,
    duration_seconds: float = 2.0,
    seed: int = 1,
    steps: int = 20,
    denoise: float = 1.0,
    sampler_name: str = "res_multistep",
    scheduler_name: str = "simple",
    fps: float = 24.0,
    unet_name: str = DEFAULT_UNET,
    clip_name: str = DEFAULT_CLIP,
    video_vae_name: str = DEFAULT_VIDEO_VAE,
    audio_vae_name: str = DEFAULT_AUDIO_VAE,
) -> Dict[str, Any]:
    """Builds a prompt graph for pure Text-to-Video (T2V / 純文生影片)."""
    length = duration_to_frames(duration_seconds, int(fps))

    prompt_graph = {
        "unet_loader": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet_name, "weight_dtype": "default"},
        },
        "clip_loader": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": "minimax", "device": "default"},
        },
        "video_vae_loader": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": video_vae_name},
        },
        "audio_vae_loader": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": audio_vae_name},
        },
        "random_noise": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": int(seed)},
        },
        "sampler_select": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": sampler_name},
        },
        "basic_scheduler": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["unet_loader", 0],
                "scheduler": scheduler_name,
                "steps": int(steps),
                "denoise": float(denoise),
            },
        },
        "minimax_node": {
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": ["clip_loader", 0],
                "vae": ["video_vae_loader", 0],
                "prompt": prompt,
                "width": int(width),
                "height": int(height),
                "length": int(length),
            },
        },
        "basic_guider": {
            "class_type": "BasicGuider",
            "inputs": {
                "model": ["unet_loader", 0],
                "conditioning": ["minimax_node", 0],
            },
        },
        "sampler_custom_advanced": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["random_noise", 0],
                "guider": ["basic_guider", 0],
                "sampler": ["sampler_select", 0],
                "sigmas": ["basic_scheduler", 0],
                "latent_image": ["minimax_node", 1],
            },
        },
        "vae_decode_video": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["sampler_custom_advanced", 0],
                "vae": ["video_vae_loader", 0],
            },
        },
        "vae_decode_audio": {
            "class_type": "VAEDecodeAudio",
            "inputs": {
                "samples": ["sampler_custom_advanced", 0],
                "vae": ["audio_vae_loader", 0],
            },
        },
        "create_video": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["vae_decode_video", 0],
                "audio": ["vae_decode_audio", 0],
                "fps": float(fps),
                "bit_depth": 8,
            },
        },
        "save_video": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["create_video", 0],
                "filename_prefix": "video/MiniMax_H3_T2V",
                "format": "auto",
                "codec": "auto",
            },
        },
    }

    return prompt_graph


def build_r2v_workflow(
    prompt: str,
    ref_image_filenames: Optional[List[str]] = None,
    ref_video_filename: Optional[str] = None,
    ref_audio_filename: Optional[str] = None,
    ref_image_size: str = "match",
    width: int = 1344,
    height: int = 768,
    duration_seconds: float = 2.0,
    seed: int = 1,
    steps: int = 20,
    denoise: float = 1.0,
    sampler_name: str = "res_multistep",
    scheduler_name: str = "simple",
    fps: float = 24.0,
    unet_name: str = DEFAULT_UNET,
    clip_name: str = DEFAULT_CLIP,
    video_vae_name: str = DEFAULT_VIDEO_VAE,
    audio_vae_name: str = DEFAULT_AUDIO_VAE,
) -> Dict[str, Any]:
    """Builds a prompt graph for Reference-to-Video / Video-to-Video (R2V / 影片生影片)."""
    length = duration_to_frames(duration_seconds, int(fps))

    prompt_graph: Dict[str, Any] = {
        "unet_loader": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet_name, "weight_dtype": "default"},
        },
        "clip_loader": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": "minimax", "device": "default"},
        },
        "video_vae_loader": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": video_vae_name},
        },
        "audio_vae_loader": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": audio_vae_name},
        },
        "random_noise": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": int(seed)},
        },
        "sampler_select": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": sampler_name},
        },
        "basic_scheduler": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["unet_loader", 0],
                "scheduler": scheduler_name,
                "steps": int(steps),
                "denoise": float(denoise),
            },
        },
    }

    minimax_inputs: Dict[str, Any] = {
        "clip": ["clip_loader", 0],
        "vae": ["video_vae_loader", 0],
        "audio_vae": ["audio_vae_loader", 0],
        "prompt": prompt,
        "width": int(width),
        "height": int(height),
        "length": int(length),
        "ref_image_size": ref_image_size,
    }

    # Reference Images (e.g. ref_images.ref_image_0, ref_images.ref_image_1...)
    if ref_image_filenames:
        for i, img_filename in enumerate(ref_image_filenames):
            node_id = f"load_ref_image_{i}"
            prompt_graph[node_id] = {
                "class_type": "LoadImage",
                "inputs": {"image": img_filename},
            }
            minimax_inputs[f"ref_images.ref_image_{i}"] = [node_id, 0]

    # Reference Video (LoadVideo -> GetVideoComponents -> ref_videos & ref_video_audios)
    if ref_video_filename:
        prompt_graph["load_ref_video"] = {
            "class_type": "LoadVideo",
            "inputs": {"file": ref_video_filename},
        }
        prompt_graph["get_video_components"] = {
            "class_type": "GetVideoComponents",
            "inputs": {"video": ["load_ref_video", 0]},
        }
        minimax_inputs["ref_videos.ref_video_0"] = ["get_video_components", 0]
        minimax_inputs["ref_video_audios.ref_video_audio_0"] = ["get_video_components", 1]

    # Reference Standalone Audio
    if ref_audio_filename:
        prompt_graph["load_ref_audio"] = {
            "class_type": "LoadAudio",
            "inputs": {"audio": ref_audio_filename},
        }
        minimax_inputs["ref_audios.ref_audio_0"] = ["load_ref_audio", 0]

    prompt_graph["minimax_node"] = {
        "class_type": "MiniMaxH3ReferenceToVideo",
        "inputs": minimax_inputs,
    }

    prompt_graph["basic_guider"] = {
        "class_type": "BasicGuider",
        "inputs": {
            "model": ["unet_loader", 0],
            "conditioning": ["minimax_node", 0],
        },
    }

    prompt_graph["sampler_custom_advanced"] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {
            "noise": ["random_noise", 0],
            "guider": ["basic_guider", 0],
            "sampler": ["sampler_select", 0],
            "sigmas": ["basic_scheduler", 0],
            "latent_image": ["minimax_node", 1],
        },
    }

    prompt_graph["vae_decode_video"] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["sampler_custom_advanced", 0],
            "vae": ["video_vae_loader", 0],
        },
    }

    prompt_graph["vae_decode_audio"] = {
        "class_type": "VAEDecodeAudio",
        "inputs": {
            "samples": ["sampler_custom_advanced", 0],
            "vae": ["audio_vae_loader", 0],
        },
    }

    prompt_graph["create_video"] = {
        "class_type": "CreateVideo",
        "inputs": {
            "images": ["vae_decode_video", 0],
            "audio": ["vae_decode_audio", 0],
            "fps": float(fps),
            "bit_depth": 8,
        },
    }

    prompt_graph["save_video"] = {
        "class_type": "SaveVideo",
        "inputs": {
            "video": ["create_video", 0],
            "filename_prefix": "video/MiniMax_H3_R2V",
            "format": "auto",
            "codec": "auto",
        },
    }

    return prompt_graph

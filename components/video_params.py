"""
Reusable video generation parameters UI component (DRY principle).
Encapsulates aspect ratio, quality level, duration, steps, seed, denoise, sampler, and scheduler.
(Spec 2026-10-31 任務 5: fps 拉桿已移除 — MiniMax-H3 只支援 24fps，生成端固定用 MINIMAX_FIXED_FPS。)
"""
import random
import os
from typing import List, Optional, Tuple, Any
from PIL import Image
import gradio as gr
from config import (
    get_director_models,
    list_comfy_models,
    DEFAULT_UNET,
    DEFAULT_CLIP,
    DEFAULT_VIDEO_VAE,
    DEFAULT_AUDIO_VAE,
    ORIGINAL_RATIO_LABEL,
    I2V_ASPECT_RATIOS,
    T2V_ASPECT_RATIOS,
    QUALITY_CHOICES,
    DEFAULT_QUALITY_LEVEL,
    DEFAULT_MULTIPLE,
    SAMPLER_CHOICES,
    SCHEDULER_CHOICES,
    calculate_dimensions,
    calculate_dimensions_adaptive_ratio,
    normalize_aspect_ratio,
    normalize_quality_choice,
    normalize_sampler,
    normalize_scheduler,
)


def generate_random_seed() -> int:
    return random.randint(1, 999999999999999)


def on_resolution_change(ar: str, quality_str: str, img_path: Optional[str] = None) -> str:
    """Calculates resolution label when aspect ratio, quality level, or image changes."""
    quality_str = normalize_quality_choice(quality_str)

    if ar == ORIGINAL_RATIO_LABEL or "原圖" in str(ar) or "自動" in str(ar):
        if img_path and os.path.exists(img_path):
            try:
                with Image.open(img_path) as im:
                    orig_w, orig_h = im.size
                w, h = calculate_dimensions_adaptive_ratio(orig_w, orig_h, quality_str, multiple=DEFAULT_MULTIPLE)
                actual_mp = round((w * h) / 1_000_000, 2)
                return f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP)"
            except Exception:
                pass
        w, h = calculate_dimensions("16:9 (橫向風景)", quality_str, multiple=DEFAULT_MULTIPLE)
        actual_mp = round((w * h) / 1_000_000, 2)
        return f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP)"

    ar = normalize_aspect_ratio(ar, allow_original=False)
    w, h = calculate_dimensions(ar, quality_str, multiple=DEFAULT_MULTIPLE)
    actual_mp = round((w * h) / 1_000_000, 2)
    return f"📐 **輸出解析度**：`{w} x {h}` (~{actual_mp} MP)"


class VideoParamsComponent:
    """Encapsulates common generation parameter controls."""

    def __init__(
        self,
        aspect_ratio_choices: List[str] = I2V_ASPECT_RATIOS,
        default_aspect_ratio: str = ORIGINAL_RATIO_LABEL,
        default_quality: str = DEFAULT_QUALITY_LEVEL,
        default_duration: float = 2.0,
        default_steps: int = 20,
        include_director_model: bool = False,
        include_model_selectors: bool = False,
    ):
        # 導演模型下拉收在「⚙️ 進階參數」裡（Spec 2026-10-31 UI 簡化案）：
        # 只有挂了導演區塊的 tab（I2V）開旗標，其他 tab 不會憑空多出一個用不到的欄位。
        self.include_director_model = include_director_model
        # 生成模型選擇（管理員限定，Spec 2026-11-02）：一般使用者看不到這區，
        # 且後端 resolve_model_names 另有一道把關，UI 藏不藏都只能用預設模型。
        self.include_model_selectors = include_model_selectors
        self.aspect_ratio_choices = aspect_ratio_choices
        self.default_aspect_ratio = default_aspect_ratio
        self.default_quality = default_quality
        self.default_duration = default_duration
        self.default_steps = default_steps

        self.aspect_ratio: Optional[gr.Dropdown] = None
        self.quality_level: Optional[gr.Dropdown] = None
        self.res_info: Optional[gr.Markdown] = None
        self.duration: Optional[gr.Slider] = None
        self.steps: Optional[gr.Slider] = None
        self.seed: Optional[gr.Number] = None
        self.rand_btn: Optional[gr.Button] = None
        self.denoise: Optional[gr.Slider] = None
        self.sampler: Optional[gr.Dropdown] = None
        self.scheduler: Optional[gr.Dropdown] = None
        self.director_model: Optional[gr.Dropdown] = None
        # 管理員模型選擇區（build-time 一律隱藏；開頁時由 super-user 檢查決定可可見）
        self.model_row: Optional[gr.Row] = None
        self.model_unet: Optional[gr.Dropdown] = None
        self.model_clip: Optional[gr.Dropdown] = None
        self.model_video_vae: Optional[gr.Dropdown] = None
        self.model_audio_vae: Optional[gr.Dropdown] = None

    def render(self) -> "VideoParamsComponent":
        # Row 1: Aspect Ratio, Quality Level
        with gr.Row():
            self.aspect_ratio = gr.Dropdown(
                choices=self.aspect_ratio_choices,
                value=self.default_aspect_ratio,
                label="長寬比",
                scale=1,
                filterable=False,
            )
            self.quality_level = gr.Dropdown(
                choices=QUALITY_CHOICES,
                value=self.default_quality,
                label="畫質等級",
                scale=1,
                filterable=False,
            )

        with gr.Row():
            self.res_info = gr.Markdown("📐 **輸出解析度**：`1344 x 768` (~1.03 MP)")

        # Row 2: Duration, Steps（影格率固定 24fps，不開放調整 — Spec 任務 5）
        with gr.Row():
            with gr.Column():
                self.duration = gr.Slider(
                    minimum=1.0, maximum=15.0, value=self.default_duration, step=0.5,
                    label="影片時長 (秒)", scale=2
                )
            with gr.Column():
                self.steps = gr.Slider(
                    minimum=1, maximum=50, value=self.default_steps, step=1,
                    label="取樣步數", scale=2
                )

        with gr.Accordion("⚙️ 進階參數", open=False):
            with gr.Row():
                self.seed = gr.Number(value=1, precision=0, label="隨機種子", scale=4)
                self.rand_btn = gr.Button("🎲 隨機", scale=1)
            with gr.Row():
                self.denoise = gr.Slider(minimum=0.1, maximum=1.0, value=1.0, step=0.05, label="去噪強度")
            with gr.Row():
                self.sampler = gr.Dropdown(choices=SAMPLER_CHOICES, value="res_multistep", label="取樣器", filterable=False)
                self.scheduler = gr.Dropdown(choices=SCHEDULER_CHOICES, value="simple", label="調度器", filterable=False)
            if self.include_director_model:
                director_models = get_director_models()
                with gr.Row():
                    self.director_model = gr.Dropdown(
                        choices=director_models,
                        value=(director_models[0] if director_models else None),
                        label="導演模型",
                        info="「優化提示詞」按鈕使用的導演模型；放好新模型後清單會自動更新",
                        filterable=False,
                        interactive=bool(director_models),
                        allow_custom_value=False,
                    )

            if self.include_model_selectors:
                # 管理員限定：build-time 隱藏，開頁時 super-user 檢查決定可見性；
                # choices 每次開頁從模型資料夾重掃（放新模型即出現在清單）。
                def _mk(kind: str, default: str, label: str) -> gr.Dropdown:
                    return gr.Dropdown(
                        choices=list_comfy_models(kind, preferred=default),
                        value=default, label=label,
                        filterable=False, allow_custom_value=False,
                    )

                # 整個區（標題＋兩列下拉）包在同一個可見性受控的容器裡，
                # 開頁 load 時 super-user 才看得到全部元素。
                with gr.Column(visible=False) as self.model_row:
                    gr.Markdown("🧠 **生成模型**（管理員限定；一般使用者一律使用預設模型）")
                    with gr.Row():
                        self.model_unet = _mk("unet", DEFAULT_UNET, "生成模型 (UNET)")
                        self.model_clip = _mk("clip", DEFAULT_CLIP, "文字Encoding模型 (CLIP)")
                    with gr.Row():
                        self.model_video_vae = _mk("vae", DEFAULT_VIDEO_VAE, "影像 VAE")
                        self.model_audio_vae = _mk("vae", DEFAULT_AUDIO_VAE, "音訊 VAE")

        return self

    def register_events(self, image_ref: Optional[gr.Image] = None):
        """Binds resolution calculation and random seed button events."""
        if self.rand_btn and self.seed:
            self.rand_btn.click(generate_random_seed, outputs=[self.seed])

        inputs = [self.aspect_ratio, self.quality_level]
        if image_ref is not None:
            inputs.append(image_ref)

        for comp in [self.aspect_ratio, self.quality_level]:
            if comp and self.res_info:
                comp.change(on_resolution_change, inputs=inputs, outputs=[self.res_info])

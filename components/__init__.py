"""
Reusable UI Components for AI WebUI.
"""
from components.styles import CUSTOM_CSS, CUSTOM_HEAD_JS
from components.header import HeaderComponent, build_header_html
from components.dashboard_sidebar import DashboardNavComponent, MODULE_CHOICES, MODULE_MINIMAX, MODULE_UPSCALER, MODULE_STRATA
from components.comfy_toolbar import ComfyToolbarComponent
from components.video_params import VideoParamsComponent, generate_random_seed, on_resolution_change
from components.media_player import VideoPlayerCardComponent, ActionButtonsComponent, build_progress_html
from components.history_gallery import HistoryGalleryComponent, get_history_dropdown_choices, on_select_history_item, on_delete_history_item

__all__ = [
    "CUSTOM_CSS",
    "CUSTOM_HEAD_JS",
    "HeaderComponent",
    "build_header_html",
    "DashboardNavComponent",
    "MODULE_CHOICES",
    "MODULE_MINIMAX",
    "MODULE_UPSCALER",
    "MODULE_STRATA",
    "ComfyToolbarComponent",
    "VideoParamsComponent",
    "VideoPlayerCardComponent",
    "ActionButtonsComponent",
    "build_progress_html",
    "HistoryGalleryComponent",
    "get_history_dropdown_choices",
    "on_select_history_item",
    "on_delete_history_item",
    "generate_random_seed",
    "on_resolution_change",
]

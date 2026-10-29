"""
Functional views for AI WebUI.
"""
from views.minimax.view import MiniMaxView
from views.upscaler.view import UpscalerView
from views.strata.view import StrataView
from views.admin.view import AdminPanelView

__all__ = [
    "MiniMaxView",
    "UpscalerView",
    "StrataView",
    "AdminPanelView",
]

"""
MiniMax-H3 video generation module.
"""
from views.minimax.view import MiniMaxView
from views.minimax.tabs import I2VTab, T2VTab, R2VTab, on_first_frame_change

__all__ = [
    "MiniMaxView",
    "I2VTab",
    "T2VTab",
    "R2VTab",
    "on_first_frame_change",
]

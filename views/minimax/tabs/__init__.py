"""
Tabs for MiniMax-H3 view.
"""
from views.minimax.tabs.i2v_tab import I2VTab, on_first_frame_change
from views.minimax.tabs.t2v_tab import T2VTab
from views.minimax.tabs.r2v_tab import R2VTab

__all__ = [
    "I2VTab",
    "T2VTab",
    "R2VTab",
    "on_first_frame_change",
]

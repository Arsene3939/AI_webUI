"""
Regression guard for the sidebar collapse affordance (spec task 5):
gradio's native chevron toggle is nearly invisible on our dark sidebar,
so CUSTOM_CSS must keep the high-contrast .toggle-button styling.
"""
from components.styles import CUSTOM_CSS


class TestSidebarToggleAffordance:
    def test_toggle_button_high_contrast_styling_present(self):
        assert ".sidebar .toggle-button" in CUSTOM_CSS, "sidebar 收合拉頁籤的高對比樣式被移除了"
        assert ".sidebar .chevron-left" in CUSTOM_CSS, "chevron 箭頭的可見度樣式被移除了"

    def test_toggle_styling_declared_after_sidebar_base_rules(self):
        tab_rule = CUSTOM_CSS.find(".sidebar .toggle-button {")
        sidebar_base = CUSTOM_CSS.find("div[class*=\"sidebar\"] {")
        assert tab_rule != -1 and sidebar_base != -1
        assert tab_rule > sidebar_base, "拉頁籤樣式必須排在 sidebar 基礎樣式之後才能確保疊代優先"

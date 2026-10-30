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
        sidebar_base = CUSTOM_CSS.find(".sidebar:not(.right),")
        assert tab_rule != -1 and sidebar_base != -1
        assert tab_rule > sidebar_base, "拉頁籤樣式必須排在 sidebar 基礎樣式之後才能確保疊代優先"

    def test_no_broad_selector_may_squish_the_app_container(self):
        """防回歸：`div[class*="sidebar"]` 曾命中 gradio 6 的 .sidebar-parent（整個 App 的
        flex 主容器）並把整頁壓成 260px 寬。此選擇器不准再出現。"""
        assert 'div[class*="sidebar"]' not in CUSTOM_CSS

    def test_sidebar_sized_by_scoped_rule_only(self):
        """側欄寬度/離屏定位必須由 .sidebar:not(.right)  scoped 規則統一管理。"""
        assert "width: 260px !important" in CUSTOM_CSS
        assert "left: -260px !important" in CUSTOM_CSS
        assert "transform: translateX(260px) !important" in CUSTOM_CSS


class TestFeedbackLineBoxlessGuard:
    """Spec 2026-10-31 round 3 task 3: status-feedback Markdown lines
    (backend status, last-frame hint, admin op messages) must render as bare
    natural text like the task progress line — no box paint on the element,
    and the theme's .block wrapper must not re-add a second box either."""

    def test_backend_status_box_paints_no_box(self):
        assert ".backend-status-box {" in CUSTOM_CSS
        assert "background: transparent !important" in CUSTOM_CSS
        assert "border: none !important" in CUSTOM_CSS
        assert "box-shadow: none !important" in CUSTOM_CSS

    def test_block_wrapper_strip_rule_present(self):
        """gradio 的 .block 包装層必須被 :has 規則脫掉，否則又出現兩層方塊。"""
        assert ".block:has(> .backend-status-box)" in CUSTOM_CSS

    def test_dead_res_display_class_stays_removed(self):
        """res-display-box 從未有任何元件使用（死 CSS），不准再出現。"""
        assert "res-display-box" not in CUSTOM_CSS


class TestDarkTextGuards:
    """Spec 2026-10-31 round 2 task 2: dark-backed UI blocks must pin their own
    text colors so a light-OS/gradio light theme can never render black-on-dark."""

    def test_header_and_status_boxes_force_light_text(self):
        assert ".header-card h2" in CUSTOM_CSS
        assert ".backend-status-box," in CUSTOM_CSS or ".backend-status-box {" in CUSTOM_CSS
        assert "color: #f8fafc !important" in CUSTOM_CSS
        assert "color: #e2e8f0 !important" in CUSTOM_CSS


class TestDesktopLayoutGuard:
    """Spec 2026-10-31 task 3: desktop (>=1024px) gets a wider centered layout,
    and every desktop override must live INSIDE the min-width media query so the
    mobile layout stays untouched."""

    def test_desktop_media_query_present(self):
        assert "@media (min-width: 1024px)" in CUSTOM_CSS, "電腦版排版優化區塊被移除了"

    def test_desktop_block_widens_container(self):
        block = CUSTOM_CSS.split("@media (min-width: 1024px)", 1)[1]
        assert ".container" in block
        assert "max-width: 1280px" in block, "電腦版容器寬度上限被改掉了"

    def test_global_container_cap_is_not_wider_than_desktop_cap(self):
        # The base (mobile) .container rule must not exceed the desktop cap.
        base = CUSTOM_CSS.split("@media (min-width: 1024px)", 1)[0]
        assert "max-width: 1000px" in base

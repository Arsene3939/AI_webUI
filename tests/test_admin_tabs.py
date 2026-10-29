"""
Unit tests for Admin Tab OOP hierarchy, encapsulation, and inheritance across views.
"""
import pytest
from unittest.mock import MagicMock
import gradio as gr
from core.base_admin_tab import BaseAdminTab
from core.comfy_admin_tab import ComfyUIAdminTab
from core.admin_manager import AdminManager
from core.session_context import SessionContext
from views.minimax.admin_tab import MiniMaxAdminTab
from views.upscaler.admin_tab import UpscalerAdminTab
from views.strata.admin_tab import StrataAdminTab


class TestAdminTabHierarchy:
    def test_inheritance_hierarchy(self):
        """Verifies proper OOP inheritance tree."""
        assert issubclass(ComfyUIAdminTab, BaseAdminTab)
        assert issubclass(MiniMaxAdminTab, ComfyUIAdminTab)
        assert issubclass(UpscalerAdminTab, ComfyUIAdminTab)
        assert issubclass(StrataAdminTab, BaseAdminTab)

    def test_admin_manager_ip_normalization(self):
        """Tests that IPv4-mapped IPv6, loopback, and custom IPs are correctly recognized."""
        # 1. Standard localhost & loopback
        req_local = MagicMock()
        req_local.client.host = "127.0.0.1"
        assert AdminManager.is_super_user(req_local) is True

        req_ipv6_loopback = MagicMock()
        req_ipv6_loopback.client.host = "::1"
        assert AdminManager.is_super_user(req_ipv6_loopback) is True

        # 2. IPv4-mapped IPv6 loopback (very common in Windows ASGI/Uvicorn)
        req_mapped_local = MagicMock()
        req_mapped_local.client.host = "::ffff:127.0.0.1"
        assert AdminManager.is_super_user(req_mapped_local) is True

        # 3. Custom admin IP with IPv4-mapped prefix
        test_ip = "192.168.1.99"
        AdminManager.save_admin_ip_list([test_ip])
        try:
            req_custom_ipv4 = MagicMock()
            req_custom_ipv4.client.host = test_ip
            assert AdminManager.is_super_user(req_custom_ipv4) is True

            req_custom_mapped = MagicMock()
            req_custom_mapped.client.host = f"::ffff:{test_ip}"
            assert AdminManager.is_super_user(req_custom_mapped) is True

            # Unauthorized IP
            req_unauth = MagicMock()
            req_unauth.client.host = "192.168.1.200"
            assert AdminManager.is_super_user(req_unauth) is False
        finally:
            AdminManager.save_admin_ip_list([])

    def test_minimax_admin_tab_components(self):
        """Ensures MiniMaxAdminTab instantiates base, comfy, and minimax specific components."""
        with gr.Blocks():
            session_ctx = SessionContext().render()
            tab = MiniMaxAdminTab()
            tab.render(session_ctx)

            # Base components
            assert tab.status_badge is not None
            assert tab.toggle_status_btn is not None
            assert tab.hw_dashboard_html is not None
            assert tab.devices_html is not None
            assert tab.new_ip_input is not None

            # ComfyUI components
            assert tab.free_vram_btn is not None
            assert tab.restart_backend_btn is not None
            assert tab.queue_html is not None

            # MiniMax specific components
            assert tab.device_filter is not None
            assert tab.status_filter is not None
            assert tab.all_tasks_dropdown is not None

    def test_upscaler_admin_tab_components(self):
        """Ensures UpscalerAdminTab instantiates comfy and upscaler specific controls."""
        with gr.Blocks():
            session_ctx = SessionContext().render()
            tab = UpscalerAdminTab()
            tab.render(session_ctx)

            assert tab.free_vram_btn is not None
            assert tab.clean_cache_btn is not None

    def test_strata_admin_tab_components(self):
        """Ensures StrataAdminTab instantiates base and strata LLM endpoint configuration."""
        with gr.Blocks():
            session_ctx = SessionContext().render()
            tab = StrataAdminTab()
            tab.render(session_ctx)

            assert tab.hw_dashboard_html is not None
            assert tab.api_base_input is not None
            assert tab.test_conn_btn is not None
            # Strata should not have ComfyUI specific VRAM purge button
            assert not hasattr(tab, "free_vram_btn")


class TestDashboardSidebar:
    def test_sidebar_dashboard_structure(self):
        """Ensures Dashboard uses gr.Sidebar and no dropdowns."""
        from components.dashboard_sidebar import (
            DashboardNavComponent,
            MODULE_MINIMAX,
            MODULE_UPSCALER,
            MODULE_STRATA,
        )

        with gr.Blocks():
            comp = DashboardNavComponent()
            comp.render()

            assert isinstance(comp.sidebar, gr.Sidebar)
            assert isinstance(comp.module_selector, gr.Radio)
            assert comp.btn_minimax is not None
            assert comp.btn_upscaler is not None
            assert comp.btn_strata is not None
            # Verify no dropdown is used for module selection
            assert not isinstance(comp.module_selector, gr.Dropdown)


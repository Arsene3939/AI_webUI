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
        """Ensures Dashboard uses gr.Sidebar with 3 page links (/minimax /upscaler /strata).
        (Routing refactor 2026-10-31: the in-page radio switcher became real page links.)"""
        from components.dashboard_sidebar import DashboardNavComponent, MODULE_MINIMAX

        with gr.Blocks():
            comp = DashboardNavComponent(active_module=MODULE_MINIMAX)
            comp.render()

            assert isinstance(comp.sidebar, gr.Sidebar)
            assert comp.links_html is not None

            html = comp.links_html.value
            # exactly 3 anchor links to the routed pages
            assert html.count('<a class="dashboard-link') == 3
            for href in ('href="/minimax"', 'href="/upscaler"', 'href="/strata"'):
                assert href in html
            # the page rendering the sidebar highlights its own link
            assert 'dashboard-link active" href="/minimax"' in html
            assert 'dashboard-link active" href="/upscaler"' not in html




class TestAdminTaskFilter:
    """Regression (2026-11-01): the filter triggers returned the raw choices LIST as
    the dropdown's *value* — menu never re-filtered and gradio raised
    "'…' is not in the list of choices". apply_task_filter must return
    gr.update(choices=…, value=…) with value always inside choices."""

    ADMIN_REQ = MagicMock(client=MagicMock(host="127.0.0.1"))

    def _mk_task(self, device_id, status):
        from task_manager import task_manager
        t = task_manager.create_task("I2V", f"prompt {device_id} {status}", {"prompt": "x"}, device_id=device_id)
        t.status = status
        return t.task_id

    def _ids(self, upd):
        return [c[1] for c in upd["choices"]]

    def test_apply_task_filter_returns_update_dict(self):
        id_a = self._mk_task("dev_alpha", "completed")
        id_b = self._mk_task("dev_beta", "failed")

        upd, dev_upd = AdminManager.apply_task_filter("全部裝置", "全部狀態", request=self.ADMIN_REQ)
        assert isinstance(upd, dict) and upd.get("__type__") == "update"
        assert dev_upd.get("choices") == AdminManager.get_admin_device_filter_choices()
        ids = self._ids(upd)
        assert id_a in ids and id_b in ids
        assert upd["value"] in ids

    def test_device_filter_filters_and_snaps_invalid_value(self):
        id_a = self._mk_task("dev_alpha", "completed")
        id_b = self._mk_task("dev_beta", "failed")

        upd, _dev = AdminManager.apply_task_filter("dev_alpha", "全部狀態", current_task_id=id_b, request=self.ADMIN_REQ)
        ids = self._ids(upd)
        assert id_a in ids and id_b not in ids
        assert upd["value"] in ids  # snapped: previous selection no longer offered

    def test_status_filter_keeps_valid_selection(self):
        id_a = self._mk_task("dev_alpha", "completed")
        id_b = self._mk_task("dev_beta", "failed")

        upd, _dev = AdminManager.apply_task_filter("全部裝置", "失敗/中斷", current_task_id=id_b, request=self.ADMIN_REQ)
        ids = self._ids(upd)
        assert id_b in ids and id_a not in ids
        assert upd["value"] == id_b

    def test_empty_result_value_is_placeholder(self):
        self._mk_task("dev_alpha", "completed")
        upd, _dev = AdminManager.apply_task_filter("dev_ghost", "全部狀態", request=self.ADMIN_REQ)
        assert self._ids(upd) == [""]
        assert upd["value"] == ""  # value "" is a real (placeholder) choice -> no error

    def test_non_admin_gets_noop_update(self):
        upd, dev_upd = AdminManager.apply_task_filter("全部裝置", "全部狀態", request=None)
        assert isinstance(upd, dict) and upd.get("__type__") == "update"
        assert "choices" not in upd and "choices" not in dev_upd

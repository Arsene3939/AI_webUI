"""
Unit tests for the backend-shutdown safeguard (spec task 4) and its admin override
(spec 2026-10-31 task 1):
the 🛑 toolbar stop button and the admin "restart backend" action must refuse to kill
ComfyUI while jobs are queued/running for REGULAR users — but a super user's 🛑 press
must FORCE-shutdown, interrupting every active task first.
"""
from types import SimpleNamespace

import pytest

import core.admin_manager as admin_module
import components.comfy_toolbar as comfy_toolbar
from core.admin_manager import AdminManager
from components.comfy_toolbar import ComfyToolbarComponent
from task_manager import TaskManager, task_manager


def _fake_running(n):
    """Lightweight stand-ins for active Task objects (only len() is consulted)."""
    return [SimpleNamespace(status="running") for _ in range(n)]


class TestActiveTaskCountSemantics:
    def test_counts_only_queued_and_running_across_devices_and_modules(self):
        tm = TaskManager()
        t_q = tm.create_task("I2V", "queued job", {}, device_id="dev_1")
        t_up = tm.create_task("UPSCALER", "queued upscale", {}, device_id="dev_2")
        t_done = tm.create_task("T2V", "done job", {}, device_id="dev_3")
        t_dead = tm.create_task("I2V", "interrupted job", {}, device_id="dev_4")
        t_done.status = "completed"
        t_dead.status = "interrupted"

        assert tm.get_active_task_count() == 2
        overview = tm.get_active_tasks_overview()
        assert {t.task_id for t in overview} == {t_q.task_id, t_up.task_id}

        t_q.status = "completed"
        assert tm.get_active_task_count() == 1

    def test_empty_manager_reports_zero(self):
        tm = TaskManager()
        assert tm.get_active_task_count() == 0
        assert tm.get_active_tasks_overview() == []


class TestToolbarStopBackendGuard:
    @pytest.fixture
    def toolbar(self, monkeypatch):
        # Neutralise live ComfyUI probing and the real kill routine (calls recorded).
        monkeypatch.setattr(comfy_toolbar, "check_server", lambda url: (True, ""))
        recorder = []
        monkeypatch.setattr(
            comfy_toolbar, "stop_comfyui_backend",
            lambda url=None: recorder.append(url) or (True, "🛑 後端模型已關閉"),
        )
        component = ComfyToolbarComponent()
        component.stop_calls = recorder
        return component

    def test_shutdown_blocked_while_tasks_active(self, toolbar, monkeypatch):
        monkeypatch.setattr(
            comfy_toolbar.task_manager, "get_active_tasks_overview",
            lambda: _fake_running(2), raising=False,
        )
        _, msg = toolbar.on_stop_backend()
        assert "無法關閉後端模型" in msg
        assert "2 個工作" in msg
        assert "停止按鈕" in msg
        assert toolbar.stop_calls == [], "Backend was killed despite active tasks!"

    def test_shutdown_allowed_when_idle(self, toolbar, monkeypatch):
        monkeypatch.setattr(
            comfy_toolbar.task_manager, "get_active_tasks_overview",
            lambda: [], raising=False,
        )
        _, msg = toolbar.on_stop_backend()
        assert toolbar.stop_calls, "stop_comfyui_backend was never called while idle"
        assert "後端模型已關閉" in msg
        assert "無法關閉" not in msg

    def test_single_active_job_reported_in_message(self, toolbar, monkeypatch):
        monkeypatch.setattr(
            comfy_toolbar.task_manager, "get_active_tasks_overview",
            lambda: _fake_running(1), raising=False,
        )
        _, msg = toolbar.on_stop_backend()
        assert "1 個工作正在排队或生成中" in msg


class TestAdminRestartBackendGuard:
    @pytest.fixture
    def patched_admin(self, monkeypatch):
        monkeypatch.setattr(AdminManager, "is_super_user", lambda request=None: True)
        monkeypatch.setattr(admin_module.time, "sleep", lambda s: None)
        stop_calls, start_calls = [], []
        monkeypatch.setattr(admin_module, "stop_comfyui_backend", lambda url=None: stop_calls.append(url))
        monkeypatch.setattr(
            admin_module, "start_comfyui_backend",
            lambda url=None: start_calls.append(url) or (True, "🟢 後端模型已啟動"),
        )
        return stop_calls, start_calls

    def test_restart_blocked_while_tasks_active(self, patched_admin, monkeypatch):
        stop_calls, start_calls = patched_admin
        monkeypatch.setattr(task_manager, "get_active_task_count", lambda: 3, raising=False)
        msg = AdminManager.on_restart_backend()
        assert "無法重啟後端" in msg
        assert "3 個工作" in msg
        assert "清空所有等待中排隊佇列" in msg
        assert stop_calls == [] and start_calls == [], "Restart killed the backend despite active tasks!"

    def test_restart_allowed_when_idle(self, patched_admin, monkeypatch):
        stop_calls, start_calls = patched_admin
        monkeypatch.setattr(task_manager, "get_active_task_count", lambda: 0, raising=False)
        msg = AdminManager.on_restart_backend()
        assert stop_calls and start_calls, "Restart did not stop+start the backend while idle"
        assert "後端模型已啟動" in msg

    def test_restart_guard_runs_after_permission_check(self, monkeypatch):
        monkeypatch.setattr(AdminManager, "is_super_user", lambda request=None: False)
        monkeypatch.setattr(task_manager, "get_active_task_count", lambda: pytest.fail("guard ran before auth"), raising=False)
        msg = AdminManager.on_restart_backend()
        assert "權限不足" in msg


class TestAdminForceStopBackend:
    """Spec 2026-10-31 task 1: an admin's 🛑 press force-kills the backend, ignoring
    queued/running tasks — but every interrupted task is marked first so history stays honest."""

    def _admin_request(self):
        return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    @pytest.fixture
    def toolbar(self, monkeypatch):
        monkeypatch.setattr(comfy_toolbar, "check_server", lambda url: (True, ""))
        recorder = []
        monkeypatch.setattr(
            comfy_toolbar, "stop_comfyui_backend",
            lambda url=None: recorder.append(url) or (True, "🛑 後端模型已關閉"),
        )
        monkeypatch.setattr(
            AdminManager, "is_super_user",
            lambda request=None: (getattr(getattr(request, "client", None), "host", "") == "127.0.0.1"),
        )
        component = ComfyToolbarComponent()
        component.stop_calls = recorder
        return component

    def test_force_stop_interrupts_all_tasks_then_kills_backend(self, toolbar, monkeypatch):
        monkeypatch.setattr(
            comfy_toolbar.task_manager, "get_active_tasks_overview",
            lambda: _fake_running(2), raising=False,
        )
        interrupts = []
        monkeypatch.setattr(
            comfy_toolbar.task_manager, "interrupt_device_tasks",
            lambda device_id=None, module=None: interrupts.append((device_id, module)) or ["t1", "t2"],
            raising=False,
        )
        _, msg = toolbar.on_stop_backend(request=self._admin_request())
        assert "強制關閉" in msg
        assert "已中斷 2 個進行中的工作" in msg
        assert interrupts == [(None, None)], "Force stop must interrupt ALL devices/modules"
        assert toolbar.stop_calls, "Backend was not killed on the admin force path"

    def test_force_stop_when_idle_shuts_down_without_interrupting(self, toolbar, monkeypatch):
        monkeypatch.setattr(comfy_toolbar.task_manager, "get_active_tasks_overview", lambda: [], raising=False)
        monkeypatch.setattr(
            comfy_toolbar.task_manager, "interrupt_device_tasks",
            lambda **kw: pytest.fail("interrupt called with no active tasks"), raising=False,
        )
        _, msg = toolbar.on_stop_backend(request=self._admin_request())
        assert "後端模型已關閉" in msg
        assert toolbar.stop_calls

    def test_non_admin_request_kept_blocked_by_safeguard(self, toolbar, monkeypatch):
        monkeypatch.setattr(
            comfy_toolbar.task_manager, "get_active_tasks_overview",
            lambda: _fake_running(1), raising=False,
        )
        stranger = SimpleNamespace(client=SimpleNamespace(host="203.0.113.9"))
        _, msg = toolbar.on_stop_backend(request=stranger)
        assert "無法關閉後端模型" in msg
        assert toolbar.stop_calls == [], "Non-admin must never force-kill the backend"

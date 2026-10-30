"""
Extended unit tests for the serial dispatch queue: multi-device / multi-module fairness,
interrupt-delete interactions, restart recovery, and concurrent submission stress.
(Spec tasks 1: queuing mechanism hardening)
"""
import json
import threading
import time

import pytest

from task_manager import TaskManager


def install_fake_worker(monkeypatch, behavior):
    """Replaces _monitor_worker with a scripted stand-in; returns (execution_call_log, activity_stats)."""
    calls = []
    activity = {"count": 0, "max": 0}

    def fake_worker(self, task, prompt_graph, server_url):
        assert task.task_id not in calls, f"Task {task.task_id} executed more than once!"
        activity["count"] += 1
        activity["max"] = max(activity["max"], activity["count"])
        calls.append(task.task_id)
        try:
            behavior(task)
        finally:
            activity["count"] -= 1

    monkeypatch.setattr(TaskManager, "_monitor_worker", fake_worker)
    return calls, activity


def wait_for_status(tasks, statuses=("completed",), timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if all(t.status in statuses for t in tasks):
            return True
        time.sleep(0.02)
    return False


class TestMultiDeviceFifoOrder:
    def test_arrival_order_interleaved_across_devices(self, monkeypatch):
        """Two users' jobs must run strictly in submission order across devices, one at a time."""
        def behavior(task):
            time.sleep(0.15)
            task.status = "completed"
            task.stage = "completed"

        calls, activity = install_fake_worker(monkeypatch, behavior)
        tm = TaskManager()

        t_a1 = tm.create_task("I2V", "user A job 1", {}, device_id="dev_A")
        t_b1 = tm.create_task("UPSCALER", "user B job 1", {}, device_id="dev_B")
        t_a2 = tm.create_task("T2V", "user A job 2", {}, device_id="dev_A")
        tm.start_background_task(t_a1, {})
        tm.start_background_task(t_b1, {})
        tm.start_background_task(t_a2, {})

        assert wait_for_status([t_a1, t_b1, t_a2]), \
            f"Not all tasks completed: {[t.status for t in (t_a1, t_b1, t_a2)]}"
        assert calls == [t_a1.task_id, t_b1.task_id, t_a2.task_id], "Cross-device arrival (FIFO) order violated"
        assert activity["max"] == 1, "Serial execution violated: backend overlap detected"

    def test_queued_message_counts_multiple_tasks_ahead(self, monkeypatch):
        """With one job running and two waiting, the 2nd/3rd waiters must report 1 and 2 jobs ahead."""
        started = threading.Event()
        release = threading.Event()

        def behavior(task):
            if "blocker" in task.prompt:
                started.set()
                release.wait(timeout=10)
            task.status = "completed"
            task.stage = "completed"

        install_fake_worker(monkeypatch, behavior)
        tm = TaskManager()

        t_block = tm.create_task("I2V", "blocker", {}, device_id="dev_msg2")
        t_wait1 = tm.create_task("UPSCALER", "waiter one", {}, device_id="dev_msg2")
        t_wait2 = tm.create_task("I2V", "waiter two", {}, device_id="dev_msg2")

        tm.start_background_task(t_block, {})
        assert started.wait(timeout=5)
        tm.start_background_task(t_wait1, {})
        tm.start_background_task(t_wait2, {})

        assert "前面還有 1 個工作" in t_wait1.message, f"1st waiter message wrong: {t_wait1.message}"
        assert "前面還有 2 個工作" in t_wait2.message, f"2nd waiter message wrong: {t_wait2.message}"

        release.set()
        assert wait_for_status([t_block, t_wait1, t_wait2])


class TestInterruptAndDeleteInteractions:
    def _make_blocker_env(self, monkeypatch):
        started = threading.Event()
        release = threading.Event()

        def behavior(task):
            if "blocker" in task.prompt:
                started.set()
                # Mimic real worker cooperatively honoring cancel_event
                while not release.is_set() and not task.cancel_event.is_set():
                    time.sleep(0.02)
                if task.cancel_event.is_set():
                    task.status = "interrupted"
                    return
            task.status = "completed"
            task.stage = "completed"

        calls, activity = install_fake_worker(monkeypatch, behavior)
        return calls, activity, started, release

    def test_stop_one_device_keeps_other_device_queued_job_alive(self, monkeypatch):
        """Device A pressing stop must never kill device B's queued or waiting jobs."""
        calls, activity, started, release = self._make_blocker_env(monkeypatch)
        tm = TaskManager()

        t_a_block = tm.create_task("I2V", "blocker dev A", {}, device_id="dev_A")
        t_b_wait = tm.create_task("UPSCALER", "dev B waiting job", {}, device_id="dev_B")
        tm.start_background_task(t_a_block, {})
        assert started.wait(timeout=5)
        tm.start_background_task(t_b_wait, {})

        interrupted = tm.interrupt_device_tasks(device_id="dev_A", module="minimax")
        assert interrupted == [t_a_block.task_id]
        assert t_b_wait.status == "queued", "Device B queued job was friendly-fired by device A's stop!"

        release.set()
        assert wait_for_status([t_b_wait], statuses=("completed",))
        assert t_b_wait.task_id in calls and t_a_block.task_id in calls

    def test_stop_upscaler_module_spares_running_minimax_job(self, monkeypatch):
        """Same device: stopping queued upscaler work must leave the running minimax job untouched."""
        calls, activity, started, release = self._make_blocker_env(monkeypatch)
        tm = TaskManager()

        t_mm_block = tm.create_task("I2V", "blocker minimax", {}, device_id="dev_S")
        t_up_wait = tm.create_task("UPSCALER", "upscaler waiting", {}, device_id="dev_S")
        tm.start_background_task(t_mm_block, {})
        assert started.wait(timeout=5)
        tm.start_background_task(t_up_wait, {})

        interrupted = tm.interrupt_device_tasks(device_id="dev_S", module="upscaler")
        assert interrupted == [t_up_wait.task_id]
        assert not t_mm_block.cancel_event.is_set(), "Running minimax job received cancel signal!"

        release.set()
        assert wait_for_status([t_mm_block], statuses=("completed",))
        assert calls == [t_mm_block.task_id], "Interrupted upscaler task must never execute"
        with tm._lock:
            assert all(e[0] != t_up_wait.task_id for e in tm._dispatch_queue)

    def test_queue_continues_after_running_task_interrupted(self, monkeypatch):
        """Targeted-interrupting the RUNNING task must release the serial slot so the next queued job runs."""
        calls, activity, started, release = self._make_blocker_env(monkeypatch)
        tm = TaskManager()

        t_block = tm.create_task("I2V", "blocker", {}, device_id="dev_C")
        t_next = tm.create_task("UPSCALER", "next in line", {}, device_id="dev_C")
        tm.start_background_task(t_block, {})
        assert started.wait(timeout=5)
        tm.start_background_task(t_next, {})

        # Targeted single-task cancel (admin panel style): ONLY the blocker dies, the queue continues.
        assert tm.interrupt_task(t_block.task_id) is True
        assert wait_for_status([t_next], statuses=("completed",)), "Queue stalled after running task interrupted"
        assert calls == [t_block.task_id, t_next.task_id]
        assert t_next.status == "completed"
        assert t_block.status == "interrupted"

    def test_deleted_queued_task_never_executes(self, monkeypatch):
        """Admin delete_task on a still-queued task must purge it from the dispatch queue."""
        calls, activity, started, release = self._make_blocker_env(monkeypatch)
        tm = TaskManager()

        t_block = tm.create_task("I2V", "blocker", {}, device_id="dev_D")
        t_victim = tm.create_task("UPSCALER", "doomed task", {}, device_id="dev_D")
        tm.start_background_task(t_block, {})
        assert started.wait(timeout=5)
        tm.start_background_task(t_victim, {})

        assert tm.delete_task(t_victim.task_id, is_admin=True) is True
        release.set()
        assert wait_for_status([t_block], statuses=("completed",))
        time.sleep(0.2)  # give the dispatcher time to (mis)handle the stale queue entry
        assert t_victim.task_id not in calls, "Deleted queued task still got dispatched!"
        with tm._lock:
            assert all(e[0] != t_victim.task_id for e in tm._dispatch_queue), "Stale entry left in dispatch queue"

    def test_admin_global_interrupt_cancels_everything(self, monkeypatch):
        """device_id=None interrupt (admin kill-all) must purge queues across ALL devices/modules."""
        calls, activity, started, release = self._make_blocker_env(monkeypatch)
        tm = TaskManager()

        t_block = tm.create_task("I2V", "blocker dev A", {}, device_id="dev_A")
        t_a_wait = tm.create_task("UPSCALER", "dev A waiting", {}, device_id="dev_A")
        t_b_wait = tm.create_task("I2V", "dev B waiting", {}, device_id="dev_B")
        tm.start_background_task(t_block, {})
        assert started.wait(timeout=5)
        tm.start_background_task(t_a_wait, {})
        tm.start_background_task(t_b_wait, {})

        interrupted = tm.interrupt_device_tasks()
        assert set(interrupted) == {t_block.task_id, t_a_wait.task_id, t_b_wait.task_id}
        assert t_a_wait.status == "interrupted" and t_b_wait.status == "interrupted"
        release.set()
        time.sleep(0.4)
        assert calls == [t_block.task_id], "Only the already-running task may have started"
        with tm._lock:
            assert len(tm._dispatch_queue) == 0, "Kill-all left stale dispatch entries"


class TestRestartRecovery:
    def test_zombie_queued_task_demoted_on_restart(self):
        """A task that waited in the WebUI queue (never submitted) must not stay active after restart."""
        tm1 = TaskManager()
        t = tm1.create_task("UPSCALER", "queued but never submitted", {}, device_id="dev_zombie")
        assert t.status == "queued" and t.prompt_id is None
        tm1._save_history()

        tm2 = TaskManager()
        loaded = tm2.get_task(t.task_id)
        assert loaded is not None
        assert loaded.status == "interrupted", \
            f"Zombie queued task survived restart as '{loaded.status}' — device UI would hang on 排隊中 forever"
        assert "重啟" in loaded.message
        assert tm2.get_active_task_for_device("dev_zombie") is None
        assert tm2.get_latest_task_for_device("dev_zombie").status == "interrupted"

        # Demotion must have been persisted
        with open(tm_module_history(), "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert any(item["task_id"] == t.task_id and item["status"] == "interrupted" for item in saved)

    def test_submitted_running_task_survives_restart_for_sync_recovery(self):
        """Tasks that DID reach ComfyUI (prompt_id set) keep their state for sync_task_with_server."""
        tm1 = TaskManager()
        t = tm1.create_task("I2V", "was running at shutdown", {}, device_id="dev_restart")
        t.status = "running"
        t.prompt_id = "pid-survivor-001"
        tm1._save_history()

        tm2 = TaskManager()
        with tm2._lock:
            loaded = tm2._tasks[t.task_id]
        assert loaded.status == "running"
        assert loaded.prompt_id == "pid-survivor-001"

    def test_reloaded_history_is_never_auto_requeued(self, monkeypatch):
        """Restart must not resurrect old tasks into the dispatcher queue."""
        calls, activity = install_fake_worker(monkeypatch, lambda task: None)
        tm1 = TaskManager()
        t = tm1.create_task("I2V", "legacy queued task", {}, device_id="dev_requeue")
        t.prompt_id = "pid-legacy-001"  # submitted before shutdown -> NOT demoted, but must not re-run
        t.status = "queued"
        tm1._save_history()

        tm2 = TaskManager()
        time.sleep(0.3)
        assert tm2._dispatcher_started is False, "Dispatcher thread started without any new submission"
        assert calls == [], "Reloaded history task was wrongly requeued and re-executed!"


def tm_module_history():
    """Resolves the monkeypatched HISTORY_FILE path of the task_manager module."""
    import task_manager as tm_module
    return tm_module.HISTORY_FILE


class TestQueueStress:
    def test_pre_interrupted_task_is_never_enqueued(self, monkeypatch):
        """Race guard: a task interrupted before submission must be skipped entirely."""
        calls, _ = install_fake_worker(monkeypatch, lambda task: None)
        tm = TaskManager()
        t = tm.create_task("I2V", "cancelled before submit", {}, device_id="dev_race")
        t.cancel_event.set()
        t.status = "interrupted"

        tm.start_background_task(t, {})
        with tm._lock:
            assert len(tm._dispatch_queue) == 0
        assert tm._dispatcher_started is False
        time.sleep(0.2)
        assert calls == []

    def test_concurrent_submissions_run_once_serially(self, monkeypatch):
        """8 jobs from 2 devices/2 modules submitted from parallel threads:
        every job runs exactly once, never overlapping, and the queue never drops one."""
        def behavior(task):
            time.sleep(0.02)
            task.status = "completed"
            task.stage = "completed"

        calls, activity = install_fake_worker(monkeypatch, behavior)
        tm = TaskManager()

        jobs = []
        for i in range(4):
            jobs.append((tm.create_task("I2V", f"A job {i}", {}, device_id="dev_P"), {}, ))
            jobs.append((tm.create_task("UPSCALER", f"Q job {i}", {}, device_id="dev_Q"), {}, ))

        barrier = threading.Barrier(len(jobs))

        def submit(task):
            barrier.wait(timeout=10)
            tm.start_background_task(task, {})

        threads = [threading.Thread(target=submit, args=(t,)) for t, _ in jobs]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=10)

        tasks = [t for t, _ in jobs]
        assert wait_for_status(tasks, timeout=25), \
            f"Stress: unfinished tasks: {[(t.task_id[:20], t.status) for t in tasks if t.status != 'completed']}"
        assert sorted(calls) == sorted(t.task_id for t in tasks), "A task was lost or duplicated by the queue"
        assert activity["max"] == 1, "Serial execution violated under concurrent submissions"

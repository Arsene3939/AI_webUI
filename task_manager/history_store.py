"""
JSON history persistence for tasks (top-100, atomic write) plus the restart
zombie-queue guard (Spec 2026-10-31 task 2) that demotes never-submitted
queued/running records when they are reloaded.

NOTE: HISTORY_FILE is read through the task_manager package at call time
(_pkg.HISTORY_FILE) so tests can monkeypatch task_manager.HISTORY_FILE.
"""
import json
import os
import uuid
from typing import Dict

import task_manager as _pkg
from config import (
    normalize_quality_choice,
    normalize_aspect_ratio,
    normalize_sampler,
    normalize_scheduler,
)
from logger import get_logger

from .models import Task

logger = get_logger("TaskManager")


def load_history(tasks: Dict[str, Task]) -> int:
    """Populates `tasks` (task_id -> Task) from the history file.
    Returns the number of zombie records demoted to interrupted."""
    history_file = _pkg.HISTORY_FILE
    if not os.path.exists(history_file):
        return 0
    demoted = 0
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                t = Task.from_dict(item)
                if t.params:
                    if "quality_level" in t.params:
                        t.params["quality_level"] = normalize_quality_choice(t.params["quality_level"])
                    if "aspect_ratio" in t.params:
                        t.params["aspect_ratio"] = normalize_aspect_ratio(t.params["aspect_ratio"])
                    if "sampler" in t.params:
                        t.params["sampler"] = normalize_sampler(t.params["sampler"])
                    if "scheduler" in t.params:
                        t.params["scheduler"] = normalize_scheduler(t.params["scheduler"])
                # Zombie-queue guard: tasks marked queued/running that were never
                # submitted to ComfyUI (prompt_id is None) were sitting in the WebUI
                # dispatch queue when the server stopped. Nothing can resume them, and
                # leaving them "active" would pin the device UI on 排隊中 forever.
                if t.status in ("queued", "running") and not t.prompt_id:
                    t.status = "interrupted"
                    t.stage = "interrupted"
                    t.message = "⚠️ 工作已在排队时因伺服器重啟而遺失，請重新提交"
                    demoted += 1
                tasks[t.task_id] = t
        logger.info("Loaded %d task(s) from history file: %s", len(tasks), history_file)
        if demoted:
            logger.warning("Demoted %d never-submitted queued/running task(s) to interrupted after restart.", demoted)
    except Exception as e:
        logger.warning("Failed to load task history: %s", e)
    return demoted


def save_history(tasks: Dict[str, Task], lock) -> None:
    """Atomically persists the newest 100 task records to HISTORY_FILE."""
    tmp_file = None
    try:
        items = []
        with lock:
            for t in sorted(tasks.values(), key=lambda x: x.created_at, reverse=True)[:100]:
                items.append(t.to_dict())
        tmp_file = f"{_pkg.HISTORY_FILE}.{uuid.uuid4().hex[:6]}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, _pkg.HISTORY_FILE)
    except Exception:
        if tmp_file is not None and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass

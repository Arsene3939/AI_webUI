"""
Upload archiving: copies user-uploaded media (first frames, reference videos...)
into INPUTS_ARCHIVE_DIR keyed by task id, so 「恢复上次输入」 keeps working long
after the temp upload is gone; and removes those archives when the task is deleted.

NOTE: INPUTS_ARCHIVE_DIR is read through the task_manager package at call time
(_pkg.INPUTS_ARCHIVE_DIR) for test monkeypatching.
"""
import os
import shutil
from typing import Optional

import task_manager as _pkg
from utils.logger import get_logger

logger = get_logger("TaskManager")


def archive_file(file_path: Optional[str], task_id: str, prefix: str) -> Optional[str]:
    """Copies an uploaded file into the per-task archive; returns the archived path."""
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        ext = os.path.splitext(file_path)[1]
        dest_name = f"{task_id}_{prefix}{ext}"
        dest_path = os.path.join(_pkg.INPUTS_ARCHIVE_DIR, dest_name)
        shutil.copy2(file_path, dest_path)
        return dest_path
    except Exception:
        return file_path


def remove_task_archives(task_id: str) -> None:
    """Removes every archived upload belonging to the given task id."""
    try:
        prefix = f"{task_id}_"
        for fname in os.listdir(_pkg.INPUTS_ARCHIVE_DIR):
            if fname.startswith(prefix):
                try:
                    os.remove(os.path.join(_pkg.INPUTS_ARCHIVE_DIR, fname))
                except Exception:
                    pass
    except Exception:
        pass

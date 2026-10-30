"""
One-shot E2E residue cleaner (Spec 2026-10-31 task 4).

The e2e runners now self-clean after every run. This script exists to sweep leftovers
produced by OLDER e2e runs that predate the auto-cleanup.

What it removes:
  - Media files whose name contains "_e2e_" in outputs/ and outputs/frames/
    (minimax_e2e_*.mp4 / upscale_e2e_*.mp4 dummy videos)
  - task_history.json records whose output video is an e2e dummy file, or whose
    device_id matches an e2e runner device (dev_user_/dev_cross_/dev_upscaler_/
    dev_stranger_/dev_legacy_/dev_e2e_ prefixes)
  - outputs/inputs/ archived uploads belonging to those purged task records

What it NEVER removes: real user videos/records, admin_ips.json, webui.log.

NOTE: run this while the WebUI server is STOPPED — otherwise the live in-memory
task manager may rewrite the history file and undo the purge.
"""
import os
import re
import json
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")

MEDIA_EXTS = (".mp4", ".webm", ".mkv", ".png")
E2E_DEVICE_RE = re.compile(r"^dev_(user|cross|upscaler|stranger|legacy|e2e)_")


def main() -> int:
    history_file = os.path.join(OUTPUT_DIR, "task_history.json")
    inputs_dir = os.path.join(OUTPUT_DIR, "inputs")
    frames_dir = os.path.join(OUTPUT_DIR, "frames")

    removed_records = 0
    removed_files = 0
    doomed_task_ids = []

    # --- 1. Purge e2e records from the task history (and their videos) ---
    data = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[ERROR] Cannot read {history_file}: {e}")
            return 1

    kept = []
    for item in data:
        video = item.get("video_path") or ""
        device = item.get("device_id") or ""
        is_e2e = "_e2e_" in os.path.basename(video) or bool(E2E_DEVICE_RE.match(device))
        if is_e2e:
            removed_records += 1
            if item.get("task_id"):
                doomed_task_ids.append(item["task_id"])
            if video and os.path.exists(video):
                try:
                    os.remove(video)
                    removed_files += 1
                except Exception:
                    pass
        else:
            kept.append(item)

    if removed_records:
        tmp_file = history_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(kept, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, history_file)

    # --- 2. Sweep e2e-named media files left in outputs/ and outputs/frames/ ---
    for scan_dir in (OUTPUT_DIR, frames_dir):
        if os.path.isdir(scan_dir):
            for fname in os.listdir(scan_dir):
                if "_e2e_" in fname and fname.lower().endswith(MEDIA_EXTS):
                    try:
                        os.remove(os.path.join(scan_dir, fname))
                        removed_files += 1
                    except Exception:
                        pass

    # --- 3. Remove archived input media under outputs/inputs/ ---
    # Archives are named <task_id>_<field>.<ext> (task_id = task_<epoch>_<hex>, i.e. the
    # first 3 underscore-joined segments). An archive is residue when its task id belongs
    # to a purged record, or when no remaining history record references it anymore.
    if os.path.isdir(inputs_dir):
        live_prefixes = {f"{item['task_id']}_" for item in kept if item.get("task_id")}
        doomed_prefixes = {f"{tid}_" for tid in doomed_task_ids}
        for fname in os.listdir(inputs_dir):
            parts = fname.split("_")
            task_prefix = ("_".join(parts[:3]) + "_") if len(parts) >= 3 else ""
            doomed = any(fname.startswith(p) for p in doomed_prefixes)
            orphan = bool(task_prefix) and task_prefix not in live_prefixes
            if doomed or orphan:
                try:
                    os.remove(os.path.join(inputs_dir, fname))
                    removed_files += 1
                except Exception:
                    pass

    print(f"[clean_e2e_leftovers] history records purged: {removed_records}")
    print(f"[clean_e2e_leftovers] files deleted: {removed_files}")
    print(f"[clean_e2e_leftovers] remaining history records: {len(kept)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

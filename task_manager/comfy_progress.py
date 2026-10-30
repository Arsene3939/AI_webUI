"""
ComfyUI job lifecycle for a single task (Spec 2026-10-31 task-manager modularization):
- submit the workflow graph (queue_prompt)
- websocket listener pushing real-time step/node progress onto the Task
- the 0.5s polling loop that derives stage/message from /history + /queue,
  downloads the finished output, and the backend-liveness watchdog
  (Spec 2026-10-31 task 2: consecutive dead probes abort the task as interrupted)

queue_prompt / download_output_file are resolved through the task_manager facade at
call time (_pkg.*) so tests patching task_manager.queue_prompt keep intercepting here.
"""
import asyncio
import json
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional

import requests
import websockets

import task_manager as _pkg
from utils.logger import get_logger

from .models import Task

logger = get_logger("TaskManager")

BACKEND_FAILURE_LIMIT = 10  # consecutive polls where BOTH history and queue requests fail


def ws_listener(
    ws_url: str,
    client_id: str,
    prompt_id: str,
    task: Task,
    prompt_graph: Optional[Dict[str, Any]],
    stop_event: threading.Event,
):
    """Listens to ComfyUI websocket for real-time progress steps and executing node names."""
    async def listen():
        full_ws = f"{ws_url}/ws?clientId={client_id}"
        try:
            async with websockets.connect(full_ws, ping_timeout=20, close_timeout=5) as ws:
                logger.debug("[Task %s] WebSocket connected to %s", task.task_id, full_ws)
                while not stop_event.is_set():
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    if isinstance(msg, str):
                        event = json.loads(msg)
                        etype = event.get("type")
                        data = event.get("data", {})
                        if etype == "progress":
                            p_id = data.get("prompt_id")
                            if p_id and p_id != prompt_id:
                                continue
                            v = data.get("value", 0)
                            m = data.get("max", 1)
                            if m > 0:
                                task.step = v
                                task.total_steps = m
                                task.progress = min(0.95, max(0.15, 0.15 + (v / m) * 0.77))
                                if v < m:
                                    task.stage = "sampling"
                                else:
                                    task.stage = "postprocessing"
                        elif etype == "executing":
                            node = data.get("node")
                            p_id = data.get("prompt_id")
                            if p_id == prompt_id:
                                if node is None:
                                    task.stage = "completed"
                                else:
                                    task.current_node = str(node)
                                    node_key = str(node)
                                    node_info = prompt_graph.get(node_key, {}) if prompt_graph else {}
                                    class_type = str(node_info.get("class_type", "")).lower()
                                    node_str = f"{node_key} {class_type}".lower()
                                    if any(k in node_str for k in ["vae_decode", "vaedecode", "create_video", "createvideo", "save_video", "savevideo"]):
                                        task.stage = "postprocessing"
                                    elif any(k in node_str for k in ["sampler", "sampling", "ksampler"]):
                                        task.stage = "sampling"
                                        if task.total_steps > 0:
                                            task.message = f"⚡ 影片生成中: {task.step}/{task.total_steps} 步"
                                        else:
                                            task.message = "⚡ 影片生成中..."
                                    elif task.stage not in ("sampling", "postprocessing"):
                                        task.stage = "preprocessing"
        except Exception as e:
            logger.debug("[Task %s] WebSocket closed or unreachable: %s", task.task_id, e)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(listen())
    except Exception:
        pass
    finally:
        loop.close()


def monitor_worker(
    task: Task,
    prompt_graph: Dict[str, Any],
    server_url: str,
    save: Callable[[], None],
):
    """Submits the task's workflow to ComfyUI then polls it to completion/failure."""
    if task.cancel_event.is_set() or task.status == "interrupted":
        logger.info("[Task %s] Interrupted before starting worker.", task.task_id)
        return

    task.status = "running"
    task.stage = "preprocessing"
    task.message = "⚡ 前處理中：正在提交任務至後端..."
    task.progress = 0.08
    logger.info("[Task %s] Submitting workflow graph to ComfyUI (%s)...", task.task_id, server_url)

    client_id = str(uuid.uuid4())
    try:
        if task.cancel_event.is_set() or task.status == "interrupted":
            logger.info("[Task %s] Interrupted before queueing prompt.", task.task_id)
            return
        prompt_id = _pkg.queue_prompt(prompt_graph, client_id, server_url)
        task.prompt_id = prompt_id
        task.status = "queued"
        task.stage = "pending"
        task.message = "⏳ 排隊中..."
        task.progress = 0.15
        logger.info("[Task %s] Prompt queued successfully! Assigned ComfyUI prompt_id: %s", task.task_id, prompt_id)
    except Exception as e:
        if task.cancel_event.is_set() or task.status == "interrupted":
            logger.info("[Task %s] Interrupted during prompt submission: %s", task.task_id, e)
            return
        task.status = "failed"
        task.stage = "failed"
        task.message = f"❌ 提交失敗: {str(e)}"
        save()
        logger.error("[Task %s] Failed to queue prompt to ComfyUI: %s", task.task_id, e)
        return

    # Start WebSocket progress listener for real-time steps
    stop_ws = threading.Event()
    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_thread = threading.Thread(
        target=ws_listener,
        args=(ws_url, client_id, task.prompt_id, task, prompt_graph, stop_ws),
        daemon=True,
    )
    ws_thread.start()

    start_time = time.time()
    last_logged_step = -1
    last_logged_stage = task.stage
    backend_failures = 0

    while True:
        if task.cancel_event.is_set() or task.status == "interrupted":
            task.status = "interrupted"
            task.stage = "interrupted"
            task.message = "⚠️ 任務已中斷"
            stop_ws.set()
            save()
            logger.info("[Task %s] Interrupted.", task.task_id)
            return

        elapsed = round(time.time() - start_time, 1)
        task.elapsed = elapsed

        # Format human-readable elapsed time (seconds, minutes, or hours)
        hrs = int(elapsed // 3600)
        mins = int((elapsed % 3600) // 60)
        secs = int(elapsed % 60)
        if hrs > 0:
            time_str = f"{hrs}小時{mins}分{secs}秒"
        elif mins > 0:
            time_str = f"{mins}分{secs}秒"
        else:
            time_str = f"{secs}秒"

        # Log stage changes
        if task.stage != last_logged_stage:
            logger.info("[Task %s] Stage changed -> %s (%s)", task.task_id, task.stage, task.message)
            last_logged_stage = task.stage

        # Log step progress
        if task.stage == "sampling" and task.step != last_logged_step and task.total_steps > 0:
            logger.info("[Task %s] Sampling: %d/%d steps (%d%%, elapsed: %s)",
                        task.task_id, task.step, task.total_steps, int(task.progress * 100), time_str)
            last_logged_step = task.step

        history_ok = False
        queue_ok = False

        # 1. Check if finished or failed in ComfyUI history
        try:
            h_resp = requests.get(f"{server_url}/history/{task.prompt_id}", timeout=5)
            history_ok = True
            if h_resp.status_code == 200:
                history = h_resp.json().get(task.prompt_id, {})
                outputs = history.get("outputs", {})
                if outputs:
                    for nid, nout in outputs.items():
                        items = nout.get("videos") or nout.get("gifs") or nout.get("images") or []
                        for it in items:
                            fn = it.get("filename")
                            if fn and (fn.endswith(".mp4") or fn.endswith(".webm") or fn.endswith(".mkv")):
                                subfolder = it.get("subfolder", "")
                                folder_type = it.get("type", "output")
                                task.stage = "postprocessing"
                                task.message = f"⚡ 後處理中：正在儲存影片... (耗時 {time_str})"
                                task.progress = 0.95
                                logger.info("[Task %s] Output detected in ComfyUI: %s. Downloading...", task.task_id, fn)
                                local_path = _pkg.download_output_file(fn, subfolder, folder_type, server_url)
                                task.video_path = local_path
                                task.status = "completed"
                                task.stage = "completed"
                                task.progress = 1.0
                                task.completed_at = time.time()
                                task.message = f"✅ 影片生成完成！耗時 {time_str}"
                                stop_ws.set()
                                save()
                                logger.info("[Task %s] Completed! Saved to: %s (Total time: %s)", task.task_id, local_path, time_str)
                                return

                status_info = history.get("status", {})
                if status_info.get("status_str") == "error":
                    task.status = "failed"
                    task.stage = "failed"
                    task.message = "❌ 生成失敗，請查看後端錯誤記錄。"
                    stop_ws.set()
                    save()
                    logger.error("[Task %s] ComfyUI reported execution error: %s", task.task_id, status_info)
                    return
        except Exception as e:
            logger.debug("[Task %s] History check exception: %s", task.task_id, e)

        # 2. Check queue position / running state
        try:
            q_resp = requests.get(f"{server_url}/queue", timeout=5)
            queue_ok = True
            if q_resp.status_code == 200:
                q_data = q_resp.json()
                running = [item[1] for item in q_data.get("queue_running", [])]
                pending = [item[1] for item in q_data.get("queue_pending", [])]

                if task.total_steps > 0 and task.step >= task.total_steps:
                    task.status = "running"
                    task.stage = "postprocessing"
                    task.message = f"⚡ 後處理中：正在合成影片... (耗時 {time_str})"
                elif task.stage == "postprocessing":
                    task.status = "running"
                    task.message = f"⚡ 後處理中：正在合成影片... (耗時 {time_str})"
                elif task.stage == "sampling" or (task.total_steps > 0 and task.step > 0):
                    task.status = "running"
                    task.stage = "sampling"
                    if task.total_steps > 0:
                        task.message = f"⚡ 影片生成中: {task.step}/{task.total_steps} 步 (耗時 {time_str})"
                    else:
                        task.message = f"⚡ 影片生成中... (耗時 {time_str})"
                elif task.prompt_id in running:
                    task.status = "running"
                    task.stage = "preprocessing"
                    task.progress = min(0.95, 0.25 + (elapsed / 1800.0) * 0.70)
                    task.message = f"⚡ 前處理中：正在載入模型... (耗時 {time_str})"
                elif task.prompt_id in pending:
                    task.status = "queued"
                    task.stage = "pending"
                    task.progress = 0.18
                    task.message = f"⏳ 排隊中... (已等待 {time_str})"
        except Exception as e:
            logger.debug("[Task %s] Queue poll exception: %s", task.task_id, e)

        # 3. Backend-liveness watchdog: if the ComfyUI server stops answering every probe
        #    (e.g. its terminal was killed mid-generation), abort the task instead of
        #    spinning forever, and persist the record so it shows up in history.
        if not history_ok and not queue_ok:
            backend_failures += 1
            if backend_failures >= BACKEND_FAILURE_LIMIT:
                task.status = "interrupted"
                task.stage = "interrupted"
                task.message = "⚠️ 後端模型已離線，任務已中止（請確認後端後重新提交）"
                stop_ws.set()
                save()
                logger.error(
                    "[Task %s] Backend unreachable for %d consecutive polls at step %d/%d "
                    "(elapsed: %s) — aborting task as interrupted.",
                    task.task_id, backend_failures, task.step, task.total_steps, time_str,
                )
                return
        else:
            backend_failures = 0

        time.sleep(0.5)

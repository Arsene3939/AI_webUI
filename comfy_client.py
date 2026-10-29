"""
ComfyUI API client for managing uploads, prompt submission, WebSocket progress,
and output retrieval.
"""
import os
import json
import uuid
import time
import subprocess
import requests
import asyncio
import websockets
from typing import Optional, Tuple, Generator, Dict, Any
from config import COMFY_SERVER_URL, COMFY_WS_URL, OUTPUT_DIR
from logger import get_logger

logger = get_logger("ComfyClient")

COMFY_ROOT = r"F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
COMFY_PYTHON = r"F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"

_COMFY_PROCESS: Optional[subprocess.Popen] = None


def check_server(server_url: Optional[str] = None) -> Tuple[bool, str]:
    """Check if the ComfyUI server is reachable."""
    server_url = server_url or COMFY_SERVER_URL
    try:
        resp = requests.get(f"{server_url}/system_stats", timeout=3)
        if resp.status_code == 200:
            return True, "🟢 ComfyUI 後端運作中"
        return False, f"🔴 ComfyUI 回應異常 ({resp.status_code})"
    except Exception:
        return False, "🔴 ComfyUI 未連線 (離線中)"


def start_comfyui_backend(server_url: Optional[str] = None) -> Tuple[bool, str]:
    """Starts the ComfyUI backend server in an independent process if not running."""
    global _COMFY_PROCESS
    server_url = server_url or COMFY_SERVER_URL
    is_ok, _ = check_server(server_url)
    if is_ok:
        logger.info("ComfyUI backend already running at %s", server_url)
        return True, "🟢 後端已經在運作中，無須重複啟動"

    main_py = os.path.join(COMFY_ROOT, "main.py")
    if not os.path.exists(main_py):
        logger.error("ComfyUI main script missing: %s", main_py)
        return False, f"❌ 找不到 ComfyUI 核心主程式: {main_py}"
    if not os.path.exists(COMFY_PYTHON):
        logger.error("ComfyUI Python venv missing: %s", COMFY_PYTHON)
        return False, f"❌ 找不到 Python 解譯器: {COMFY_PYTHON}"

    cmd = [
        COMFY_PYTHON,
        main_py,
        "--listen", "0.0.0.0",
        "--port", "8188",
        "--output-directory", r"F:\program_file\Comfy-Desktop\ComfyUI-Shared\output",
        "--input-directory", r"F:\program_file\Comfy-Desktop\ComfyUI-Shared\input",
    ]

    try:
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
        logger.info("Spawning ComfyUI backend process: %s", " ".join(cmd))
        _COMFY_PROCESS = subprocess.Popen(cmd, cwd=COMFY_ROOT, creationflags=flags)
    except Exception as e:
        logger.error("Failed to spawn ComfyUI process: %s", e)
        return False, f"❌ 啟動進程失敗: {str(e)}"

    # Wait and verify up to 15 seconds
    for _ in range(15):
        time.sleep(1)
        ok, _ = check_server(server_url)
        if ok:
            logger.info("ComfyUI backend verified online at %s", server_url)
            return True, "🟢 後端已成功啟動並就緒！"

    logger.info("ComfyUI start command sent; still loading in background")
    return True, "⏳ 已送出啟動指令，正在背景載入中，約需 5~10 秒..."


def stop_comfyui_backend(server_url: Optional[str] = None) -> Tuple[bool, str]:
    """Stops the ComfyUI backend process."""
    global _COMFY_PROCESS
    server_url = server_url or COMFY_SERVER_URL
    is_ok, _ = check_server(server_url)
    if not is_ok and _COMFY_PROCESS is None:
        logger.info("ComfyUI backend already offline")
        return False, "🔴 後端本來就未在運作中。"

    logger.info("Stopping ComfyUI backend (server_url: %s)...", server_url)
    # 1. Terminate tracked subprocess if available
    if _COMFY_PROCESS is not None:
        try:
            _COMFY_PROCESS.terminate()
            _COMFY_PROCESS.kill()
        except Exception:
            pass
        _COMFY_PROCESS = None

    # 2. Terminate any process bound to the server port (default 8188)
    try:
        port = "8188"
        if ":" in server_url:
            port = server_url.split(":")[-1].replace("/", "")

        # Look up owning PID via PowerShell on Windows
        cmd = f'powershell -Command "(Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue).OwningProcess"'
        out = subprocess.check_output(cmd, shell=True).decode().strip()
        for line in out.splitlines():
            pid = line.strip()
            if pid and pid.isdigit() and int(pid) > 0:
                logger.info("Terminating process PID %s on port %s", pid, port)
                subprocess.run(f"taskkill /F /PID {pid} /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.warning("Error stopping port processes: %s", e)

    time.sleep(1)
    is_ok, _ = check_server(server_url)
    if not is_ok:
        logger.info("ComfyUI backend stopped successfully.")
        return True, "🛑 後端已成功關閉。"
    else:
        logger.warning("ComfyUI backend failed to terminate completely.")
        return False, "⚠️ 嘗試關閉後端失敗，請手動檢查終端機。"


def upload_media_file(file_path: str, server_url: Optional[str] = None) -> str:
    """Uploads an image, video, or audio file to ComfyUI's input directory."""
    server_url = server_url or COMFY_SERVER_URL
    if not file_path or not os.path.exists(file_path):
        logger.error("Upload failed: file not found: %s", file_path)
        raise FileNotFoundError(f"檔案不存在: {file_path}")

    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    url = f"{server_url}/upload/image"
    logger.info("Uploading media file '%s' (%d bytes) to %s...", filename, file_size, url)

    with open(file_path, "rb") as f:
        files = {"image": (filename, f)}
        data = {"overwrite": "true", "type": "input"}
        response = requests.post(url, files=files, data=data, timeout=60)
        response.raise_for_status()
        result = response.json()
        uploaded_name = result.get("name", filename)
        logger.info("Media file uploaded successfully as '%s'", uploaded_name)
        return uploaded_name


def queue_prompt(prompt_graph: Dict[str, Any], client_id: str, server_url: Optional[str] = None) -> str:
    """Submits a prompt graph to ComfyUI."""
    server_url = server_url or COMFY_SERVER_URL
    url = f"{server_url}/prompt"
    payload = {"prompt": prompt_graph, "client_id": client_id}
    logger.info("Submitting prompt graph (%d nodes, client_id: %s) to %s...", len(prompt_graph), client_id[:8], url)
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "prompt_id" not in data:
        error_msg = data.get("error", "未知錯誤")
        node_errors = data.get("node_errors", {})
        logger.error("ComfyUI rejected prompt execution: %s (%s)", error_msg, node_errors)
        raise RuntimeError(f"ComfyUI 拒絕執行: {error_msg} ({json.dumps(node_errors, ensure_ascii=False)})")
    prompt_id = data["prompt_id"]
    logger.info("ComfyUI accepted prompt! Assigned prompt_id: %s", prompt_id)
    return prompt_id


def interrupt_execution(prompt_id: Optional[str] = None, server_url: Optional[str] = None) -> bool:
    """
    Interrupts current execution on ComfyUI and dequeues the given prompt_id if pending.
    Returns True if an interrupt or delete request succeeded, False otherwise.
    """
    server_url = server_url or COMFY_SERVER_URL
    success = False

    # 1. If prompt_id is specified, dequeue from pending queue or cancel job
    if prompt_id:
        # Try modern job cancel endpoint
        try:
            cancel_resp = requests.post(f"{server_url}/api/jobs/{prompt_id}/cancel", timeout=3)
            if cancel_resp.status_code == 200:
                logger.info("ComfyUI cancelled job %s via /api/jobs/{id}/cancel", prompt_id)
                success = True
        except Exception:
            pass

        # Dequeue from pending queue
        try:
            del_resp = requests.post(f"{server_url}/queue", json={"delete": [prompt_id]}, timeout=3)
            if del_resp.status_code == 200:
                logger.info("ComfyUI deleted prompt %s from queue", prompt_id)
                success = True
        except Exception:
            pass

        # Targeted interrupt
        try:
            int_resp = requests.post(f"{server_url}/interrupt", json={"prompt_id": prompt_id}, timeout=3)
            if int_resp.status_code == 200:
                logger.info("ComfyUI interrupted prompt %s via /interrupt", prompt_id)
                success = True
        except Exception:
            pass

    # 2. General interrupt for any currently executing prompt
    try:
        gen_resp = requests.post(f"{server_url}/interrupt", json={}, timeout=3)
        if gen_resp.status_code == 200:
            logger.info("ComfyUI general /interrupt sent successfully")
            success = True
    except Exception as e:
        logger.debug("ComfyUI general interrupt exception: %s", e)

    return success


def download_output_file(
    filename: str,
    subfolder: str = "",
    folder_type: str = "output",
    server_url: Optional[str] = None,
) -> str:
    """Downloads an output file from ComfyUI to local output directory."""
    server_url = server_url or COMFY_SERVER_URL
    params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    view_url = f"{server_url}/view"
    logger.info("Downloading output file '%s' from %s...", filename, view_url)
    resp = requests.get(view_url, params=params, stream=True, timeout=120)
    resp.raise_for_status()

    local_filename = f"{int(time.time())}_{filename}"
    local_path = os.path.join(OUTPUT_DIR, local_filename)

    with open(local_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    file_size = os.path.getsize(local_path)
    logger.info("Downloaded output file saved to %s (%d bytes)", local_path, file_size)
    return local_path


async def _listen_websocket_progress(
    ws_url: str,
    client_id: str,
    prompt_id: str,
    progress_queue: asyncio.Queue,
):
    """Listens to ComfyUI WebSocket messages for execution progress."""
    full_ws_url = f"{ws_url}/ws?clientId={client_id}"
    try:
        async with websockets.connect(full_ws_url, max_size=100 * 1024 * 1024) as ws:
            while True:
                msg = await ws.recv()
                if isinstance(msg, str):
                    event = json.loads(msg)
                    event_type = event.get("type")
                    data = event.get("data", {})

                    if event_type == "status":
                        exec_info = data.get("status", {}).get("exec_info", {})
                        queue_remaining = exec_info.get("queue_remaining", 0)
                        await progress_queue.put({"type": "queue", "remaining": queue_remaining})

                    elif event_type == "progress":
                        val = data.get("value", 0)
                        max_val = data.get("max", 1)
                        node = data.get("node")
                        await progress_queue.put({"type": "progress", "val": val, "max": max_val, "node": node})

                    elif event_type == "executing":
                        node = data.get("node")
                        p_id = data.get("prompt_id")
                        if node is None and p_id == prompt_id:
                            # Prompt execution finished!
                            await progress_queue.put({"type": "done"})
                            break
                        else:
                            await progress_queue.put({"type": "executing", "node": node})

                    elif event_type == "executed":
                        p_id = data.get("prompt_id")
                        if p_id == prompt_id:
                            output_data = data.get("output", {})
                            await progress_queue.put({"type": "executed", "output": output_data})
    except Exception as e:
        await progress_queue.put({"type": "ws_error", "error": str(e)})


def run_and_monitor(
    prompt_graph: Dict[str, Any],
    server_url: str = COMFY_SERVER_URL,
    ws_url: str = COMFY_WS_URL,
) -> Generator[Tuple[float, str, Optional[str]], None, None]:
    """
    Submits workflow and yields (progress_percent [0.0 - 1.0], status_text, video_path).
    Compatible with Gradio generator functions.
    """
    is_ok, msg = check_server(server_url)
    if not is_ok:
        yield 0.0, f"❌ {msg}", None
        return

    client_id = str(uuid.uuid4())
    yield 0.05, "📤 正在提交任務...", None

    try:
        prompt_id = queue_prompt(prompt_graph, client_id, server_url)
    except Exception as e:
        yield 0.0, f"❌ 提交失敗: {str(e)}", None
        return

    yield 0.1, f"⏳ 已加入排隊隊列 (ID: {prompt_id[:8]}...)", None

    # Track progress via polling & history as fallback
    start_time = time.time()
    video_path = None
    last_step = 0
    total_steps = 20

    while True:
        # Check history to see if completed
        try:
            h_resp = requests.get(f"{server_url}/history/{prompt_id}", timeout=5)
            if h_resp.status_code == 200:
                history = h_resp.json().get(prompt_id, {})
                outputs = history.get("outputs", {})
                if outputs:
                    # Look for video output in any node
                    for nid, nout in outputs.items():
                        # SaveVideo or VHS outputs
                        video_items = nout.get("videos") or nout.get("gifs") or nout.get("images") or []
                        for item in video_items:
                            filename = item.get("filename")
                            if filename and (filename.endswith(".mp4") or filename.endswith(".webm") or filename.endswith(".mkv")):
                                subfolder = item.get("subfolder", "")
                                folder_type = item.get("type", "output")
                                yield 0.95, "📥 正在儲存影片...", None
                                video_path = download_output_file(filename, subfolder, folder_type, server_url)
                                total_elapsed = round(time.time() - start_time, 1)
                                yield 1.0, f"✅ 影片生成成功！耗時 {total_elapsed} 秒", video_path
                                return
        except Exception:
            pass

        # Check prompt queue status
        try:
            q_resp = requests.get(f"{server_url}/queue", timeout=5)
            if q_resp.status_code == 200:
                q_data = q_resp.json()
                running = [item[1] for item in q_data.get("queue_running", [])]
                pending = [item[1] for item in q_data.get("queue_pending", [])]

                elapsed = int(time.time() - start_time)
                hrs = int(elapsed // 3600)
                mins = int((elapsed % 3600) // 60)
                secs = int(elapsed % 60)
                if hrs > 0:
                    time_str = f"{hrs}小時{mins}分{secs}秒"
                elif mins > 0:
                    time_str = f"{mins}分{secs}秒"
                else:
                    time_str = f"{secs}秒"

                if prompt_id in running:
                    yield 0.3 + min(0.65, elapsed / 1800.0), f"⚡ 影片生成中... (耗時 {time_str})", None
                elif prompt_id in pending:
                    yield 0.15, f"⏳ 排隊中... (已等待 {time_str})", None
                else:
                    time.sleep(1)
        except Exception:
            pass

        time.sleep(2)

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

COMFY_ROOT = r"F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
COMFY_PYTHON = r"F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"

_COMFY_PROCESS: Optional[subprocess.Popen] = None


def check_server(server_url: str = COMFY_SERVER_URL) -> Tuple[bool, str]:
    """Check if the ComfyUI server is reachable."""
    try:
        resp = requests.get(f"{server_url}/system_stats", timeout=3)
        if resp.status_code == 200:
            return True, "🟢 ComfyUI 後端運作中"
        return False, f"🔴 ComfyUI 回應異常 ({resp.status_code})"
    except Exception:
        return False, "🔴 ComfyUI 未連線 (離線中)"


def start_comfyui_backend(server_url: str = COMFY_SERVER_URL) -> Tuple[bool, str]:
    """Starts the ComfyUI backend server in an independent process if not running."""
    global _COMFY_PROCESS
    is_ok, _ = check_server(server_url)
    if is_ok:
        return True, "🟢 ComfyUI 後端已經在運作中，無須重複啟動！"

    main_py = os.path.join(COMFY_ROOT, "main.py")
    if not os.path.exists(main_py):
        return False, f"❌ 找不到 ComfyUI 核心主程式: {main_py}"
    if not os.path.exists(COMFY_PYTHON):
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
        _COMFY_PROCESS = subprocess.Popen(cmd, cwd=COMFY_ROOT, creationflags=flags)
    except Exception as e:
        return False, f"❌ 啟動進程失敗: {str(e)}"

    # Wait and verify up to 15 seconds
    for _ in range(15):
        time.sleep(1)
        ok, _ = check_server(server_url)
        if ok:
            return True, "🟢 ComfyUI 後端已成功啟動並就緒！"

    return True, "⏳ 已送出啟動指令，ComfyUI 正在背景載入中，約需 5~10 秒..."


def stop_comfyui_backend(server_url: str = COMFY_SERVER_URL) -> Tuple[bool, str]:
    """Stops the ComfyUI backend process."""
    global _COMFY_PROCESS
    is_ok, _ = check_server(server_url)
    if not is_ok and _COMFY_PROCESS is None:
        return False, "🔴 ComfyUI 本來就未在運作中。"

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
                subprocess.run(f"taskkill /F /PID {pid} /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    time.sleep(1)
    is_ok, _ = check_server(server_url)
    if not is_ok:
        return True, "🛑 ComfyUI 後端已成功關閉。"
    else:
        return False, "⚠️ 嘗試關閉 ComfyUI 後端失敗，請手動檢查終端機。"


def upload_media_file(file_path: str, server_url: str = COMFY_SERVER_URL) -> str:
    """Uploads an image, video, or audio file to ComfyUI's input directory."""
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"檔案不存在: {file_path}")

    filename = os.path.basename(file_path)
    url = f"{server_url}/upload/image"

    with open(file_path, "rb") as f:
        files = {"image": (filename, f)}
        data = {"overwrite": "true", "type": "input"}
        response = requests.post(url, files=files, data=data, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result.get("name", filename)


def queue_prompt(prompt_graph: Dict[str, Any], client_id: str, server_url: str = COMFY_SERVER_URL) -> str:
    """Submits a prompt graph to ComfyUI."""
    url = f"{server_url}/prompt"
    payload = {"prompt": prompt_graph, "client_id": client_id}
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "prompt_id" not in data:
        error_msg = data.get("error", "未知錯誤")
        node_errors = data.get("node_errors", {})
        raise RuntimeError(f"ComfyUI 拒絕執行: {error_msg} ({json.dumps(node_errors, ensure_ascii=False)})")
    return data["prompt_id"]


def download_output_file(
    filename: str,
    subfolder: str = "",
    folder_type: str = "output",
    server_url: str = COMFY_SERVER_URL,
) -> str:
    """Downloads an output file from ComfyUI to local output directory."""
    params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    resp = requests.get(f"{server_url}/view", params=params, stream=True, timeout=120)
    resp.raise_for_status()

    local_filename = f"{int(time.time())}_{filename}"
    local_path = os.path.join(OUTPUT_DIR, local_filename)

    with open(local_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

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
    yield 0.05, "📤 正在向 ComfyUI 提交工作流佇列...", None

    try:
        prompt_id = queue_prompt(prompt_graph, client_id, server_url)
    except Exception as e:
        yield 0.0, f"❌ 提交失敗: {str(e)}", None
        return

    yield 0.1, f"⏳ 工作流已加入佇列 (Prompt ID: {prompt_id[:8]}...)", None

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
                                yield 0.95, "📥 影片生成完畢，正在下載至 WebUI...", None
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
                    yield 0.3 + min(0.65, elapsed / 1800.0), f"⚡ MiniMax-H3 正在進行音視訊聯合去噪擴散運算... (已耗時 {time_str})", None
                elif prompt_id in pending:
                    yield 0.15, f"⏳ 排隊等待執行中... (已等待 {time_str})", None
                else:
                    time.sleep(1)
        except Exception:
            pass

        time.sleep(2)

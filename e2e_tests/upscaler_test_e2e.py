"""
Video Resolution Upscaler WebUI End-to-End (E2E) Test Suite.
Validates the complete real-world user lifecycle for video upscaling:
  1. ComfyUI backend startup & connection (/system_stats, check_server)
  2. Frontend WebUI server startup (launch_webui, HTTP 200 health probe on / and /config)
  3. Simulating user opening the webpage & discovering models from F:\\Comfy_models\\upscale_models
  4. Simulating user submitting an upscale task request via live WebUI API (/handle_upscale_generate)
  5. Monitoring real-time upscaling progress stream until 100% completion
  6. Verifying user video download succeeded (non-empty MP4 with valid header magic bytes)
  7. History gallery retrieval & strict multi-device segregation verification
  8. Clean shutdown of WebUI and backend servers
"""

import os
import sys
import time
import json
import uuid
import socket
import argparse
import tempfile
import threading
import requests
import gradio_client
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# --- High-Fidelity Mock ComfyUI Server for Video Upscaler ---

class MockComfyUIUpscalerHandler(BaseHTTPRequestHandler):
    submitted_prompts = set()
    poll_counts = {}
    # Timeline log: (prompt_id, is_upscale_graph, submission_wall_time)
    prompt_log = []

    def log_message(self, format, *args):
        # Suppress noisy HTTP logging in test output
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/system_stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"system": {"status": "ok"}}')
            return

        elif path.startswith("/history/"):
            prompt_id = path.replace("/history/", "").strip()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            # Return empty on first poll, completed output on subsequent polls
            if prompt_id in self.submitted_prompts:
                count = self.poll_counts.get(prompt_id, 0)
                self.poll_counts[prompt_id] = count + 1
                if count >= 1:
                    resp = {
                        prompt_id: {
                            "outputs": {
                                "12": {
                                    "videos": [
                                        {
                                            "filename": f"upscale_e2e_{prompt_id[:8]}.mp4",
                                            "subfolder": "video",
                                            "type": "output",
                                        }
                                    ]
                                }
                            }
                        }
                    }
                else:
                    resp = {}
            else:
                resp = {}
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        elif path == "/queue":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            running = []
            for p_id in self.submitted_prompts:
                if self.poll_counts.get(p_id, 0) < 1:
                    running.append([0, p_id, {}])
            self.wfile.write(json.dumps({"queue_running": running, "queue_pending": []}).encode("utf-8"))
            return

        elif path == "/view":
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.end_headers()
            # Standard MP4 header + sample payload for downloaded upscaled video
            dummy_mp4_bytes = (
                b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2mp41"
                b"\x00\x00\x00\x08free\x00\x00\x00\x18mdatUpscale_E2E_Video_Output"
            )
            self.wfile.write(dummy_mp4_bytes)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/upload/image":
            content_length = int(self.headers.get("Content-Length", 0))
            _ = self.rfile.read(content_length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            mock_filename = f"upload_video_{uuid.uuid4().hex[:8]}.mp4"
            self.wfile.write(json.dumps({"name": mock_filename}).encode("utf-8"))
            return

        elif path == "/prompt":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            prompt_graph = data.get("prompt", {})
            is_minimax_graph = "unet_loader" in prompt_graph

            if not is_minimax_graph:
                # Verify prompt graph contains the 6 required nodes from utility-gan_upscaler.json
                assert "1" in prompt_graph, "Missing UpscaleModelLoader (node 1) in upscale graph"
                assert "9" in prompt_graph, "Missing LoadVideo (node 9) in upscale graph"
                assert "10" in prompt_graph, "Missing GetVideoComponents (node 10) in upscale graph"
                assert "2" in prompt_graph, "Missing ImageUpscaleWithModel (node 2) in upscale graph"
                assert "11" in prompt_graph, "Missing CreateVideo (node 11) in upscale graph"
                assert "12" in prompt_graph, "Missing SaveVideo (node 12) in upscale graph"

            # Strict ComfyUI node schema validation (simulating execution.validate_prompt)
            node_11_inputs = prompt_graph.get("11", {}).get("inputs", {})
            if "bit_depth" in node_11_inputs:
                bd_val = node_11_inputs["bit_depth"]
                if isinstance(bd_val, str):
                    try:
                        int(bd_val)
                    except ValueError:
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "error": {
                                "type": "prompt_outputs_failed_validation",
                                "message": f"Failed to convert an input value to a INT value: bit_depth, {bd_val}, invalid literal for int() with base 10: '{bd_val}'"
                            }
                        }).encode("utf-8"))
                        return

            prompt_id = str(uuid.uuid4())
            self.submitted_prompts.add(prompt_id)
            self.poll_counts[prompt_id] = 0
            self.prompt_log.append((prompt_id, not is_minimax_graph, time.time()))

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"prompt_id": prompt_id}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


def start_mock_comfyui_server():
    """Starts the mock ComfyUI server on an available local port."""
    server = HTTPServer(("127.0.0.1", 0), MockComfyUIUpscalerHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server, f"http://127.0.0.1:{port}"


def find_free_port(start_port: int = 7885) -> int:
    """Finds an available local port starting from start_port."""
    for p in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 7896


# --- Video Resolution Upscaler End-to-End Test Runner ---

class UpscalerE2ETestRunner:
    def __init__(self, use_live_server: bool = False):
        self.use_live_server = use_live_server
        self.mock_server = None
        self.backend_url = None
        self.webui_port = None
        self.webui_url = None
        self.client = None
        self.temp_dir = tempfile.mkdtemp(prefix="upscaler_e2e_")
        self.results = []

    def log_step(self, step_name: str, passed: bool, message: str = "", duration: float = 0.0):
        status = "[PASS]" if passed else "[FAIL]"
        self.results.append((step_name, passed, message, duration))
        dur_str = f"({duration:.2f}s)" if duration > 0 else ""
        print(f" {status} {step_name} {dur_str}")
        if message:
            print(f"        -> {message}")

    def create_valid_test_video(self) -> str:
        """Creates a dummy valid MP4 file with binary headers on disk."""
        vid_path = os.path.join(self.temp_dir, f"test_input_{uuid.uuid4().hex[:6]}.mp4")
        dummy_mp4_bytes = (
            b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2mp41"
            b"\x00\x00\x00\x08free\x00\x00\x00\x20mdatUpscaler_Input_Video_Test_Data"
        )
        with open(vid_path, "wb") as f:
            f.write(dummy_mp4_bytes)
        return vid_path

    def run(self) -> bool:
        print("=" * 75)
        print("Video Resolution Upscaler WebUI End-to-End (E2E) Test Suite")
        print("=" * 75)

        total_start = time.time()

        # -------------------------------------------------------------
        # STEP 1: ComfyUI Backend Service Startup & Verification
        # -------------------------------------------------------------
        t0 = time.time()
        try:
            import config
            import comfy_client

            if self.use_live_server:
                self.backend_url = config.COMFY_SERVER_URL
                print(f"[*] Verifying live ComfyUI backend at {self.backend_url}...")
                ok, msg = comfy_client.check_server(self.backend_url)
                if not ok:
                    print(f"[*] ComfyUI offline, attempting backend startup...")
                    ok, msg = comfy_client.start_comfyui_backend(self.backend_url)
                assert ok, f"Live ComfyUI backend unavailable: {msg}"
            else:
                self.mock_server, self.backend_url = start_mock_comfyui_server()
                config.set_comfy_server_url(self.backend_url)
                print(f"[*] Started In-Process Mock ComfyUI Server on {self.backend_url}")

            # Verify /system_stats
            resp = requests.get(f"{self.backend_url}/system_stats", timeout=5)
            assert resp.status_code == 200, f"/system_stats returned {resp.status_code}"
            ok, msg = comfy_client.check_server(self.backend_url)
            assert ok, f"check_server failed: {msg}"

            self.log_step("Step 1: ComfyUI Backend Startup & Connection", True, f"Online ({msg})", time.time() - t0)
        except Exception as e:
            self.log_step("Step 1: ComfyUI Backend Startup & Connection", False, str(e), time.time() - t0)
            self._cleanup()
            return False

        # -------------------------------------------------------------
        # STEP 2: Frontend WebUI Server Startup & HTTP Health Probe
        # -------------------------------------------------------------
        t0 = time.time()
        try:
            import app
            from task_manager import task_manager

            self.webui_port = find_free_port(7885)
            self.webui_url = f"http://127.0.0.1:{self.webui_port}"
            print(f"[*] Launching WebUI Server on {self.webui_url}...")

            os.environ["TEST_OVERRIDE_STATUS"] = "OK"
            app.launch_webui(port=self.webui_port, raise_on_error=True, prevent_thread_lock=True, quiet=True)

            # Probe HTTP Root (/)
            resp_root = requests.get(f"{self.webui_url}/", timeout=6)
            assert resp_root.status_code == 200, f"WebUI root returned HTTP {resp_root.status_code}"

            # Probe HTTP Config (/config)
            resp_config = requests.get(f"{self.webui_url}/config", timeout=6)
            assert resp_config.status_code == 200, f"WebUI /config returned HTTP {resp_config.status_code}"
            assert "components" in resp_config.json(), "Missing components in WebUI /config payload"

            # Connect Gradio client to the live WebUI server
            self.client = gradio_client.Client(self.webui_url)

            self.log_step("Step 2: Frontend WebUI Server Launch & Health Probe", True,
                          f"Bound to port {self.webui_port}, HTTP 200 OK & Gradio API connected", time.time() - t0)
        except Exception as e:
            self.log_step("Step 2: Frontend WebUI Server Launch & Health Probe", False, str(e), time.time() - t0)
            self._cleanup()
            return False

        # -------------------------------------------------------------
        # STEP 3: User Webpage Load & Upscale Model Discovery
        # -------------------------------------------------------------
        t0 = time.time()
        try:
            from config import get_upscale_models
            models = get_upscale_models()
            assert len(models) > 0, "No upscale models found in models directory!"
            assert "RealESRGAN_x4plus.safetensors" in models or "4x-UltraSharp.safetensors" in models, (
                f"Expected standard upscale model in choices: {models}"
            )
            chosen_model = models[0]

            self.log_step(
                "Step 3: Webpage Load & Upscale Model Discovery",
                True,
                f"Discovered {len(models)} models from upscale_models dir: {models} -> Selected: {chosen_model}",
                time.time() - t0,
            )
        except Exception as e:
            self.log_step("Step 3: Webpage Load & Upscale Model Discovery", False, str(e), time.time() - t0)
            self._cleanup()
            return False

        # -------------------------------------------------------------
        # STEP 4 & 5: Simulate User Submitting Video Upscaler Request & Monitoring Progress
        # -------------------------------------------------------------
        t0 = time.time()
        user_device_id = f"dev_upscaler_{uuid.uuid4().hex[:6]}"
        test_video = self.create_valid_test_video()
        try:
            print(f"[*] Submitting live Video Upscaler request with model '{chosen_model}' via Gradio Client...")

            job = self.client.submit(
                gradio_client.handle_file(test_video),  # input_video
                chosen_model,                           # upscale_model
                None,                                   # session_task_state
                user_device_id,                         # device_id_state
                api_name="/handle_upscale_generate",
            )

            # Monitor progress stream until completion
            last_yield = None
            observed_stages = []
            start_gen_time = time.time()

            for item in job:
                last_yield = item
                html_snippet = item[0] if isinstance(item, (list, tuple)) else str(item)
                if "前處理" in html_snippet and "preprocessing" not in observed_stages:
                    observed_stages.append("preprocessing")
                elif ("排隊中" in html_snippet or "生成中" in html_snippet or "處理中" in html_snippet) and "running" not in observed_stages:
                    observed_stages.append("running")
                elif ("後處理" in html_snippet or "完成" in html_snippet) and "postprocessing" not in observed_stages:
                    observed_stages.append("postprocessing")

                if time.time() - start_gen_time > 45:
                    raise TimeoutError("Video upscaling exceeded 45s timeout!")

            assert last_yield is not None, "Job finished without yielding any outputs"
            final_html, final_video, final_task_id, final_dev_id = last_yield
            assert "100%" in final_html or "完成" in final_html, f"Final progress HTML unexpected: {final_html}"
            assert final_task_id, "Missing task_id in final upscale yield"
            assert final_dev_id == user_device_id, f"Device ID mismatch in output: {final_dev_id}"

            # Verify task object in task_manager
            t_obj = task_manager.get_task(final_task_id, device_id=user_device_id)
            assert t_obj is not None, "Task object not found in task_manager"
            assert t_obj.task_type == "UPSCALER", f"Expected task_type 'UPSCALER', got '{t_obj.task_type}'"
            assert t_obj.params["model"] == chosen_model, f"Expected model '{chosen_model}', got '{t_obj.params.get('model')}'"

            self.log_step(
                "Step 4 & 5: Video Upscaler Request & Real-Time Progress Stream",
                True,
                f"Streamed progress through stages: {observed_stages} -> Completed (Task ID: {final_task_id[:16]}, Model: {chosen_model})",
                time.time() - t0,
            )
        except Exception as e:
            self.log_step("Step 4 & 5: Video Upscaler Request & Real-Time Progress Stream", False, str(e), time.time() - t0)
            self._cleanup()
            return False

        # -------------------------------------------------------------
        # STEP 6: Verify User Video Download Succeeded
        # -------------------------------------------------------------
        t0 = time.time()
        try:
            assert final_video, "Returned upscaled video file path is empty!"
            assert os.path.exists(final_video), f"Upscaled video file missing from disk: {final_video}"
            file_size = os.path.getsize(final_video)
            assert file_size > 0, f"Upscaled video file is empty (0 bytes): {final_video}"

            # Verify MP4 magic header bytes
            with open(final_video, "rb") as vf:
                header_bytes = vf.read(16)
            assert b"ftyp" in header_bytes or b"isom" in header_bytes, "Invalid MP4 header format in upscaled output"

            self.log_step(
                "Step 6: User Video Download & Integrity Check",
                True,
                f"File verified: {os.path.basename(final_video)} ({file_size} bytes, valid MP4 header)",
                time.time() - t0,
            )
        except Exception as e:
            self.log_step("Step 6: User Video Download & Integrity Check", False, str(e), time.time() - t0)
            self._cleanup()
            return False

        # -------------------------------------------------------------
        # STEP 6.5: Cross-Module Concurrency — minimax + upscale queue politely
        # (Spec Task 1: serial queueing, no cross-module preemption;
        #  Spec Task 2: per-module history isolation on a shared device)
        # -------------------------------------------------------------
        t0 = time.time()
        cross_dev = f"dev_cross_{uuid.uuid4().hex[:6]}"
        try:
            from components.history_gallery import get_history_dropdown_choices

            # Dummy first-frame PNG for the MiniMax I2V job (real 1x1 RGBA PNG via PIL)
            from PIL import Image
            png_path = os.path.join(self.temp_dir, f"cross_frame_{uuid.uuid4().hex[:6]}.png")
            Image.new("RGBA", (1, 1), (128, 128, 128, 255)).save(png_path)

            print("[*] Cross-module: submitting MiniMax I2V job...")
            mm_job = self.client.submit(
                gradio_client.handle_file(png_path),   # first_frame
                None,                                  # last_frame
                "Cross-module queueing e2e shot",      # prompt
                "16:9 (橫向風景)",                     # aspect_ratio
                "5 (1.0 MP - 標準推薦)",               # quality_level
                2.0,                                   # duration
                1,                                     # seed
                20,                                    # steps
                1.0,                                   # denoise
                "res_multistep",                       # sampler
                "simple",                              # scheduler
                24,                                    # fps
                None,                                  # session_task_state
                cross_dev,                             # device_id_state
                api_name="/handle_i2v_generate",
            )

            mm_final_yield = {}
            mm_stream_done = threading.Event()

            def consume_minimax_stream():
                try:
                    for item in mm_job:
                        mm_final_yield["last"] = item
                except Exception as exc:
                    mm_final_yield["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
                finally:
                    mm_stream_done.set()

            threading.Thread(target=consume_minimax_stream, daemon=True).start()

            # Submit an upscale task while minimax still occupies the serial backend.
            time.sleep(0.5)
            print("[*] Cross-module: submitting Video Upscaler job while minimax is active...")
            cross_video = self.create_valid_test_video()
            up_job = self.client.submit(
                gradio_client.handle_file(cross_video),
                chosen_model,
                None,
                cross_dev,
                api_name="/handle_upscale_generate",
            )

            up_yields = []
            for item in up_job:
                up_yields.append(item)
                if time.time() - t0 > 60:
                    raise TimeoutError("Cross-module upscale exceeded 60s timeout!")

            assert mm_stream_done.wait(timeout=60), "MiniMax progress stream did not finish!"

            mm_final = mm_final_yield.get("last")
            up_final = up_yields[-1] if up_yields else None
            assert mm_final is not None and up_final is not None, (
                "Missing final yields in cross-module streams "
                f"(minimax stream error: {mm_final_yield.get('error', 'none')})"
            )

            mm_html, mm_video, mm_task_id, _ = mm_final
            up_html, up_video, up_task_id, _ = up_final

            # Both tasks must have run to completion: neither was preempted by the other.
            assert ("完成" in mm_html or "100%" in mm_html), f"MiniMax job was preempted! Final stream: {str(mm_html)[:120]}"
            assert ("完成" in up_html or "100%" in up_html), f"Upscale job failed! Final stream: {str(up_html)[:120]}"

            t_mm = task_manager.get_task(mm_task_id, device_id=cross_dev)
            t_up = task_manager.get_task(up_task_id, device_id=cross_dev)
            assert t_mm and t_up, "Cross-module task objects missing from task_manager"
            assert t_mm.status == "completed" and t_mm.module == "minimax"
            assert t_up.status == "completed" and t_up.module == "upscaler"

            # Serial dispatcher evidence: the upscale prompt only reached ComfyUI
            # after the minimax task had already completed (no backend overlap).
            log_by_pid = {pid: (is_up, ts) for pid, is_up, ts in MockComfyUIUpscalerHandler.prompt_log}
            assert t_mm.prompt_id in log_by_pid and t_up.prompt_id in log_by_pid, "Missing prompt submissions in mock timeline log"
            up_submit_ts = log_by_pid[t_up.prompt_id][1]
            assert up_submit_ts >= t_mm.completed_at - 0.6, (
                f"Serial dispatcher violated: upscale prompt submitted at {up_submit_ts:.2f} "
                f"but minimax task only completed at {t_mm.completed_at:.2f}"
            )

            # Per-module history isolation on the SAME shared device (Spec Task 2)
            mm_hist = [tid for _, tid in get_history_dropdown_choices(cross_dev, module="minimax") if tid]
            up_hist = [tid for _, tid in get_history_dropdown_choices(cross_dev, module="upscaler") if tid]
            assert mm_hist == [mm_task_id], f"minimax history gallery polluted on shared device: {mm_hist}"
            assert up_hist == [up_task_id], f"upscaler history gallery polluted on shared device: {up_hist}"

            self.log_step(
                "Step 6.5: Cross-Module Concurrency (Serial Queuing & History Isolation)",
                True,
                f"minimax {mm_task_id[:16]} and upscale {up_task_id[:16]} completed serially on device '{cross_dev}' "
                f"(upscale prompt submitted {up_submit_ts - t_mm.completed_at:+.2f}s relative to minimax completion)",
                time.time() - t0,
            )
        except Exception as e:
            self.log_step("Step 6.5: Cross-Module Concurrency (Serial Queuing & History Isolation)", False, str(e), time.time() - t0)
            self._cleanup()
            return False

        # -------------------------------------------------------------
        # STEP 7: History Gallery & Multi-Device Segregation Verification
        # -------------------------------------------------------------
        t0 = time.time()
        stranger_device_id = f"dev_stranger_{uuid.uuid4().hex[:6]}"
        try:
            from components.history_gallery import (
                get_history_dropdown_choices,
                on_select_history_item,
                on_delete_history_item,
            )

            # 1. User sees own upscaled task in history dropdown
            user_choices = get_history_dropdown_choices(user_device_id, task_type="UPSCALER")
            user_task_ids = [t_id for _, t_id in user_choices if t_id]
            assert final_task_id in user_task_ids, "Upscale task not found in user's history dropdown!"

            # 2. Selecting history item returns video and markdown metadata
            hist_video, hist_info = on_select_history_item(final_task_id, user_device_id)
            assert hist_video and os.path.exists(hist_video), "History item video file missing"
            assert "任務詳細資料" in hist_info, "History markdown info missing"
            assert "UPSCALER" in hist_info, "History task_type info missing"

            # 3. Stranger device sees ZERO history and cannot access user's task
            stranger_choices = get_history_dropdown_choices(stranger_device_id, task_type="UPSCALER")
            assert not any(t_id == final_task_id for _, t_id in stranger_choices), "User upscale task leaked to stranger device history!"

            blocked_task = task_manager.get_task(final_task_id, device_id=stranger_device_id)
            assert blocked_task is None, "Stranger device improperly accessed user's isolated task!"

            # 4. User deletes task via on_delete_history_item
            updated_dd, empty_v, _ = on_delete_history_item(final_task_id, user_device_id, task_type="UPSCALER")
            updated_choices = updated_dd.get("choices") if isinstance(updated_dd, dict) else getattr(updated_dd, "choices", [])
            assert not any(t_id == final_task_id for _, t_id in updated_choices), "Deleted upscale task still appears in user history!"
            assert task_manager.get_task(final_task_id, device_id=user_device_id) is None, "Task still present in task_manager after delete!"

            self.log_step(
                "Step 7: History Gallery & Multi-Device Segregation (Including Delete)",
                True,
                "Upscaler history retrieval, metadata inspection, delete operation, and strict isolation confirmed",
                time.time() - t0,
            )
        except Exception as e:
            self.log_step("Step 7: History Gallery & Multi-Device Segregation", False, str(e), time.time() - t0)
            self._cleanup()
            return False

        # -------------------------------------------------------------
        # STEP 8: Clean Server Shutdown
        # -------------------------------------------------------------
        t0 = time.time()
        try:
            self._cleanup()
            self.log_step("Step 8: Clean Server Shutdown", True, "WebUI and mock ComfyUI backend servers terminated gracefully", time.time() - t0)
        except Exception as e:
            self.log_step("Step 8: Clean Server Shutdown", False, str(e), time.time() - t0)
            return False

        # -------------------------------------------------------------
        # Final Summary
        # -------------------------------------------------------------
        total_time = time.time() - total_start
        all_passed = all(p for _, p, _, _ in self.results)

        print("=" * 75)
        if all_passed:
            print(f" ALL UPSCALER E2E TESTS PASSED SUCCESSFULLY! (Total: {total_time:.2f}s)")
        else:
            print(f" UPSCALER E2E TEST SUITE REPORTED FAILURES. (Total: {total_time:.2f}s)")
        print("=" * 75)

        return all_passed

    def _cleanup(self):
        """Terminates active servers."""
        try:
            import app
            app.demo.close()
        except Exception:
            pass

        if self.mock_server is not None:
            try:
                self.mock_server.shutdown()
                self.mock_server.server_close()
            except Exception:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video Resolution Upscaler WebUI End-to-End Test")
    parser.add_argument("--live", action="store_true", help="Test against live ComfyUI backend")
    args = parser.parse_args()

    runner = UpscalerE2ETestRunner(use_live_server=args.live)
    success = runner.run()
    sys.exit(0 if success else 1)

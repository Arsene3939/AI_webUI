"""
MiniMax-H3 WebUI End-to-End (E2E) Generation Test Suite.
Validates the complete real-world user lifecycle:
  1. ComfyUI backend startup & connection (/system_stats, check_server)
  2. Frontend WebUI server startup (launch_webui, HTTP 200 health probe on / and /config)
  3. Simulating user opening the webpage (demo.load with legacy session data containing
     "1 (0.5 MP - 極速)", verifying zero Dropdown.preprocess choice errors & component normalization)
  4. Simulating user submitting a video generation request via the live WebUI API (handle_i2v_generate / handle_t2v_generate)
  5. Monitoring real-time generation progress stream until 100% completion
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
from PIL import Image
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
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# --- High-Fidelity Mock ComfyUI Server for Fast, Deterministic Testing ---

class MockComfyUIHandler(BaseHTTPRequestHandler):
    submitted_prompts = set()
    poll_counts = {}

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
                                "save_video": {
                                    "videos": [
                                        {
                                            "filename": f"minimax_e2e_{prompt_id[:8]}.mp4",
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
            # Standard MP4 header + sample payload
            dummy_mp4_bytes = (
                b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2mp41"
                b"\x00\x00\x00\x08free\x00\x00\x00\x18mdatMiniMax_E2E_Video_Output"
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
            mock_filename = f"upload_{uuid.uuid4().hex[:8]}.png"
            self.wfile.write(json.dumps({"name": mock_filename}).encode("utf-8"))
            return

        elif path == "/prompt":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            prompt_id = str(uuid.uuid4())
            self.submitted_prompts.add(prompt_id)
            self.poll_counts[prompt_id] = 0

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"prompt_id": prompt_id}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


def start_mock_comfyui_server():
    """Starts the mock ComfyUI server on an available local port."""
    server = HTTPServer(("127.0.0.1", 0), MockComfyUIHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server, f"http://127.0.0.1:{port}"


def find_free_port(start_port: int = 7880) -> int:
    """Finds an available local port starting from start_port."""
    for p in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 7895


# --- Comprehensive End-to-End User Lifecycle Test Runner ---

class E2ETestRunner:
    def __init__(self, use_live_server: bool = False):
        self.use_live_server = use_live_server
        self.mock_server = None
        self.backend_url = None
        self.webui_port = None
        self.webui_url = None
        self.client = None
        self.temp_dir = tempfile.mkdtemp(prefix="minimax_e2e_")
        self.results = []

    def log_step(self, step_name: str, passed: bool, message: str = "", duration: float = 0.0):
        status = "[PASS]" if passed else "[FAIL]"
        self.results.append((step_name, passed, message, duration))
        dur_str = f"({duration:.2f}s)" if duration > 0 else ""
        print(f" {status} {step_name} {dur_str}")
        if message:
            print(f"        -> {message}")

    def create_valid_test_image(self, width: int = 1280, height: int = 720) -> str:
        """Generates a valid PNG test image on disk."""
        img_path = os.path.join(self.temp_dir, f"test_frame_{uuid.uuid4().hex[:6]}.png")
        im = Image.new("RGB", (width, height), color=(30, 65, 110))
        im.save(img_path)
        return img_path

    def run(self) -> bool:
        print("=" * 75)
        print("MiniMax-H3 WebUI End-to-End (E2E) Realistic User Lifecycle Test Suite")
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

            self.webui_port = find_free_port(7880)
            self.webui_url = f"http://127.0.0.1:{self.webui_port}"
            print(f"[*] Launching WebUI Server on {self.webui_url}...")

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
        # STEP 3: Simulate User Opening Webpage & Session Restore
        # (Directly tests & validates fix for dropdown crash with legacy "1 (0.5 MP - 極速)")
        # -------------------------------------------------------------
        t0 = time.time()
        legacy_device_id = f"dev_legacy_{uuid.uuid4().hex[:6]}"
        try:
            from config import QUALITY_CHOICES

            # Seed task history with legacy task containing old 5-level format
            legacy_params = {
                "prompt": "E2E Legacy Task Verification",
                "quality_level": "1 (0.5 MP - 極速)",
                "aspect_ratio": "16:9 橫向風景 (1344 x 768)",
                "custom_w": 1344,
                "custom_h": 768,
                "duration": 2.0,
                "seed": 9999,
                "steps": 20,
                "denoise": 1.0,
                "sampler": "unknown_sampler",
                "scheduler": "unknown_scheduler",
            }
            legacy_task = task_manager.create_task("I2V", legacy_params["prompt"], legacy_params, device_id=legacy_device_id)

            # Simulate user browser opening webpage (calls demo.load -> restore_device_state)
            restored = self.client.predict(legacy_device_id, legacy_task.task_id, api_name="/restore_device_state")
            assert len(restored) == len(app.all_restored_outputs), f"Outputs mismatch: {len(restored)} vs {len(app.all_restored_outputs)}"

            # Verify quality level component was normalized to current QUALITY_CHOICES (avoiding dropdown crash!)
            i2v_quality_update = restored[8]  # index 8 in all_restored_outputs
            quality_val = i2v_quality_update.get("value") if isinstance(i2v_quality_update, dict) else i2v_quality_update
            assert quality_val in QUALITY_CHOICES, f"Restored quality '{quality_val}' was not normalized into QUALITY_CHOICES!"

            i2v_ar_update = restored[7]  # index 7 in all_restored_outputs
            ar_val = i2v_ar_update.get("value") if isinstance(i2v_ar_update, dict) else i2v_ar_update
            assert ar_val in app.ASPECT_RATIOS, f"Restored aspect ratio '{ar_val}' is invalid!"

            # Simulate browser triggering dropdown .change event (on_resolution_change)
            res_change = self.client.predict(ar_val, quality_val, api_name="/on_resolution_change")
            assert len(res_change) == 3, f"Unexpected on_resolution_change return: {res_change}"

            # Simulate user manually switching device ID
            switch_res = self.client.predict("998877", legacy_device_id, None, api_name="/switch_manual_device_id")
            assert len(switch_res) == len(app.all_restored_outputs), f"Unexpected switch output count: {len(switch_res)}"

            self.log_step(
                "Step 3: Webpage Load & Session Restore (Dropdown Bug Fix)",
                True,
                f"Legacy '1 (0.5 MP - 極速)' successfully normalized to '{quality_val}' with zero exceptions",
                time.time() - t0
            )
        except Exception as e:
            import traceback
            err_msg = f"{type(e).__name__}: {str(e) or traceback.format_exc()}"
            self.log_step("Step 3: Webpage Load & Session Restore (Dropdown Bug Fix)", False, err_msg, time.time() - t0)
            self._cleanup()
            return False

        # -------------------------------------------------------------
        # STEP 4 & 5: Simulate User Submitting Video Generation Request & Monitoring Real-Time Progress Stream
        # -------------------------------------------------------------
        t0 = time.time()
        user_device_id = f"dev_user_{uuid.uuid4().hex[:6]}"
        test_img = self.create_valid_test_image(1280, 720)
        try:
            print("[*] Submitting live Image-to-Video (I2V) request via Gradio Client...")
            # Submit generation request to the live server
            job = self.client.submit(
                gradio_client.handle_file(test_img),  # i2v_first_frame
                None,                                 # i2v_last_frame
                "E2E High-Speed Train Crossing Cyberpunk City at Sunset",
                "16:9 (橫向風景)",
                "5 (1.0 MP - 標準推薦)",
                1344,
                768,
                2.0,
                88888,
                20,
                1.0,
                "res_multistep",
                "simple",
                24,
                app.DEFAULT_UNET,
                app.DEFAULT_CLIP,
                app.DEFAULT_VIDEO_VAE,
                app.DEFAULT_AUDIO_VAE,
                None,
                user_device_id,
                api_name="/handle_i2v_generate",
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
                elif ("排隊中" in html_snippet or "生成中" in html_snippet) and "running" not in observed_stages:
                    observed_stages.append("running")
                elif ("後處理" in html_snippet or "完成" in html_snippet) and "postprocessing" not in observed_stages:
                    observed_stages.append("postprocessing")

                if time.time() - start_gen_time > 45:
                    raise TimeoutError("Video generation exceeded 45s timeout!")

            assert last_yield is not None, "Job finished without yielding any outputs"
            final_html, final_video, final_task_id, final_dev_id = last_yield
            assert "100%" in final_html or "完成" in final_html, f"Final progress HTML unexpected: {final_html}"
            assert final_task_id, "Missing task_id in final generation yield"
            assert final_dev_id == user_device_id, f"Device ID mismatch in output: {final_dev_id}"

            self.log_step(
                "Step 4 & 5: Video Generation Request & Real-Time Progress Stream",
                True,
                f"Streamed progress through stages: {observed_stages} -> Completed (Task ID: {final_task_id[:16]})",
                time.time() - t0
            )
        except Exception as e:
            self.log_step("Step 4 & 5: Video Generation Request & Real-Time Progress Stream", False, str(e), time.time() - t0)
            self._cleanup()
            return False

        # -------------------------------------------------------------
        # STEP 6: Verify User Video Download Succeeded
        # -------------------------------------------------------------
        t0 = time.time()
        try:
            assert final_video, "Returned video file path is empty!"
            # Check local file presence
            assert os.path.exists(final_video), f"Generated video file missing from disk: {final_video}"
            file_size = os.path.getsize(final_video)
            assert file_size > 0, f"Generated video file is empty (0 bytes): {final_video}"

            # Verify MP4 magic header bytes
            with open(final_video, "rb") as vf:
                header_bytes = vf.read(16)
            assert b"ftyp" in header_bytes or b"isom" in header_bytes, "Invalid MP4 header format"

            self.log_step(
                "Step 6: User Video Download & Integrity Check",
                True,
                f"File verified: {os.path.basename(final_video)} ({file_size} bytes, valid MP4 header)",
                time.time() - t0
            )
        except Exception as e:
            self.log_step("Step 6: User Video Download & Integrity Check", False, str(e), time.time() - t0)
            self._cleanup()
            return False

        # -------------------------------------------------------------
        # STEP 7: History Gallery & Multi-Device Segregation Verification
        # -------------------------------------------------------------
        t0 = time.time()
        stranger_device_id = f"dev_stranger_{uuid.uuid4().hex[:6]}"
        try:
            # 1. User sees own task in history dropdown
            user_choices = app.get_history_dropdown_choices(user_device_id)
            user_task_ids = [t_id for _, t_id in user_choices if t_id]
            assert final_task_id in user_task_ids, "Generated task not found in user's history dropdown!"

            # 2. Selecting history item returns video and markdown metadata
            hist_video, hist_info = app.on_select_history_item(final_task_id, user_device_id)
            assert hist_video and os.path.exists(hist_video), "History item video file missing"
            assert "任務詳細資料" in hist_info, "History markdown info missing"

            # 3. Stranger device sees ZERO history and cannot access user's task
            stranger_choices = app.get_history_dropdown_choices(stranger_device_id)
            assert not any(t_id == final_task_id for _, t_id in stranger_choices), "User task leaked to stranger device history!"

            blocked_task = task_manager.get_task(final_task_id, device_id=stranger_device_id)
            assert blocked_task is None, "Stranger device improperly accessed user's isolated task!"

            self.log_step(
                "Step 7: History Gallery & Multi-Device Segregation",
                True,
                "History retrieval verified; strict isolation between devices confirmed",
                time.time() - t0
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
            self.log_step("Step 8: Clean Server Shutdown", True, "WebUI and backend servers terminated gracefully", time.time() - t0)
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
            print(f" ALL REALISTIC E2E TESTS PASSED SUCCESSFULLY! (Total: {total_time:.2f}s)")
        else:
            print(f" E2E TEST SUITE REPORTED FAILURES. (Total: {total_time:.2f}s)")
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
    parser = argparse.ArgumentParser(description="MiniMax-H3 WebUI End-to-End Test")
    parser.add_argument("--live", action="store_true", help="Test against live ComfyUI backend")
    args = parser.parse_args()

    runner = E2ETestRunner(use_live_server=args.live)
    success = runner.run()
    sys.exit(0 if success else 1)

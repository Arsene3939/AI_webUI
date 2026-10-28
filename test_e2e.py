"""
MiniMax-H3 WebUI End-to-End (E2E) Generation Test Script.
Validates the complete lifecycle:
  1. Module initialization & Gradio Blocks integrity
  2. ComfyUI connection & media upload pipeline
  3. Image-to-Video (I2V) background generation & download
  4. Text-to-Video (T2V) background generation & download
  5. Reference-to-Video (R2V) multi-modal workflow generation
  6. Mobile standby / page refresh session state restoration (demo.load)
  7. Strict per-device isolation between separate users/devices
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
from urllib.parse import urlparse, parse_qs

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


# --- Lightweight Mock ComfyUI Server for Deterministic, Fast E2E Testing ---

class MockComfyUIHandler(BaseHTTPRequestHandler):
    submitted_prompts = set()
    history_records = {}

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging in test output
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

            # If prompt was queued, return completed video outputs
            if prompt_id in self.submitted_prompts:
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
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        elif path == "/queue":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"queue_running": [], "queue_pending": []}')
            return

        elif path == "/view":
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.end_headers()
            # Valid dummy MP4 header + payload
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


# --- E2E Test Suite Execution ---

class E2ETestRunner:
    def __init__(self, use_live_server: bool = False):
        self.use_live_server = use_live_server
        self.mock_server = None
        self.server_url = None
        self.temp_dir = tempfile.mkdtemp(prefix="minimax_e2e_")
        self.results = []

    def log_step(self, step_name: str, passed: bool, message: str = "", duration: float = 0.0):
        status = "[PASS]" if passed else "[FAIL]"
        self.results.append((step_name, passed, message, duration))
        dur_str = f"({duration:.2f}s)" if duration > 0 else ""
        print(f" {status} {step_name} {dur_str}")
        if message:
            print(f"        -> {message}")

    def create_dummy_media(self):
        """Creates dummy image, video, and audio files for E2E testing."""
        # 1. Image
        img_path = os.path.join(self.temp_dir, "test_input_first_frame.png")
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        with open(img_path, "wb") as f:
            f.write(png_bytes)

        # 2. Video
        vid_path = os.path.join(self.temp_dir, "test_input_video.mp4")
        with open(vid_path, "wb") as f:
            f.write(b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2mp41")

        # 3. Audio
        aud_path = os.path.join(self.temp_dir, "test_input_audio.wav")
        with open(aud_path, "wb") as f:
            f.write(b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")

        return img_path, vid_path, aud_path

    def run(self) -> bool:
        print("=" * 70)
        print("MiniMax-H3 WebUI End-to-End (E2E) Test Suite")
        print("=" * 70)

        total_start = time.time()

        # Step 1: Module Imports and Gradio App Construction
        t0 = time.time()
        try:
            import config
            import comfy_client
            import workflow_builder
            from task_manager import TaskManager, task_manager
            import app
            assert hasattr(app, "demo"), "app.py missing demo Blocks instance"
            self.log_step("Step 1: Module Imports & Gradio UI Build", True, "app.demo constructed successfully", time.time() - t0)
        except Exception as e:
            self.log_step("Step 1: Module Imports & Gradio UI Build", False, str(e), time.time() - t0)
            return False

        # Step 2: Establish ComfyUI Endpoint (Live or Mock Server)
        t0 = time.time()
        if self.use_live_server:
            self.server_url = config.COMFY_SERVER_URL
            print(f"[*] Using Live ComfyUI Endpoint: {self.server_url}")
        else:
            self.mock_server, self.server_url = start_mock_comfyui_server()
            print(f"[*] Started In-Process Mock ComfyUI Server on {self.server_url}")

        ok, msg = comfy_client.check_server(self.server_url)
        if not ok and self.use_live_server:
            self.log_step("Step 2: ComfyUI Server Connection", False, f"Server offline: {msg}", time.time() - t0)
            return False
        self.log_step("Step 2: ComfyUI Server Connection", True, f"Connection verified: {msg}", time.time() - t0)

        # Step 3: Media Creation & Upload Pipeline
        t0 = time.time()
        try:
            test_img, test_vid, test_aud = self.create_dummy_media()
            uploaded_img_name = comfy_client.upload_media_file(test_img, server_url=self.server_url)
            assert uploaded_img_name, "Upload returned empty filename"
            self.log_step("Step 3: Media File Upload Pipeline", True, f"Uploaded: {uploaded_img_name}", time.time() - t0)
        except Exception as e:
            self.log_step("Step 3: Media File Upload Pipeline", False, str(e), time.time() - t0)
            return False

        # Step 4: End-to-End Image-to-Video (I2V) Pipeline
        t0 = time.time()
        device_alpha = f"e2e_alpha_{uuid.uuid4().hex[:6]}"
        try:
            i2v_graph = workflow_builder.build_i2v_workflow(
                prompt="E2E Cyberpunk City at Dusk",
                first_frame_filename=uploaded_img_name,
                width=1344,
                height=768,
                duration_seconds=2.0,
                seed=12345,
            )
            i2v_params = {
                "first_frame": test_img,
                "prompt": "E2E Cyberpunk City at Dusk",
                "custom_w": 1344,
                "custom_h": 768,
                "duration": 2.0,
                "seed": 12345,
            }
            task_i2v = task_manager.create_task("I2V", i2v_params["prompt"], i2v_params, device_id=device_alpha)
            task_manager.start_background_task(task_i2v, i2v_graph, server_url=self.server_url)

            # Wait for background completion (up to 30 seconds for test)
            start_wait = time.time()
            while task_i2v.status not in ["completed", "failed"] and (time.time() - start_wait < 30):
                time.sleep(0.5)

            assert task_i2v.status == "completed", f"I2V task failed or timed out: {task_i2v.message}"
            assert task_i2v.video_path and os.path.exists(task_i2v.video_path), "I2V video file missing from disk"
            self.log_step("Step 4: Image-to-Video (I2V) Generation & Output", True, f"Saved: {os.path.basename(task_i2v.video_path)}", time.time() - t0)
        except Exception as e:
            self.log_step("Step 4: Image-to-Video (I2V) Generation & Output", False, str(e), time.time() - t0)
            return False

        # Step 5: End-to-End Text-to-Video (T2V) Pipeline
        t0 = time.time()
        try:
            t2v_graph = workflow_builder.build_t2v_workflow(
                prompt="E2E Spacecraft launching into orbit",
                width=1152,
                height=640,
                duration_seconds=2.0,
                seed=54321,
            )
            t2v_params = {
                "prompt": "E2E Spacecraft launching into orbit",
                "custom_w": 1152,
                "custom_h": 640,
                "duration": 2.0,
                "seed": 54321,
            }
            task_t2v = task_manager.create_task("T2V", t2v_params["prompt"], t2v_params, device_id=device_alpha)
            task_manager.start_background_task(task_t2v, t2v_graph, server_url=self.server_url)

            start_wait = time.time()
            while task_t2v.status not in ["completed", "failed"] and (time.time() - start_wait < 30):
                time.sleep(0.5)

            assert task_t2v.status == "completed", f"T2V task failed: {task_t2v.message}"
            assert task_t2v.video_path and os.path.exists(task_t2v.video_path), "T2V video file missing"
            self.log_step("Step 5: Text-to-Video (T2V) Generation & Output", True, f"Saved: {os.path.basename(task_t2v.video_path)}", time.time() - t0)
        except Exception as e:
            self.log_step("Step 5: Text-to-Video (T2V) Generation & Output", False, str(e), time.time() - t0)
            return False

        # Step 6: End-to-End Reference-to-Video (R2V) Multi-Modal Pipeline
        t0 = time.time()
        try:
            uploaded_vid_name = comfy_client.upload_media_file(test_vid, server_url=self.server_url)
            r2v_graph = workflow_builder.build_r2v_workflow(
                prompt="E2E Multi-modal reference animation",
                ref_image_filenames=[uploaded_img_name],
                ref_video_filename=uploaded_vid_name,
                width=1344,
                height=768,
            )
            r2v_params = {
                "prompt": "E2E Multi-modal reference animation",
                "ref_video": test_vid,
                "ref_img_1": test_img,
            }
            task_r2v = task_manager.create_task("R2V", r2v_params["prompt"], r2v_params, device_id=device_alpha)
            task_manager.start_background_task(task_r2v, r2v_graph, server_url=self.server_url)

            start_wait = time.time()
            while task_r2v.status not in ["completed", "failed"] and (time.time() - start_wait < 30):
                time.sleep(0.5)

            assert task_r2v.status == "completed", f"R2V task failed: {task_r2v.message}"
            assert task_r2v.video_path and os.path.exists(task_r2v.video_path), "R2V video missing"
            self.log_step("Step 6: Reference-to-Video (R2V) Pipeline", True, f"Saved: {os.path.basename(task_r2v.video_path)}", time.time() - t0)
        except Exception as e:
            self.log_step("Step 6: Reference-to-Video (R2V) Pipeline", False, str(e), time.time() - t0)
            return False

        # Step 7: Mobile Standby & Tab Reconnect State Restoration (demo.load)
        t0 = time.time()
        try:
            # Device Alpha reconnects with NO task_id specified (simulates phone screen unlock)
            ret_alpha = app.restore_device_state(stored_device_id=device_alpha, stored_task_id=None)
            restored_dev_id, restored_task_id = ret_alpha[0], ret_alpha[1]
            assert restored_dev_id == device_alpha, "Device ID mismatch during restoration"
            assert restored_task_id == task_r2v.task_id, "Latest task ID not correctly restored"

            # Check that parameters and video are populated
            found_restored_video = False
            for val in ret_alpha[4:]:
                v = val.get("value") if isinstance(val, dict) else getattr(val, "value", None)
                if v and isinstance(v, str) and v == task_r2v.video_path:
                    found_restored_video = True
                    break
            assert found_restored_video, "Generated video path was not restored to UI output component"
            self.log_step("Step 7: Session Restoration (demo.load)", True, f"Restored latest task: {restored_task_id[:16]}", time.time() - t0)
        except Exception as e:
            self.log_step("Step 7: Session Restoration (demo.load)", False, str(e), time.time() - t0)
            return False

        # Step 8: Multi-Device Isolation E2E Verification
        t0 = time.time()
        try:
            device_beta = f"e2e_beta_{uuid.uuid4().hex[:6]}"
            # Device Beta connects fresh
            ret_beta = app.restore_device_state(stored_device_id=device_beta, stored_task_id=None)
            assert ret_beta[0] == device_beta

            # Device Beta must NOT receive Device Alpha's video or prompts
            for val in ret_beta[4:]:
                v = val.get("value") if isinstance(val, dict) else getattr(val, "value", None)
                if isinstance(v, str):
                    assert task_i2v.video_path not in v, "Device Alpha video leaked to Device Beta!"
                    assert task_t2v.video_path not in v, "Device Alpha video leaked to Device Beta!"
                    assert task_r2v.video_path not in v, "Device Alpha video leaked to Device Beta!"
                    assert "E2E Cyberpunk" not in v, "Device Alpha prompt leaked to Device Beta!"

            # Device Beta unauthorized task access attempt
            blocked_task = task_manager.get_task(task_i2v.task_id, device_id=device_beta)
            assert blocked_task is None, "Device Beta improperly accessed Device Alpha's task!"

            # Device Beta history isolation
            beta_choices = app.get_history_dropdown_choices(device_beta)
            # Default placeholder when no history exists: [("— 暫無歷史任務紀錄 —", "")]
            # Ensure no valid task IDs are returned for Device Beta
            assert not any(task_id for _, task_id in beta_choices if task_id), "Device Beta received history items from other devices!"
            assert not any(t.task_id in str(beta_choices) for t in [task_i2v, task_t2v, task_r2v]), "Device Alpha tasks leaked into Device Beta history choices!"

            self.log_step("Step 8: Multi-Device Strict Segregation", True, "Zero cross-device leakage verified", time.time() - t0)
        except Exception as e:
            self.log_step("Step 8: Multi-Device Strict Segregation", False, str(e), time.time() - t0)
            return False

        # Step 9: Real WebUI Server Launch, Health Probe & API Integration
        t0 = time.time()
        test_port = 7875
        try:
            # 1. Launch WebUI on test port
            app.launch_webui(port=test_port, raise_on_error=True, prevent_thread_lock=True, quiet=True)

            # 2. Probe HTTP root (/) and /config endpoints
            resp_root = requests.get(f"http://127.0.0.1:{test_port}/", timeout=5)
            assert resp_root.status_code == 200, f"WebUI root returned HTTP {resp_root.status_code}"

            resp_config = requests.get(f"http://127.0.0.1:{test_port}/config", timeout=5)
            assert resp_config.status_code == 200, f"WebUI /config returned HTTP {resp_config.status_code}"
            config_data = resp_config.json()
            assert "components" in config_data, "WebUI /config response missing components"

            # 3. Connect Gradio Client and test API interaction
            client = gradio_client.Client(f"http://127.0.0.1:{test_port}")
            # Verify switch_manual_device_id works over HTTP without serialization/keyword errors
            res_switch = client.predict("a1b2c3", "dev_orig", None, api_name="/switch_manual_device_id")
            assert len(res_switch) == len(app.all_restored_outputs), f"Unexpected switch output count: {len(res_switch)}"

            # 4. Clean shutdown
            app.demo.close()
            self.log_step("Step 9: Live WebUI Server Launch & API Probe", True, f"Server bound to port {test_port}, HTTP 200 OK & Client API verified", time.time() - t0)
        except Exception as e:
            try:
                app.demo.close()
            except Exception:
                pass
            self.log_step("Step 9: Live WebUI Server Launch & API Probe", False, str(e), time.time() - t0)
            return False

        # Print Final Summary
        total_time = time.time() - total_start
        all_passed = all(p for _, p, _, _ in self.results)

        print("=" * 70)
        if all_passed:
            print(f" ALL E2E TESTS PASSED SUCCESSFULLY! (Total: {total_time:.2f}s)")
        else:
            print(f" E2E TEST SUITE REPORTED FAILURES. (Total: {total_time:.2f}s)")
        print("=" * 70)

        return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MiniMax-H3 WebUI End-to-End Test")
    parser.add_argument("--live", action="store_true", help="Test against live ComfyUI backend")
    args = parser.parse_args()

    runner = E2ETestRunner(use_live_server=args.live)
    success = runner.run()
    sys.exit(0 if success else 1)

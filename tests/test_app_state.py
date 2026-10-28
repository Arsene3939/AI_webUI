"""
Unit tests for app.py UI initialization, state restoration, and multi-device segregation.
"""
import os
import gradio as gr
import pytest
from app import (
    demo,
    build_header_html,
    restore_device_state,
    get_history_dropdown_choices,
    on_select_history_item,
    all_restored_outputs,
)
from task_manager import task_manager


class TestAppInitialization:
    def test_demo_blocks_instance(self):
        """Ensures Gradio Blocks app is properly built with all tabs."""
        assert isinstance(demo, gr.Blocks)
        # Verify app title
        assert "MiniMax-H3" in demo.title

    def test_build_header_html_concise_id(self):
        """Tests that device ID in header displays concise 'ID:XXX' without timestamp."""
        # When device_id is None, no ID badge is shown
        html_none = build_header_html(None)
        assert "ID:" not in html_none
        assert "裝置識別" not in html_none

        # Legacy device_id with timestamp: dev_1793124384_71c8f5 -> should show ID:71c8f5, NO 1793124384
        html_legacy = build_header_html("dev_1793124384_71c8f5")
        assert "ID:71c8f5" in html_legacy
        assert "1793124384" not in html_legacy
        assert "裝置識別" not in html_legacy

        # Concise device_id: dev_a1b2c3 -> should show ID:a1b2c3
        html_new = build_header_html("dev_a1b2c3")
        assert "ID:a1b2c3" in html_new

        # E2E format: e2e_alpha_c7dd3e -> should show ID:c7dd3e
        html_e2e = build_header_html("e2e_alpha_c7dd3e")
        assert "ID:c7dd3e" in html_e2e


class TestStateRestoration:
    def test_restore_state_new_device(self):
        """When a user connects for the first time without a device_id."""
        ret = restore_device_state(None, None)
        assert len(ret) == len(all_restored_outputs), f"Return length {len(ret)} must match outputs {len(all_restored_outputs)}"
        assigned_device_id = ret[0]
        assert assigned_device_id.startswith("dev_")

    def test_restore_state_i2v_task(self, tmp_path):
        """Tests that I2V task inputs and video are restored for the correct device."""
        dev_id = "device_test_i2v"
        dummy_video = tmp_path / "i2v_out.mp4"
        dummy_video.write_bytes(b"video_bytes")

        params = {
            "first_frame": "/path/to/frame1.png",
            "last_frame": "/path/to/frame2.png",
            "prompt": "Cyberpunk night market with neon lights",
            "res_preset": "16:9 橫向風景 (1344 x 768)",
            "custom_w": 1344,
            "custom_h": 768,
            "duration": 2.0,
            "seed": 777,
            "steps": 25,
            "denoise": 1.0,
            "fps": 24,
            "sampler": "euler",
            "scheduler": "simple",
        }
        task = task_manager.create_task("I2V", params["prompt"], params, device_id=dev_id)
        task.status = "completed"
        task.video_path = str(dummy_video)
        task.message = "Finished!"

        # Call restore_device_state for this device
        ret = restore_device_state(dev_id, task.task_id)
        assert len(ret) == len(all_restored_outputs), f"Return length {len(ret)} must match outputs {len(all_restored_outputs)}"

        returned_dev_id = ret[0]
        returned_task_id = ret[1]
        assert returned_dev_id == dev_id
        assert returned_task_id == task.task_id

        # The I2V updates start after (device_id, task_id, header, history_dropdown) -> index 4
        # I2V (16 components):
        # 4: first_frame, 5: last_frame, 6: prompt, 7: ar, 8: quality_level, 9: w, 10: h,
        # 11: duration, 12: seed, 13: steps, 14: denoise, 15: fps, 16: sampler, 17: scheduler,
        # 18: status, 19: output_video
        i2v_first_frame = ret[4]
        i2v_last_frame = ret[5]
        i2v_prompt = ret[6]
        i2v_seed = ret[12]
        i2v_video = ret[19]

        def extract_val(u):
            return u.get("value") if isinstance(u, dict) else getattr(u, "value", None)

        assert extract_val(i2v_prompt) == "Cyberpunk night market with neon lights"
        assert extract_val(i2v_seed) == 777
        assert extract_val(i2v_video) == str(dummy_video)

    def test_restore_state_t2v_task(self, tmp_path):
        """Tests that T2V task inputs and video are restored for the correct device."""
        dev_id = "device_test_t2v"
        dummy_video = tmp_path / "t2v_out.mp4"
        dummy_video.write_bytes(b"video_bytes")

        params = {
            "prompt": "Deep underwater coral reef with luminescent fish",
            "aspect_ratio": "16:9 (橫向風景)",
            "quality_level": "3 (1.0 MP - 標準推薦)",
            "custom_w": 1344,
            "custom_h": 768,
            "duration": 3.0,
            "seed": 888,
        }
        task = task_manager.create_task("T2V", params["prompt"], params, device_id=dev_id)
        task.status = "completed"
        task.video_path = str(dummy_video)

        ret = restore_device_state(dev_id, task.task_id)
        assert len(ret) == len(all_restored_outputs)

        def extract_val(u):
            return u.get("value") if isinstance(u, dict) else getattr(u, "value", None)

        # T2V components start at index 4 + 16 = 20
        # 20: prompt, 21: ar, 22: quality_level, 23: w, 24: h, 25: duration, 26: seed ... 33: video
        assert extract_val(ret[20]) == "Deep underwater coral reef with luminescent fish"
        assert extract_val(ret[26]) == 888
        assert extract_val(ret[33]) == str(dummy_video)

    def test_restore_state_r2v_task(self, tmp_path):
        """Tests that R2V task inputs and video are restored for the correct device."""
        dev_id = "device_test_r2v"
        dummy_video = tmp_path / "r2v_out.mp4"
        dummy_video.write_bytes(b"video_bytes")

        params = {
            "prompt": "Stylized animation of an ancient temple",
            "ref_image_size": "match",
            "duration": 2.5,
            "seed": 999,
        }
        task = task_manager.create_task("R2V", params["prompt"], params, device_id=dev_id)
        task.status = "completed"
        task.video_path = str(dummy_video)

        ret = restore_device_state(dev_id, task.task_id)
        assert len(ret) == len(all_restored_outputs)

        def extract_val(u):
            return u.get("value") if isinstance(u, dict) else getattr(u, "value", None)

        # R2V components start at index 4 + 16 + 14 = 34
        # 34: prompt, 35: ref_video, 36: ref_audio, 37..40: img1..4, 41: size,
        # 42: ar, 43: quality_level, 44: w, 45: h, 46: duration, 47: seed ... 54: video
        assert extract_val(ret[34]) == "Stylized animation of an ancient temple"
        assert extract_val(ret[47]) == 999
        assert extract_val(ret[54]) == str(dummy_video)

    def test_restore_state_strict_device_isolation(self, tmp_path):
        """
        Critical Test: Ensure Device B never sees Device A's inputs, prompt, or video
        upon page refresh or state restoration.
        """
        dev_a = "user_device_A"
        dev_b = "user_device_B"

        dummy_video_a = tmp_path / "private_a.mp4"
        dummy_video_a.write_bytes(b"classified_video_A")

        params_a = {
            "prompt": "Top Secret Prompt for Device A Only",
            "custom_w": 1344,
            "custom_h": 768,
            "duration": 3.0,
            "seed": 99999,
        }
        task_a = task_manager.create_task("T2V", params_a["prompt"], params_a, device_id=dev_a)
        task_a.status = "completed"
        task_a.video_path = str(dummy_video_a)

        # Device B loads the page (e.g. mobile standby or new tab)
        ret_b = restore_device_state(dev_b, stored_task_id=None)

        returned_dev_b = ret_b[0]
        assert returned_dev_b == dev_b

        # Verify that ALL updates for Device B are default (no prompt or video leaked!)
        # Check all string and dict values in ret_b
        for update_item in ret_b[4:]:
            # If an update dictionary or Gradio update has a value, it must NOT contain Device A's data
            val = getattr(update_item, "value", None)
            if isinstance(val, dict):
                val = val.get("value")
            if isinstance(val, str):
                assert "Top Secret Prompt" not in val
                assert "classified_video_A" not in val
            assert val != 99999

    def test_history_gallery_isolation(self, tmp_path):
        """Tests that history dropdown choices are strictly filtered per device."""
        dev_1 = "device_user_1"
        dev_2 = "device_user_2"

        v1 = tmp_path / "v1.mp4"
        v1.write_bytes(b"v1")
        t1 = task_manager.create_task("T2V", "Video One", {}, device_id=dev_1)
        t1.status = "completed"
        t1.video_path = str(v1)

        v2 = tmp_path / "v2.mp4"
        v2.write_bytes(b"v2")
        t2 = task_manager.create_task("T2V", "Video Two", {}, device_id=dev_2)
        t2.status = "completed"
        t2.video_path = str(v2)

        choices_1 = get_history_dropdown_choices(dev_1)
        choices_2 = get_history_dropdown_choices(dev_2)

        # Device 1 should only see t1
        assert any(t1.task_id in c for c in choices_1)
        assert not any(t2.task_id in c for c in choices_1)

        # Device 2 should only see t2
        assert any(t2.task_id in c for c in choices_2)
        assert not any(t1.task_id in c for c in choices_2)

    def test_on_select_history_item_isolation(self, tmp_path):
        """Tests that selecting a history item belongs only to the requesting device."""
        dev_1 = "device_user_1"
        dev_2 = "device_user_2"

        v1 = tmp_path / "v1.mp4"
        v1.write_bytes(b"v1")
        t1 = task_manager.create_task("T2V", "Video One", {}, device_id=dev_1)
        t1.status = "completed"
        t1.video_path = str(v1)

        # Device 1 accesses its own item -> succeeds
        vid_path, info_md = on_select_history_item(t1.task_id, device_id=dev_1)
        assert vid_path == str(v1)
        assert "Video One" in info_md

        # Device 2 tries to access Device 1's item -> blocked
        vid_path_blocked, info_md_blocked = on_select_history_item(t1.task_id, device_id=dev_2)
        assert vid_path_blocked is None
        assert "找不到該影片檔案" in info_md_blocked

    def test_browser_state_persistent_secret(self):
        """
        Tests that BrowserState uses a persistent secret key across restarts,
        preventing device_id from regenerating upon app updates/restarts.
        """
        from app import device_id_state, session_task_state, DEVICE_STORAGE_SECRET
        assert DEVICE_STORAGE_SECRET == "minimax_h3_device_secret_2026"
        assert device_id_state.secret == "minimax_h3_device_secret_2026"
        assert session_task_state.secret == "minimax_h3_device_secret_2026"


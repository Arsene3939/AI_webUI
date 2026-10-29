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

    def test_restore_state_legacy_quality_choices(self):
        """Tests that legacy quality string (e.g. '1 (0.5 MP - 極速)') is normalized on restore without crash."""
        from config import QUALITY_CHOICES
        dev_id = "device_test_legacy_quality"
        params = {
            "prompt": "Legacy prompt",
            "quality_level": "1 (0.5 MP - 極速)",
            "aspect_ratio": "16:9 橫向風景 (1344 x 768)",
            "sampler": "unknown_sampler",
            "scheduler": "unknown_scheduler",
        }
        task = task_manager.create_task("I2V", params["prompt"], params, device_id=dev_id)
        ret = restore_device_state(dev_id, task.task_id)

        # Check I2V quality update (output index 8)
        quality_update = ret[8]
        val = quality_update.get("value") if isinstance(quality_update, dict) else quality_update
        assert val in QUALITY_CHOICES, f"Restored quality {val} must be in QUALITY_CHOICES"

        # Check I2V aspect ratio update (output index 7)
        ar_update = ret[7]
        ar_val = ar_update.get("value") if isinstance(ar_update, dict) else ar_update
        assert ar_val == "16:9 (橫向風景)"

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
        # I2V (14 components):
        # 4: first_frame, 5: last_frame, 6: prompt, 7: ar, 8: quality_level,
        # 9: duration, 10: seed, 11: steps, 12: denoise, 13: fps, 14: sampler, 15: scheduler,
        # 16: status, 17: output_video
        i2v_first_frame = ret[4]
        i2v_last_frame = ret[5]
        i2v_prompt = ret[6]
        i2v_seed = ret[10]
        i2v_video = ret[17]

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
            "quality_level": "3 (0.6 MP - 流暢體驗)",
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

        # T2V components start at index 4 + 14 = 18
        # 18: prompt, 19: ar, 20: quality_level, 21: duration, 22: seed ... 29: video
        assert extract_val(ret[18]) == "Deep underwater coral reef with luminescent fish"
        assert extract_val(ret[22]) == 888
        assert extract_val(ret[29]) == str(dummy_video)

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

        # R2V components start at index 4 + 14 + 12 = 30
        # 30: prompt, 31: ref_video, 32: ref_audio, 33..36: img1..4, 37: size,
        # 38: ar, 39: quality_level, 40: duration, 41: seed ... 48: video
        assert extract_val(ret[30]) == "Stylized animation of an ancient temple"
        assert extract_val(ret[41]) == 999
        assert extract_val(ret[48]) == str(dummy_video)

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

    def test_on_delete_history_item(self, tmp_path):
        """Tests deleting a history item via UI callback updates dropdown choices and gallery (Spec Task 7)."""
        from app import on_delete_history_item, on_select_history_item
        dev = "dev_delete_ui_test"

        v1 = tmp_path / "v1.mp4"
        v1.write_bytes(b"v1")
        t1 = task_manager.create_task("T2V", "Video 1 to keep", {}, device_id=dev)
        t1.status = "completed"
        t1.video_path = str(v1)

        v2 = tmp_path / "v2.mp4"
        v2.write_bytes(b"v2")
        t2 = task_manager.create_task("T2V", "Video 2 to delete", {}, device_id=dev)
        t2.status = "completed"
        t2.video_path = str(v2)

        # Delete t2
        updated_dropdown, new_video, new_info = on_delete_history_item(t2.task_id, device_id=dev)
        choices = updated_dropdown.get("choices") if isinstance(updated_dropdown, dict) else getattr(updated_dropdown, "choices", [])

        # t2 is gone, t1 remains
        assert not any(t2.task_id in str(c) for c in choices)
        assert any(t1.task_id in str(c) for c in choices)
        assert new_video == str(v1)

        # Now delete t1 (last remaining)
        updated_dropdown_empty, empty_video, empty_info = on_delete_history_item(t1.task_id, device_id=dev)
        choices_empty = updated_dropdown_empty.get("choices") if isinstance(updated_dropdown_empty, dict) else getattr(updated_dropdown_empty, "choices", [])
        assert any("暫無歷史紀錄" in str(c) for c in choices_empty)
        assert empty_video is None

    def test_browser_state_persistent_secret(self):
        """
        Tests that BrowserState uses a persistent secret key across restarts,
        preventing device_id from regenerating upon app updates/restarts.
        """
        from app import device_id_state, session_task_state, DEVICE_STORAGE_SECRET
        assert DEVICE_STORAGE_SECRET == "minimax_h3_device_secret_2026"
        assert device_id_state.secret == "minimax_h3_device_secret_2026"
        assert session_task_state.secret == "minimax_h3_device_secret_2026"

    def test_build_progress_html(self):
        """Tests yellow progress bar HTML builder and step percentage calculation."""
        from app import build_progress_html
        from task_manager import Task

        # 1. Plain string message (initial state)
        html_init = build_progress_html("🟢 準備就緒")
        assert "0%" in html_init
        assert "background-color: #ffffff" in html_init
        assert "#eab308" in html_init

        # 2. In-progress task with steps (13/20 = 65%)
        t_running = Task("task_prog_1", "I2V", "prompt", {}, device_id="dev_prog")
        t_running.step = 13
        t_running.total_steps = 20
        t_running.status = "running"
        t_running.message = "⚡ 影片生成中: 13/20 步 (耗時 25秒)"

        html_running = build_progress_html(t_running)
        assert "65%" in html_running
        assert "width: 65%" in html_running
        assert "background-color: #ffffff" in html_running
        assert "#eab308" in html_running

        # 3. Completed task (100%)
        t_completed = Task("task_prog_2", "I2V", "prompt", {}, device_id="dev_prog")
        t_completed.status = "completed"
        t_completed.message = "✅ 影片生成完成！耗時 1分10秒"

        html_completed = build_progress_html(t_completed)
        assert "100%" in html_completed
        assert "width: 100%" in html_completed

        # 4. Preprocessing task (0% with pre-processing status message displayed above bar)
        t_pre = Task("task_prog_3", "I2V", "prompt", {}, device_id="dev_prog")
        t_pre.status = "running"
        t_pre.stage = "preprocessing"
        t_pre.step = 0
        t_pre.total_steps = 0
        t_pre.message = "⚡ 前處理中：正在載入模型... (耗時 12秒)"

        html_pre = build_progress_html(t_pre)
        assert "0%" in html_pre
        assert "width: 0%" in html_pre
        assert "⚡ 前處理中：正在載入模型... (耗時 12秒)" in html_pre

        # 5. Postprocessing task (100% with post-processing status message displayed above bar)
        t_post = Task("task_prog_4", "I2V", "prompt", {}, device_id="dev_prog")
        t_post.status = "running"
        t_post.stage = "postprocessing"
        t_post.step = 20
        t_post.total_steps = 20
        t_post.message = "⚡ 後處理中：正在合成影片... (耗時 1分15秒)"

        html_post = build_progress_html(t_post)
        assert "100%" in html_post
        assert "width: 100%" in html_post
        assert "⚡ 後處理中：正在合成影片... (耗時 1分15秒)" in html_post

        # 6. Verify 2 lines of vertical space allocated (Spec 10)
        assert "min-height: 2.7em" in html_post
        assert "-webkit-line-clamp: 2" in html_post

    def test_dropdowns_disable_filtering_and_custom_values(self):
        """Ensures all dropdowns in app.py have filterable=False to prevent mobile keyboard popup (Spec 9)."""
        import app
        dropdowns = [
            app.i2v_aspect_ratio,
            app.i2v_quality_level,
            app.i2v_sampler,
            app.i2v_scheduler,
            app.t2v_aspect_ratio,
            app.t2v_quality_level,
            app.t2v_sampler,
            app.t2v_scheduler,
            app.r2v_aspect_ratio,
            app.r2v_quality_level,
            app.r2v_sampler,
            app.r2v_scheduler,
            app.history_dropdown,
        ]
        for dd in dropdowns:
            assert dd.filterable is False, f"Dropdown {dd.label} must have filterable=False"

    def test_switch_manual_device_id(self):
        """Tests manually entering a remembered Device ID (Spec 8)."""
        from app import switch_manual_device_id, all_restored_outputs

        # 1. Switch to short 6-digit ID
        res = switch_manual_device_id("71c8f5", None, None)
        assert len(all_restored_outputs) == 55
        assert len(res) == len(all_restored_outputs) + 1  # 1 (edit_row) + 55 outputs
        edit_row_update = res[0]
        assigned_id = res[1]
        header_update = res[3]

        assert edit_row_update.get("visible") is False
        assert "value" not in edit_row_update  # Ensure gr.Row does not receive invalid value prop
        assert assigned_id == "dev_71c8f5"
        assert "ID:71c8f5" in header_update

        # 2. Empty input cancels without resetting current device
        res_empty = switch_manual_device_id("", "dev_current", None)
        assert res_empty[0].get("visible") is False
        assert "value" not in res_empty[0]
        assert res_empty[1] == "dev_current"

    def test_auto_poll_task_progress_completion(self, tmp_path):
        """Tests that poll_active_task_progress detects background task completion and delivers video (Spec Task 2)."""
        from app import poll_active_task_progress, _device_last_reported_completed

        dev_id = "test_dev_auto_poll"
        _device_last_reported_completed.pop(dev_id, None)

        dummy_vid = tmp_path / "polled_video.mp4"
        dummy_vid.write_bytes(b"dummy_video_bytes")

        # Create running task
        task = task_manager.create_task("I2V", "A glowing lantern in the dark", {}, device_id=dev_id)
        task.status = "running"
        task.step = 10
        task.total_steps = 20

        # Poll while running
        res_running = poll_active_task_progress(dev_id, task.task_id)
        task_id_out, i2v_st, i2v_vid = res_running[0], res_running[1], res_running[2]
        assert task_id_out == task.task_id
        # Video is still gr.update() because not completed yet
        assert i2v_vid.get("value") is None if isinstance(i2v_vid, dict) else True

        # Now simulate task completing in background
        task.status = "completed"
        task.video_path = str(dummy_vid)
        task.message = "✅ 影片生成完成！"

        # Poll should detect completion and deliver video
        res_done = poll_active_task_progress(dev_id, task.task_id)
        done_task_id, done_st, done_vid = res_done[0], res_done[1], res_done[2]
        assert done_task_id == task.task_id
        assert "✅ 影片生成完成！" in str(done_st)
        assert done_vid == str(dummy_vid)

        # Subsequent poll tick should be a no-op so video player isn't interrupted
        res_subsequent = poll_active_task_progress(dev_id, task.task_id)
        sub_vid = res_subsequent[2]
        assert sub_vid.get("value") is None if isinstance(sub_vid, dict) else True

    def test_interrupt_task_on_re_generate(self):
        """Tests that interrupt_device_tasks terminates older task when a new generation starts (Spec Task 1)."""
        dev_id = "test_dev_preempt"
        t1 = task_manager.create_task("T2V", "First task", {}, device_id=dev_id)
        t1.status = "running"

        assert not t1.cancel_event.is_set()

        # Simulate user pressing generate again
        interrupted = task_manager.interrupt_device_tasks(device_id=dev_id)
        assert t1.task_id in interrupted
        assert t1.cancel_event.is_set()
        assert t1.status == "interrupted"
        assert "中斷" in t1.message

    def test_handle_stop_generate(self):
        """Tests that clicking stop button halts active device task and restores button visibility (Spec 1)."""
        from app import handle_stop_generate
        dev_id = "test_dev_stop_action"
        t1 = task_manager.create_task("I2V", "Task to stop", {}, device_id=dev_id)
        t1.status = "running"
        assert not t1.cancel_event.is_set()

        st_html, gen_btn_up, stop_btn_up = handle_stop_generate(dev_id)
        assert t1.cancel_event.is_set()
        assert t1.status == "interrupted"
        assert "手動中斷" in st_html
        assert gen_btn_up.get("visible") is True
        assert stop_btn_up.get("visible") is False

    def test_no_custom_dimensions_or_models_in_ui(self):
        """Ensures custom_w, custom_h and model textboxes are not present in UI (Spec Tasks 3 & 4)."""
        import app
        # Ensure custom_w, custom_h, unet, clip, video_vae, audio_vae are not defined on app
        for attr in ["i2v_custom_w", "i2v_custom_h", "t2v_custom_w", "t2v_custom_h", "r2v_custom_w", "r2v_custom_h",
                     "i2v_unet", "i2v_clip", "i2v_v_vae", "i2v_a_vae"]:
            assert not hasattr(app, attr), f"app should not define {attr}"

    def test_adaptive_aspect_ratio_ui_logic(self, tmp_path):
        """Ensures UI supports '原圖比例 (自動對齊)' and accurately aligns without distortion (Spec Task 6)."""
        import app
        from config import ORIGINAL_RATIO_LABEL, I2V_ASPECT_RATIOS, T2V_ASPECT_RATIOS
        from PIL import Image

        assert ORIGINAL_RATIO_LABEL in I2V_ASPECT_RATIOS
        assert ORIGINAL_RATIO_LABEL not in T2V_ASPECT_RATIOS

        # Create a test 3:2 image (1500 x 1000)
        img_file = tmp_path / "test_3_2.png"
        im = Image.new("RGB", (1500, 1000), color=(100, 150, 200))
        im.save(img_file)

        # 1. Test on_first_frame_change triggers ORIGINAL_RATIO_LABEL and calculates 1248 x 832
        ar_up, res_info, badge = app.on_first_frame_change(str(img_file), "5 (1.0 MP - 標準推薦)")
        ar_val = ar_up.get("value") if isinstance(ar_up, dict) else getattr(ar_up, "value", None)
        assert ar_val == ORIGINAL_RATIO_LABEL
        assert "1248 x 832" in res_info
        assert "原始尺寸：`1500 x 1000`" in badge

        # 2. Test on_resolution_change with ORIGINAL_RATIO_LABEL and img_file
        res_info_changed = app.on_resolution_change(ORIGINAL_RATIO_LABEL, "5 (1.0 MP - 標準推薦)", img_path=str(img_file))
        assert "1248 x 832" in res_info_changed

        # 3. Test on_resolution_change without image gracefully falls back
        res_info_no_img = app.on_resolution_change(ORIGINAL_RATIO_LABEL, "5 (1.0 MP - 標準推薦)", img_path=None)
        assert "1344 x 736" in res_info_no_img

    def test_launch_webui_port_occupied_diagnosis(self, capsys):
        """Tests that launch_webui displays diagnostic guidance and refuses to randomly switch ports (Spec 12)."""
        import socket
        import pytest
        from app import launch_webui

        test_port = 7885
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", test_port))
        sock.listen(5)

        try:
            # Expect OSError when raise_on_error=True
            with pytest.raises(OSError) as exc_info:
                launch_webui(port=test_port, raise_on_error=True)

            assert f"Port {test_port} is already in use" in str(exc_info.value)

            # Check printed troubleshooting guide
            captured = capsys.readouterr()
            out = captured.out
            assert f"連接埠 {test_port} 已被佔用" in out
            assert "排查診斷資訊" in out
            assert "伺服器管理員排查與解決步驟" in out
            assert "taskkill /PID" in out
            assert f"netstat -ano | findstr :{test_port}" in out
        finally:
            sock.close()

    def test_server_status_flag_maintenance_and_ok(self):
        """Tests that SERVER_STATUS_UPDATING shows maintenance banner and pauses generation, while OK restores it."""
        from config import SERVER_STATUS_OK, SERVER_STATUS_UPDATING, set_server_status, get_server_status
        from app import build_header_html, handle_i2v_generate

        try:
            # 1. Test UPDATING status
            set_server_status(SERVER_STATUS_UPDATING)
            assert get_server_status() == SERVER_STATUS_UPDATING

            # Header displays maintenance banner
            header_updating = build_header_html("dev_test_status")
            assert "🔧 伺服器維護/更新中" in header_updating

            # Generation yields maintenance warning and stops
            gen_res = list(handle_i2v_generate(
                first_frame="dummy.png",
                last_frame=None,
                prompt="Test prompt",
                aspect_ratio="16:9 (橫向風景)",
                quality_level="5 (1.0 MP - 標準推薦)",
                duration=2.0,
                seed=42,
                steps=20,
                denoise=1.0,
                sampler="res_multistep",
                scheduler="simple",
                fps=24,
                current_session_task=None,
                device_id="dev_test_status",
            ))
            assert len(gen_res) == 1
            status_html, out_video, sess_task, dev_id = gen_res[0]
            assert "⚠️ 伺服器維護/更新中，暫停提交生成任務" in status_html

            # 2. Test OK status
            set_server_status(SERVER_STATUS_OK)
            assert get_server_status() == SERVER_STATUS_OK

            header_ok = build_header_html("dev_test_status")
            assert "🔧 伺服器維護/更新中" not in header_ok

        finally:
            set_server_status(SERVER_STATUS_OK)

    def test_super_user_permission_and_admin_operations(self):
        """Tests Super User detection from localhost and admin operations."""
        from unittest.mock import MagicMock
        from app import (
            is_super_user,
            check_super_user_visibility,
            build_admin_status_badge,
            build_admin_hw_dashboard_html,
            build_admin_queue_html,
            build_admin_devices_html,
            get_admin_device_filter_choices,
            get_admin_tasks_dropdown_choices,
            on_toggle_server_status,
            on_select_admin_task,
            on_delete_admin_task,
            on_clean_failed_tasks,
        )
        from config import SERVER_STATUS_OK, SERVER_STATUS_UPDATING, set_server_status, get_lan_ip

        # 1. Super User detection
        # Unknown / None request must strictly default to False (safe default)
        assert is_super_user(None) is False

        req_local = MagicMock()
        req_local.client.host = "127.0.0.1"
        assert is_super_user(req_local) is True

        # Mobile device connected via Wi-Fi (e.g. 192.168.0.11) must NOT be Super User
        req_phone = MagicMock()
        req_phone.client.host = "192.168.0.11"
        assert is_super_user(req_phone) is False

        req_lan = MagicMock()
        req_lan.client.host = "192.168.1.50"
        assert is_super_user(req_lan) is False

        # Host machine's own LAN IP is recognized as local
        req_host = MagicMock()
        req_host.client.host = get_lan_ip()
        assert is_super_user(req_host) is True

        # Page-load dynamic visibility updates
        assert check_super_user_visibility(req_local) == {"__type__": "update", "visible": True}
        assert check_super_user_visibility(req_phone) == {"__type__": "update", "visible": False}

        # Gradio special_args type hint injection validation
        from gradio.helpers import special_args
        injected, _, _, _ = special_args(check_super_user_visibility, inputs=[], request=req_phone)
        assert len(injected) == 1 and injected[0] is req_phone

        # 2. Status badge & Toggle
        set_server_status(SERVER_STATUS_OK)
        badge_ok = build_admin_status_badge()
        assert "正常服務中" in badge_ok

        badge_up, btn_up, msg_up = on_toggle_server_status(req_local)
        assert "維護更新中" in badge_up
        assert "恢復正常服務" in btn_up["value"]

        # LAN user cannot toggle status
        _, _, msg_denied = on_toggle_server_status(req_lan)
        assert "權限不足" in msg_denied

        # Restore to OK
        set_server_status(SERVER_STATUS_OK)

        # 3. Hardware Dashboard HTML
        hw_html = build_admin_hw_dashboard_html()
        assert "記憶體" in hw_html
        assert "GPU" in hw_html
        assert "磁碟" in hw_html

        # 4. Queue HTML & Devices HTML
        q_html = build_admin_queue_html()
        assert "佇列" in q_html or "運算" in q_html or "ComfyUI" in q_html

        # 5. Admin Task Filtering and Deletion across devices
        t1 = task_manager.create_task("I2V", "Admin task dev 1", {"steps": 10}, device_id="dev_user_1")
        t2 = task_manager.create_task("T2V", "Admin task dev 2", {"steps": 15}, device_id="dev_user_2")
        t2.status = "failed"

        dev_html = build_admin_devices_html()
        assert "裝置代碼" in dev_html

        all_choices = get_admin_tasks_dropdown_choices("全部裝置", "全部狀態")
        assert any(t1.task_id == val for _, val in all_choices)
        assert any(t2.task_id == val for _, val in all_choices)

        # Admin selects task to view parameters
        video_p, info_md = on_select_admin_task(t1.task_id, req_local)
        assert "Admin task dev 1" in info_md
        assert "dev_user_1" in info_md

        # Admin clean failed tasks
        up_choices, _, clean_msg, _ = on_clean_failed_tasks("全部裝置", "全部狀態", req_local)
        assert "已清除" in clean_msg
        assert task_manager.get_task(t2.task_id) is None

        # Admin delete specific task
        on_delete_admin_task(t1.task_id, "全部裝置", "全部狀態", req_local)
        assert task_manager.get_task(t1.task_id) is None


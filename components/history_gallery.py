"""
History gallery UI component with device-isolated historical tasks, video player, and details.
"""
import os
import time
from typing import List, Tuple, Optional
import gradio as gr
from task_manager import task_manager


def get_history_dropdown_choices(device_id: Optional[str]) -> List[Tuple[str, str]]:
    """Returns dropdown choices for completed tasks belonging to the specified device."""
    if not device_id:
        return [("— 暫無歷史紀錄 —", "")]
    completed = task_manager.get_completed_tasks_for_device(device_id)
    if not completed:
        return [("— 暫無歷史紀錄 —", "")]
    choices = []
    for t in completed:
        t_str = time.strftime("%m/%d %H:%M", time.localtime(t.created_at))
        short_prompt = (t.prompt[:30] + "...") if len(t.prompt) > 30 else t.prompt
        label = f"[{t.task_type}] {t_str} | {short_prompt}"
        choices.append((label, t.task_id))
    return choices


def on_select_history_item(selected_task_id: str, device_id: Optional[str]) -> Tuple[Optional[str], str]:
    """Loads video path and markdown info for selected historical task."""
    if not selected_task_id:
        return None, "請選擇上方任務"
    task = task_manager.get_task(selected_task_id, device_id=device_id)
    if not task or not task.video_path or not os.path.exists(task.video_path):
        return None, "⚠️ 找不到該影片檔案"

    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task.created_at))
    info_md = f"""
    ### 📜 任務詳細資料
    * **任務類型**：`{task.task_type}`
    * **建立時間**：{t_str}
    * **生成耗時**：{task.elapsed} 秒
    * **檔案名稱**：`{os.path.basename(task.video_path)}`
    * **提示詞**：
    ```text
    {task.prompt}
    ```
    """
    return task.video_path, info_md


def on_delete_history_item(selected_task_id: str, device_id: Optional[str]):
    """Deletes the selected historical task, cleans up storage, and refreshes the gallery."""
    if not selected_task_id:
        choices = get_history_dropdown_choices(device_id)
        return gr.update(choices=choices), None, "選擇上方任務查看詳細資訊與播放。"

    task_manager.delete_task(selected_task_id, device_id=device_id)
    choices = get_history_dropdown_choices(device_id)
    new_value = choices[0][1] if choices and choices[0][1] else ""

    if new_value:
        new_video, new_info = on_select_history_item(new_value, device_id)
        return gr.update(choices=choices, value=new_value), new_video, new_info
    else:
        return gr.update(choices=choices, value=""), None, "選擇上方任務查看詳細資訊與播放。"


class HistoryGalleryComponent:
    """Encapsulates history gallery tab and events."""

    def __init__(self):
        self.refresh_btn: Optional[gr.Button] = None
        self.dropdown: Optional[gr.Dropdown] = None
        self.delete_btn: Optional[gr.Button] = None
        self.video_preview: Optional[gr.Video] = None
        self.task_info: Optional[gr.Markdown] = None

    def render(self) -> "HistoryGalleryComponent":
        with gr.Row():
            self.refresh_btn = gr.Button("🔄 刷新歷史紀錄", variant="secondary", scale=1)
            self.dropdown = gr.Dropdown(
                choices=get_history_dropdown_choices(None),
                value="",
                label="選取歷史任務",
                scale=6,
                filterable=False,
                allow_custom_value=False,
            )
            self.delete_btn = gr.Button("🗑️ 刪除此紀錄", variant="stop", scale=1)

        with gr.Row():
            with gr.Column(scale=1):
                self.video_preview = gr.Video(label="影片播放", autoplay=False)
            with gr.Column(scale=1):
                self.task_info = gr.Markdown("選擇上方任務查看詳細資訊與播放。")
        return self

    def register_events(self, device_id_state: gr.BrowserState):
        """Binds history dropdown selection, refresh, and delete handlers."""
        def handle_refresh(device_id):
            choices = get_history_dropdown_choices(device_id)
            val = choices[0][1] if choices and choices[0][1] else ""
            if val:
                vid, info = on_select_history_item(val, device_id)
                return gr.update(choices=choices, value=val), vid, info
            return gr.update(choices=choices, value=""), None, "選擇上方任務查看詳細資訊與播放。"

        self.refresh_btn.click(
            handle_refresh,
            inputs=[device_id_state],
            outputs=[self.dropdown, self.video_preview, self.task_info],
        )

        self.dropdown.change(
            on_select_history_item,
            inputs=[self.dropdown, device_id_state],
            outputs=[self.video_preview, self.task_info],
        )

        self.delete_btn.click(
            on_delete_history_item,
            inputs=[self.dropdown, device_id_state],
            outputs=[self.dropdown, self.video_preview, self.task_info],
        )

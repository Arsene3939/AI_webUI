"""
History gallery UI component with device-isolated historical tasks, video player, and details.
"""
import os
import time
from typing import List, Tuple, Optional
import gradio as gr
from task_manager import task_manager


def get_history_dropdown_choices(
    device_id: Optional[str],
    task_type: Optional[str] = None,
    module: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Returns dropdown choices for completed tasks belonging to the specified device.
    Filters by owning module ('minimax'/'upscaler') when given, so each module's gallery
    never shows other modules' records; single task_type filter kept for compatibility.
    Failed/interrupted records (newest 15) are also listed with ❌/⚠️ markers so a job that
    died (backend offline, manual stop, backend restart) never silently disappears from view."""
    if not device_id:
        return [("— 暫無歷史紀錄 —", "")]
    completed = task_manager.get_completed_tasks_for_device(device_id, module=module)
    if task_type:
        completed = [t for t in completed if t.task_type == task_type]
    unfinished = task_manager.get_unfinished_tasks_for_device(device_id, module=module)
    if task_type:
        unfinished = [t for t in unfinished if t.task_type == task_type]
    unfinished = unfinished[:15]
    if not completed and not unfinished:
        return [("— 暫無歷史紀錄 —", "")]
    choices = []
    for t in completed:
        t_str = time.strftime("%m/%d %H:%M", time.localtime(t.created_at))
        short_prompt = (t.prompt[:30] + "...") if len(t.prompt) > 30 else t.prompt
        label = f"[{t.task_type}] {t_str} | {short_prompt}"
        choices.append((label, t.task_id))
    for t in unfinished:
        t_str = time.strftime("%m/%d %H:%M", time.localtime(t.created_at))
        short_prompt = (t.prompt[:30] + "...") if len(t.prompt) > 30 else t.prompt
        icon = "⚠️" if t.status == "interrupted" else "❌"
        label = f"{icon} [{t.task_type}] {t_str} | {short_prompt}"
        choices.append((label, t.task_id))
    return choices


def on_select_history_item(selected_task_id: str, device_id: Optional[str]) -> Tuple[Optional[str], str]:
    """Loads video path and markdown info for selected historical task."""
    if not selected_task_id:
        return None, "請選擇上方任務"
    task = task_manager.get_task(selected_task_id, device_id=device_id)
    if not task:
        return None, "⚠️ 找不到該影片檔案"

    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task.created_at))

    # Failed/interrupted job: no video to show, but surface the record and its stop reason
    # instead of pretending the entry doesn't exist (Spec 2026-10-31 task 2).
    if task.status in ("failed", "interrupted"):
        status_label = "已中斷" if task.status == "interrupted" else "失敗"
        info_md = f"""
        ### 📜 任務詳細資料（{status_label}）
        * **任務類型**：`{task.task_type}`
        * **建立時間**：{t_str}
        * **狀態**：{status_label}（進行到 {task.step}/{task.total_steps} 步）
        * **說明**：{task.message}
        * **提示詞**：
        ```text
        {task.prompt}
        ```
        """
        return None, info_md

    if not task.video_path or not os.path.exists(task.video_path):
        return None, "⚠️ 找不到該影片檔案"
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


def on_delete_history_item(
    selected_task_id: str,
    device_id: Optional[str],
    task_type: Optional[str] = None,
    module: Optional[str] = None,
):
    """Deletes the selected historical task, cleans up storage, and refreshes the gallery."""
    if not selected_task_id:
        choices = get_history_dropdown_choices(device_id, task_type=task_type, module=module)
        return gr.update(choices=choices), None, "選擇上方任務查看詳細資訊與播放。"

    task_manager.delete_task(selected_task_id, device_id=device_id)
    choices = get_history_dropdown_choices(device_id, task_type=task_type, module=module)
    new_value = choices[0][1] if choices and choices[0][1] else ""

    if new_value:
        new_video, new_info = on_select_history_item(new_value, device_id)
        return gr.update(choices=choices, value=new_value), new_video, new_info
    else:
        return gr.update(choices=choices, value=""), None, "選擇上方任務查看詳細資訊與播放。"


class HistoryGalleryComponent:
    """Encapsulates history gallery tab and events.
    `module` ("minimax"/"upscaler") scopes the gallery to one module's tasks;
    `task_type` remains for single-type filtering/backward compatibility."""

    def __init__(self, task_type: Optional[str] = None, module: Optional[str] = None):
        self.task_type = task_type
        self.module = module
        self.refresh_btn: Optional[gr.Button] = None
        self.dropdown: Optional[gr.Dropdown] = None
        self.delete_btn: Optional[gr.Button] = None
        self.video_preview: Optional[gr.Video] = None
        self.task_info: Optional[gr.Markdown] = None

    def render(self) -> "HistoryGalleryComponent":
        with gr.Row():
            self.refresh_btn = gr.Button("🔄 刷新歷史紀錄", variant="secondary", scale=1)
            self.dropdown = gr.Dropdown(
                choices=get_history_dropdown_choices(None, task_type=self.task_type, module=self.module),
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
            choices = get_history_dropdown_choices(device_id, task_type=self.task_type, module=self.module)
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

        def handle_delete(selected_task_id, device_id):
            return on_delete_history_item(selected_task_id, device_id, task_type=self.task_type, module=self.module)

        self.delete_btn.click(
            handle_delete,
            inputs=[self.dropdown, device_id_state],
            outputs=[self.dropdown, self.video_preview, self.task_info],
        )

"""
MiniMax-H3 administrator tab with global cross-device task history management.
Inherits ComfyUIAdminTab.
"""
from typing import Optional, Any
import gradio as gr
from core.comfy_admin_tab import ComfyUIAdminTab
from core.admin_manager import AdminManager


class MiniMaxAdminTab(ComfyUIAdminTab):
    """
    MiniMax administrator tab.
    Inherits all ComfyUI backend and server management features, and adds:
    - Cross-device task filtering by device and status
    - Global task parameter inspection and preview
    - Task deletion and failed tasks cleanup
    """

    def __init__(self):
        super().__init__(tab_title="⚙️ 管理員專區 (Super User)")
        self.device_filter: Optional[gr.Dropdown] = None
        self.status_filter: Optional[gr.Dropdown] = None
        self.refresh_all_tasks_btn: Optional[gr.Button] = None
        self.clean_failed_btn: Optional[gr.Button] = None
        self.all_tasks_dropdown: Optional[gr.Dropdown] = None
        self.delete_task_btn: Optional[gr.Button] = None
        self.video_preview: Optional[gr.Video] = None
        self.task_detail: Optional[gr.Markdown] = None

    def render_comfy_content(self, session_ctx: Any) -> None:
        """Injects cross-device task history management specific to MiniMax-H3."""
        gr.Markdown("### 🗂️ 全域跨裝置任務歷史紀錄")
        with gr.Row():
            self.device_filter = gr.Dropdown(
                choices=AdminManager.get_admin_device_filter_choices(),
                value="全部裝置",
                label="篩選裝置",
                filterable=False,
                allow_custom_value=False,
                scale=3,
            )
            self.status_filter = gr.Dropdown(
                choices=["全部狀態", "已完成", "生成中/排隊中", "失敗/中斷"],
                value="全部狀態",
                label="篩選狀態",
                filterable=False,
                allow_custom_value=False,
                scale=3,
            )
            self.refresh_all_tasks_btn = gr.Button("🔄 刷新列表", variant="secondary", scale=1)
            self.clean_failed_btn = gr.Button("🧹 一鍵清理失敗與中斷任務", variant="secondary", scale=2)

        init_choices = AdminManager.get_admin_tasks_dropdown_choices("全部裝置", "全部狀態")
        with gr.Row():
            self.all_tasks_dropdown = gr.Dropdown(
                choices=init_choices,
                value=init_choices[0][1] if init_choices else "",
                label="選取歷史任務 (全部裝置)",
                filterable=False,
                allow_custom_value=False,
                scale=8,
            )
            self.delete_task_btn = gr.Button("🗑️ 刪除此任務", variant="stop", scale=2)

        with gr.Row():
            with gr.Column(scale=1):
                self.video_preview = gr.Video(label="產出影片預覽", autoplay=False)
            with gr.Column(scale=1):
                self.task_detail = gr.Markdown("請從上方選取任務檢視詳細參數")

    def register_comfy_events(self, session_ctx: Any) -> None:
        """Binds task filtering, selection, and deletion event listeners."""
        for trigger in [self.device_filter.change, self.status_filter.change, self.refresh_all_tasks_btn.click]:
            trigger(
                AdminManager.get_admin_tasks_dropdown_choices,
                inputs=[self.device_filter, self.status_filter],
                outputs=[self.all_tasks_dropdown],
            )

        self.all_tasks_dropdown.change(
            AdminManager.on_select_admin_task,
            inputs=[self.all_tasks_dropdown],
            outputs=[self.video_preview, self.task_detail],
        )
        self.delete_task_btn.click(
            AdminManager.on_delete_admin_task,
            inputs=[self.all_tasks_dropdown, self.device_filter, self.status_filter],
            outputs=[self.all_tasks_dropdown, self.video_preview, self.task_detail, self.device_filter],
        )
        self.clean_failed_btn.click(
            AdminManager.on_clean_failed_tasks,
            inputs=[self.device_filter, self.status_filter],
            outputs=[self.all_tasks_dropdown, self.video_preview, self.task_detail, self.device_filter],
        )

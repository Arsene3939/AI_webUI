"""
Video player output card and progress bar component.
"""
from typing import Optional, Any
import gradio as gr


def build_progress_html(task_or_msg: Any) -> str:
    """
    Renders a yellow progress bar on a white background with direct step percentage.
    Calculates percentage strictly based on sampling steps.
    """
    if isinstance(task_or_msg, str):
        msg = task_or_msg or "🟢 準備就緒"
        pct = 100 if "完成" in msg or "成功" in msg else 0
    elif task_or_msg is None:
        msg = "🟢 準備就緒"
        pct = 0
    else:
        task = task_or_msg
        msg = getattr(task, "message", "") or "🟢 準備就緒"
        status = getattr(task, "status", "")
        stage = getattr(task, "stage", "")
        step = getattr(task, "step", 0)
        total_steps = getattr(task, "total_steps", 0)

        if status == "completed":
            pct = 100
        elif stage == "postprocessing" or (total_steps > 0 and step >= total_steps):
            pct = 100
        elif total_steps > 0:
            pct = max(0, min(100, int(round((step / total_steps) * 100))))
        else:
            pct = 0

    return f"""
    <div style="width: 100%; margin-bottom: 8px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="display: flex; justify-content: space-between; align-items: center; min-height: 44px; margin-bottom: 6px; font-size: 0.9rem; font-weight: 500; color: #334155; box-sizing: border-box;">
            <div style="flex: 1; min-width: 0; min-height: 2.7em; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; word-break: break-word; padding-right: 8px;">{msg}</div>
            <div style="flex-shrink: 0; font-weight: 700; color: #b45309; font-size: 0.95rem; line-height: 1.35;">{pct}%</div>
        </div>
        <div style="width: 100%; height: 26px; background-color: #ffffff; border: 1.5px solid #cbd5e1; border-radius: 6px; overflow: hidden; position: relative; box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);">
            <div style="width: {pct}%; height: 100%; background: linear-gradient(90deg, #fde047 0%, #eab308 100%); transition: width 0.3s ease;"></div>
            <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: 700; color: #0f172a; text-shadow: 0 0 2px rgba(255,255,255,0.7);">
                {pct}%
            </div>
        </div>
    </div>
    """


class VideoPlayerCardComponent:
    """Encapsulates status progress bar, recover button, and video output player."""

    def __init__(self, label: str = "生成影片"):
        self.label = label
        self.status: Optional[gr.HTML] = None
        self.recover_btn: Optional[gr.Button] = None
        self.output_video: Optional[gr.Video] = None

    def render(self) -> "VideoPlayerCardComponent":
        with gr.Column(scale=1):
            self.status = gr.HTML(build_progress_html("🟢 準備就緒"))
            self.recover_btn = gr.Button("🔄 恢復上次輸入與成果", variant="secondary", elem_classes=["recover-btn"])
            self.output_video = gr.Video(label=self.label, autoplay=True, interactive=False)
        return self


class ActionButtonsComponent:
    """Encapsulates primary generate button and stop generation button."""

    def __init__(self, generate_label: str = "🚀 開始生成影片"):
        self.generate_label = generate_label
        self.generate_btn: Optional[gr.Button] = None
        self.stop_btn: Optional[gr.Button] = None

    def render(self) -> "ActionButtonsComponent":
        with gr.Row():
            self.generate_btn = gr.Button(
                self.generate_label,
                variant="primary",
                elem_classes=["primary-btn"],
                visible=True,
            )
            self.stop_btn = gr.Button("🛑 停止生成", variant="stop", visible=False)
        return self

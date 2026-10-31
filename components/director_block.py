"""
"Film Director" block component (Spec 2026-11-01 task 1).

Embedded inside each MiniMax tab next to the prompt textbox: the user writes a
plain-language wish; the block uses the tab's own first-frame/reference image,
asks the director model for a professional prompt, and can apply it into the
tab's prompt field with one click.

User-facing copy stays free of developer jargon (VLM/graph/node never appear);
model & language selection live collapsed under 進階設定 per spec.
"""
from typing import Any, Optional

import gradio as gr

from config import get_director_models
from core.director_client import call_director

NOT_READY = "導演尚未就緒：管理員放好導演模型後，選項會在這裡自動出現"
THINKING = "🎬 導演構思中…（第一次請導演吃飯會久一點，請稍候）"


def refresh_model_choices(current, last_seen):
    """定時重掃目錄後要推給前端的更新（清單沒變 → 全部 no-op，零刷新）。

    Returns (model_dropdown, output_box, status_html, new_scan_state).
    """
    models = get_director_models()
    if models == list(last_seen):
        return gr.update(), gr.update(), gr.update(), last_seen
    keep = current if current in models else (models[0] if models else None)
    return (
        gr.update(choices=models, value=keep, interactive=bool(models)),
        gr.update(visible=bool(models)),
        "" if models else f'<div class="director-warn">⚠️ {NOT_READY}</div>',
        models,
    )


class DirectorBlockComponent:
    def __init__(self):
        self.brief: Optional[gr.Textbox] = None
        self.generate_btn: Optional[gr.Button] = None
        self.status: Optional[gr.HTML] = None
        self.output: Optional[gr.Textbox] = None
        self.apply_btn: Optional[gr.Button] = None
        self.model_dropdown: Optional[gr.Dropdown] = None
        self.language_dropdown: Optional[gr.Dropdown] = None
        self.clean_prompt_state: Optional[gr.State] = None
        self.advanced_acc: Optional[gr.Accordion] = None
        self.model_timer: Optional[gr.Timer] = None
        self.model_scan_state: Optional[gr.State] = None

    def render(self) -> "DirectorBlockComponent":
        models = get_director_models()
        # 模型清單即時偵測：每 5 秒重掃一次目錄（放 Accordion 外層，確保摺疊時
        # 仍會_tick_；見 register_events 的「清單變了才更新前端」邏輯）
        self.model_timer = gr.Timer(value=5.0)
        with gr.Accordion("🎬 影片導演", open=False, elem_classes=["director-accordion"]):
            self.brief = gr.Textbox(
                label="跟導演說你想拍什麼",
                placeholder="大白話就行，例：「讓她慢慢轉頭，鏡頭輕輕推近，逆光感覺」",
                lines=2,
            )
            self.generate_btn = gr.Button("✨ 請導演寫提示詞", variant="secondary")
            self.status = gr.HTML(
                "" if models else f'<div class="director-warn">⚠️ {NOT_READY}</div>',
                elem_classes=["backend-status-box"],
            )
            self.output = gr.Textbox(label="導演成品", lines=4, interactive=True, visible=bool(models))
            self.apply_btn = gr.Button("✅ 套用到生成提示詞", variant="primary", visible=False)
            self.clean_prompt_state = gr.State("")
            self.model_scan_state = gr.State(list(models))

            with gr.Accordion("進階設定（導演模型／輸出語言）", open=False) as self.advanced_acc:
                self.model_dropdown = gr.Dropdown(
                    choices=models,
                    value=(models[0] if models else None),
                    label="導演模型",
                    filterable=False,
                    interactive=bool(models),
                    allow_custom_value=False,
                )
                self.language_dropdown = gr.Dropdown(
                    choices=[
                        ("中文說明 ＋ 英文提示詞", "zh_en"),
                        ("English only", "en"),
                    ],
                    value="zh_en",
                    label="輸出語言",
                    filterable=False,
                    interactive=True,
                    allow_custom_value=False,
                )
        return self

    def register_events(self, image_ref: Any, prompt_ref: Any) -> None:
        """Wires the director flow against the owning tab's image & prompt fields."""

        def run_director(brief, image_path, language, model):
            # streaming handler: first yield paints the busy state instantly,
            # then the blocking director call runs and we paint the result.
            yield (
                f'<div class="director-thinking">{THINKING}</div>',
                gr.update(),
                gr.update(visible=False),
                "",
            )
            ok, note, result = call_director(
                brief=brief,
                image_path=image_path,
                model_name=model,
                language=language,
            )
            if ok:
                display = f"📝 {note}\n\n{result}" if note else result
                status_html = '<div class="director-ok">✅ 導演完成 — 可直接編輯，滿意就套用</div>'
                yield status_html, gr.update(value=display, visible=True), gr.update(visible=True), result
            else:
                yield (
                    f'<div class="director-warn">⚠️ {result}</div>',
                    gr.update(),
                    gr.update(visible=False),
                    "",
                )

        self.generate_btn.click(
            run_director,
            inputs=[self.brief, image_ref, self.language_dropdown, self.model_dropdown],
            outputs=[self.status, self.output, self.apply_btn, self.clean_prompt_state],
            api_name="director_generate",
            concurrency_limit=None,
        )

        def apply_to_prompt(clean_prompt):
            if not clean_prompt:
                return gr.update(), gr.update()
            return (
                gr.update(value=clean_prompt),
                '<div class="director-ok">✅ 已套用到生成提示詞，可再手動微調</div>',
            )

        self.apply_btn.click(
            apply_to_prompt,
            inputs=[self.clean_prompt_state],
            outputs=[prompt_ref, self.status],
        )

        # 放好模型檔後網頁免重啟：定時重掃目錄，只有清單真的變化時才刷新前端
        # （下拉選項、成品框可見度、狀態行提示）。清單沒變 → 全 no-op，零閃爍。
        self.model_timer.tick(
            refresh_model_choices,
            inputs=[self.model_dropdown, self.model_scan_state],
            outputs=[self.model_dropdown, self.output, self.status, self.model_scan_state],
            api_name=False,
        )

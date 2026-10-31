"""
「優化提示詞」區塊（Spec 2026-10-31 UI 簡化案，前身＝🎬影片導演區塊）。

極簡互動：按鈕就躺在本 tab「提示詞」欄正下方；一點即把該欄現值交給導演
打磨成成品並直接覆寫回該欄。模型選擇位於本 tab 的「⚙️ 進階參數」
（VideoParamsComponent.director_model），語言／風格不再提供選項
（統一系統提示詞，管理員可編輯）。

User-facing copy stays free of developer jargon (VLM/graph/node never appear).
"""
import html
from typing import Any, Optional

import gradio as gr

from config import get_director_models
from core.director_client import call_director

NOT_READY = "導演尚未就緒：管理員放好導演模型後，選項會在「⚙️ 進階參數」自動出現"
THINKING = "🎬 導演努力思考中…"


def warn_html(text: str) -> str:
    # 狀態行是 HTML：任何來自模型/後端/使用者原文的片段都先跳脫，避免注入。
    return f'<div class="director-warn">⚠️ {html.escape(str(text), quote=False)}</div>'


def refresh_model_choices(current, last_seen):
    """定時重掃目錄後推給前端的更新（清單沒變 → 全部 no-op，零刷新）。

    Returns (model_dropdown_update, status_update, new_scan_state).
    下拉元件本體住在 tab 的進階參數區（VideoParamsComponent），這裡只負責刷新它。
    """
    models = get_director_models()
    if models == list(last_seen):
        return gr.update(), gr.update(), last_seen
    keep = current if current in models else (models[0] if models else None)
    return (
        gr.update(choices=models, value=keep, interactive=bool(models)),
        gr.update(value="" if models else warn_html(NOT_READY)),
        models,
    )


class DirectorBlockComponent:
    def __init__(self):
        self.generate_btn: Optional[gr.Button] = None
        self.status: Optional[gr.HTML] = None
        self.model_timer: Optional[gr.Timer] = None
        self.model_scan_state: Optional[gr.State] = None

    def render(self) -> "DirectorBlockComponent":
        models = get_director_models()
        # 模型清單即時偵測：每 5 秒重掃一次目錄（見 register_events 的
        # 「清單變了才更新前端」邏輯；沒變就不會觸發任何前端刷新）
        self.model_timer = gr.Timer(value=5.0)
        self.generate_btn = gr.Button("✨ 優化提示詞", variant="secondary")
        self.status = gr.HTML(
            warn_html(NOT_READY) if not models else "",
            elem_classes=["backend-status-box"],
        )
        self.model_scan_state = gr.State(list(models))
        return self

    def register_events(self, image_ref: Any, prompt_ref: Any, model_ref: Any) -> None:
        """Wires the one-click optimize flow against the owning tab's
        prompt field, first-frame image, and the 進階參數 director model dropdown."""

        def run_director(prompt_text, image_path, model):
            original = (prompt_text or "").strip()
            if not original:
                yield warn_html("請先在提示詞欄寫下你的想法，再讓導演幫你打磨"), gr.update()
                return
            # streaming handler: first yield paints the busy state instantly,
            # then the blocking director call runs and we paint the result.
            yield f'<div class="director-thinking">{THINKING}</div>', gr.update()
            ok, _note, result = call_director(
                brief=original,
                image_path=image_path,
                model_name=model,
            )
            if ok:
                yield (
                    f'<div class="director-ok">✅ 提示詞優化完成，原提示詞：'
                    f'{html.escape(original, quote=False)}</div>',
                    gr.update(value=result),
                )
            else:
                yield warn_html(result), gr.update()

        self.generate_btn.click(
            run_director,
            inputs=[prompt_ref, image_ref, model_ref],
            outputs=[self.status, prompt_ref],
            api_name="director_generate",
            concurrency_limit=None,
        )

        # 放好模型檔後網頁免重啟：定時重掃目錄，只有清單真的變化時才刷新
        # 進階參數區的模型下拉與狀態行。清單沒變 → 全 no-op，零閃爍。
        self.model_timer.tick(
            refresh_model_choices,
            inputs=[model_ref, self.model_scan_state],
            outputs=[model_ref, self.status, self.model_scan_state],
            api_name=False,
        )

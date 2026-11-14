"""minimax 區塊的 UI 文案（Spec 2026-11-03 任務 5；常數以 MINIMAX_ / DIRECTOR_ 前綴命名）。

涵蓋 MiniMax 主視圖與三個生成 tab（views/minimax/view.py、tabs/i2v_tab.py、
tabs/t2v_tab.py、tabs/r2v_tab.py）、共用水準參數卡（components/video_params.py）
與「優化提示詞」導演區塊（components/director_block.py、core/director_client.py）
回傳給 UI 的中文訊息。

沿用其他分組檔的既有共用常數（不在本檔重複定義）：
・管理頁（views/minimax/admin_tab.py）文案 → ui_text/admin.py 的 ADMIN_*；
・「生成影片」「🚀 開始生成影片」「⚠️ 任務已被手動中斷」 → ui_text/upscaler.py 的 TASK_*。
任務篩選值（全部裝置／全部狀態／已完成／生成中/排隊中／失敗/中斷）是
task_manager 以字面值比對的協定值，刻意留在來源檔（見 admin.py 邊界說明）。

含 {} 的模板由呼叫端 .format(...) 組回；值與遷移前逐字節完全相同
（測試與 e2e 以這些字串斷言）。
"""
from config import DIRECTOR_STRATA_LABEL

# ── 主視圖與分頁標籤（views/minimax/view.py、tabs/*.py）───────────────────
MINIMAX_TAB_HISTORY = "📜 歷史紀錄"
MINIMAX_TAB_I2V = "🖼️ 圖生影片 (I2V)"
MINIMAX_TAB_T2V = "✍️ 文生影片 (T2V)"
MINIMAX_TAB_R2V = "🎬 參考生影片 (R2V)"

# ── 提示詞欄與參考素材區塊（tabs/*.py）───────────────────────────────────
MINIMAX_PROMPT_LABEL = "提示詞"
MINIMAX_I2V_PROMPT_PLACEHOLDER = "描述畫面的動態、角色動作、鏡頭運動與音效（支援中英文）..."
MINIMAX_T2V_PROMPT_PLACEHOLDER = "描述想生成的場景、運鏡、角色動態、氛圍與背景音樂/音效..."
MINIMAX_R2V_PROMPT_PLACEHOLDER = "描述如何結合參考素材（支援主體、動作、風格混合）..."
MINIMAX_I2V_FIRST_FRAME_LABEL = "首幀圖片"
MINIMAX_I2V_LAST_FRAME_LABEL = "尾幀圖片 (選填)"
MINIMAX_R2V_MEDIA_ACCORDION = "📎 參考影音素材 (選填)"
MINIMAX_R2V_REF_VIDEO_LABEL = "參考影片"
MINIMAX_R2V_REF_AUDIO_LABEL = "參考音訊"
MINIMAX_R2V_IMAGES_ACCORDION = "🖼️ 參考圖片素材 (1~4 張選填)"
MINIMAX_R2V_REF_IMG_LABEL_FMT = "參考圖 {}"  # 呼叫端 .format(1..4)
MINIMAX_R2V_IMG_SIZE_LABEL = "參考圖縮放模式"
MINIMAX_R2V_IMG_SIZE_INFO = "match: 保持原始比例切齊；pad: 黑邊補齊"

# ── 生成流程狀態訊息（tabs/*.py yield 給播放器狀態列）────────────────────
MINIMAX_MSG_SERVER_UPDATING = "⚠️ 伺服器維護/更新中，暫停提交生成任務"
MINIMAX_MSG_NEED_PROMPT = "❌ 請輸入提示詞"
MINIMAX_MSG_NEED_FIRST_FRAME = "❌ 請上傳首幀圖片"
MINIMAX_MSG_UPLOADING_IMAGE = "⚡ 前處理中：正在上傳圖片..."
MINIMAX_MSG_UPLOAD_IMAGE_FAILED = "❌ 上傳圖片失敗: 檢查後端是否已啟動({})"  # 呼叫端 .format(例外訊息)
MINIMAX_MSG_UPLOADING_REF_MEDIA = "⚡ 前處理中：正在上傳參考素材..."
MINIMAX_MSG_UPLOAD_REF_IMG_FAILED = "❌ 上傳參考圖失敗: {}"
MINIMAX_MSG_UPLOAD_REF_VIDEO_FAILED = "❌ 上傳參考影片失敗: {}"
MINIMAX_MSG_UPLOAD_REF_AUDIO_FAILED = "❌ 上傳參考音訊失敗: {}"
MINIMAX_MSG_PREPARING = "⚡ 前處理中：正在準備生成..."

# ── 輸出解析度顯示（i2v on_first_frame_change、video_params on_resolution_change）
MINIMAX_RES_INFO_FMT = "📐 **輸出解析度**：`{} x {}` (~{} MP)"  # 呼叫端 .format(w, h, actual_mp)
MINIMAX_RES_INFO_DEFAULT = "📐 **輸出解析度**：`1344 x 768` (~1.03 MP)"
MINIMAX_ORIG_SIZE_BADGE_FMT = "💡 *原始尺寸：`{} x {}`*"  # 呼叫端 .format(orig_w, orig_h)
MINIMAX_MSG_RES_DETECT_FAILED = "⚠️ 圖片解析度偵測失敗: {}"

# ── 共用水準參數卡（components/video_params.py）──────────────────────────
MINIMAX_ASPECT_RATIO_LABEL = "長寬比"
MINIMAX_QUALITY_LABEL = "畫質等級"
MINIMAX_DURATION_LABEL = "影片時長 (秒)"
MINIMAX_STEPS_LABEL = "取樣步數"
MINIMAX_ADVANCED_ACCORDION = "⚙️ 進階參數"
MINIMAX_SEED_LABEL = "隨機種子"
MINIMAX_RANDOM_SEED_BTN = "🎲 隨機"
MINIMAX_DENOISE_LABEL = "去噪強度"
MINIMAX_SAMPLER_LABEL = "取樣器"
MINIMAX_SCHEDULER_LABEL = "調度器"
MINIMAX_MODEL_SECTION_MD = "🧠 **生成模型**（管理員限定；一般使用者一律使用預設模型）"
MINIMAX_MODEL_UNET_LABEL = "生成模型 (UNET)"
MINIMAX_MODEL_CLIP_LABEL = "文字Encoding模型 (CLIP)"
MINIMAX_MODEL_VIDEO_VAE_LABEL = "影像 VAE"
MINIMAX_MODEL_AUDIO_VAE_LABEL = "音訊 VAE"

# ── 「優化提示詞」導演區塊（components/director_block.py）────────────────
DIRECTOR_OPTIMIZE_BTN = "✨ 優化提示詞"
DIRECTOR_THINKING = "🎬 導演努力思考中…"
DIRECTOR_THINKING_HTML = f'<div class="director-thinking">{DIRECTOR_THINKING}</div>'
DIRECTOR_NEED_BRIEF = "請先在提示詞欄寫下你的想法，再讓導演幫你打磨"
DIRECTOR_NOT_READY = (
    f"目前只有「{DIRECTOR_STRATA_LABEL}」可用"
)
DIRECTOR_WARN_HTML = '<div class="director-warn">⚠️ {}</div>'  # 呼叫端 html.escape 後再 .format
DIRECTOR_OK_ORIGINAL_HTML = (
    '<div class="director-ok">✅ 提示詞優化完成，原提示詞：{}</div>'  # 呼叫端 .format(已跳脫的原文)
)
DIRECTOR_MODEL_LABEL = "導演模型"
DIRECTOR_MODEL_INFO = (
    "「優化提示詞」按鈕使用的導演模型；「" + DIRECTOR_STRATA_LABEL +
    "」要先到 💬 Strata 頁啟動助理模型；放好新模型後清單會自動更新"
)

# ── 導演客戶端回傳訊息（core/director_client.py；(False, "", 中文訊息) 第三元素）
DIRECTOR_MSG_MAINTENANCE = "⚠️ 伺服器維護中，導演暫時休息，請稍後再試"
DIRECTOR_MSG_NO_MODEL = (
    f"目前沒有可用的導演模型：請先下載導演模型，或改選「{DIRECTOR_STRATA_LABEL}」"
)
DIRECTOR_MSG_BACKEND_OFFLINE = "⚠️ 後端模型沒上線：請先按頁面上方的「啟動後端模型」再試一次"
DIRECTOR_MSG_IMAGE_UPLOAD_FAILED = "參考圖片上傳失敗，請確認後端是否正常後再試一次"
DIRECTOR_MSG_QUEUE_FAILED = "導演工作送件失敗，請稍後再試"
DIRECTOR_MSG_OOM = "显存不夠，導演無法上工：請先關閉佔用显存的程式再試，或請管理員改用較小的導演模型"
DIRECTOR_MSG_RUNTIME = "導演執行時發生問題，請洽管理員查看後端記錄"
DIRECTOR_MSG_TIMEOUT = "導演思考太久沒回應（可能模型太大或後端太忙），請稍後再試或改用較小的導演模型"
DIRECTOR_MSG_STRATA_OFFLINE = (
    "Strata 助理目前沒開著：請先到 💬 Strata 頁按「啟動助理模型」，"
    "或回到「⚙️ 進階參數」改用其他導演模型"
)
DIRECTOR_MSG_STRATA_FAILED_FMT = "Strata 導演無法完成：{}"  # 呼叫端 .format(sc.chat_collect 錯誤)
DIRECTOR_MSG_STRATA_FAILED = "Strata 導演無法完成，請稍後再試"

"""strata 區塊的 UI 文案（由對應負責人填入；常數一律以 STRATA_ 前綴命名）。

涵蓋 /strata 頁：對話頁（views/strata/view.py）、管理專區（views/strata/admin_tab.py）、
助理 toolbar（components/strata_toolbar.py）與助理客戶端回傳訊息（core/strata_client.py）。
"""

# ── 對話頁：系統提示詞與工作類型模板（模板鍵＝下拉選單可見標籤）──────────
STRATA_DEFAULT_CHAT_SYSTEM_PROMPT = (
    "你是這台電腦上的智慧助理 Strata，負責協助 MiniMax 影片創作與日常問題。"
    "回答用繁體中文，條理清楚、重點先講。"
)
STRATA_TEMPLATE_GENERAL = "💬 一般對話"
STRATA_TEMPLATE_STORYBOARD = "🎬 影片分鏡腳本"
STRATA_TEMPLATE_PROMPT_POLISH = "✨ 提示詞打磨"
STRATA_TEMPLATE_SCRIPT = "✍️ 劇本寫作"
STRATA_CHAT_TEMPLATES = {
    STRATA_TEMPLATE_GENERAL: STRATA_DEFAULT_CHAT_SYSTEM_PROMPT,
    STRATA_TEMPLATE_STORYBOARD: (
        "你是資深影片導演。把使用者的想法整理成短短的分鏡腳本（鏡頭、動作、氛圍），"
        "並附上一段可直接餵給影片生成模型的英文提示詞。回答用繁體中文，"
        "英文提示詞標明【English Prompt】。"
    ),
    STRATA_TEMPLATE_PROMPT_POLISH: (
        "你是提示詞工程師。把使用者給的提示詞草稿改寫成具體、有鏡頭語言與光影細節的"
        "英文視覺提示詞，並用一兩行中文說明你做了哪些調整。"
    ),
    STRATA_TEMPLATE_SCRIPT: (
        "你是編劇協作夥伴：協助發展角色、場景、節奏與對白，必要時給出多個版本供選擇。"
        "回答用繁體中文。"
    ),
}
STRATA_NOT_UP_MSG = "🟡 助理模型還沒啟動：請先按畫面上方的「啟動助理模型」，啟動完成後再傳訊息。"

# ── 對話頁：gr 元件標籤／占位文字／Markdown ─────────────────────────────
STRATA_TAB_CHAT = "💬 智慧對話助理"
STRATA_PAGE_TITLE_MD = "### 💬 Strata 智慧助理系統"
STRATA_PAGE_DESC_MD = "本機的大模型助手：日常問答、影片點子、分鏡與創意都能聊，也能幫你打磨影片用的提示詞。"
STRATA_CHATBOT_LABEL = "對話歷史"
STRATA_MSG_PLACEHOLDER = "輸入想詢問的問題或影片想法（按 Enter 發送）..."
STRATA_MSG_INPUT_LABEL = "輸入訊息"
STRATA_SEND_BTN = "傳送"
STRATA_CLEAR_BTN = "清除"
STRATA_IMAGE_ACCORDION = "🖼️ 參考圖片（可選）"
STRATA_IMAGE_LABEL = "附上圖片，助理會一起看"
STRATA_SETTINGS_ACCORDION = "⚙️ 助理設定"
STRATA_TEMPLATE_DD_LABEL = "工作類型"
STRATA_TEMPLATE_DD_INFO = "選一個工作類型，助理的回答風格會跟著切換"
STRATA_SYS_PROMPT_LABEL = "助理的角色設定"
STRATA_TEMP_LABEL = "創意度"

# ── 對話流程：助理訊息區的回覆提示 ──────────────────────────────────────
STRATA_IMAGE_NOTE = "（本次圖片未解讀，僅依文字回答）"
STRATA_EMPTY_REPLY_NOTE = "（助理這次沒有回答內容，請稍後再試）"

# ── 管理專區：標籤、按鈕與即時狀態（含 {} 模板）────────────────────────
STRATA_ADMIN_TAB_TITLE = "⚙️ Strata 助理管理專區"
STRATA_ADMIN_HEADING_MD = "### 💬 Strata 助理設定"
STRATA_ADMIN_DESC_MD = "這台電腦上助理模型的連線設定；一般状况不用改。调整後按下儲存，立即生效。"
STRATA_API_BASE_LABEL = "助理服務位址"
STRATA_API_BASE_PLACEHOLDER = "例如 http://127.0.0.1:8080"
STRATA_API_KEY_LABEL = "助理金鑰（選填）"
STRATA_API_KEY_PLACEHOLDER = "若助理設了金鑰才需填寫..."
STRATA_SAVE_CONN_BTN = "💾 儲存設定"
STRATA_REFRESH_STATUS_BTN = "🔄 檢查助理狀態"
STRATA_NO_PERM_MSG = "⛔ 您沒有管理權限，無法變更助理設定。"
STRATA_SAVE_OK_MD = "✅ {}\n\n{}"  # 呼叫端 .format(設定訊息, 助理即時狀態 Markdown)
STRATA_STATUS_OFF_MD = (
    "🔴 助理模型目前未在運作：可在頁面上方按「啟動助理模型」，或由管理員從 Strata 控制台啟動。"
)
STRATA_MODEL_RUNNING = "🟢 助理模型運作中"  # 管理頁狀態首行與 toolbar 按鈕共用
STRATA_STATUS_MODEL_LINE = "- 使用模型：{}"
STRATA_STATUS_CTX_LINE = "- 一次能記得的對話量：約 {:,} 個字以內"  # 呼叫端 .format(int(ctx))
STRATA_STATUS_VISION_ON = "- 圖片解讀：✅ 可看圖"
STRATA_STATUS_VISION_OFF = "- 圖片解讀：目前未開啟（對話仍可附文字）"

# ── 助理 toolbar：按鈕文字與狀態列訊息 ─────────────────────────────────
STRATA_CHECK_BTN = "⚡ 檢查助理模型狀態..."
STRATA_STOP_BTN = "🛑"
STRATA_BTN_STARTING = "🟡 正在啟動助理模型..."
STRATA_BTN_START = "⚡ 啟動助理模型"
STRATA_GATE_MAINT_MSG = "⚠️ 伺服器維護/更新中，暫停啟動助理模型"
STRATA_ALREADY_RUNNING_MSG = "🟢 助理模型已經在運作中，無須重複啟動"  # toolbar 與 start_backend 共用
STRATA_START_RESOURCE_HINT = (
    "\n\n💡 若「啟動後端模型」顯示運作中，可能是它正在使用中；"
    "可先到該頁面關閉後端模型，或稍後再試"
)
STRATA_STARTING_MSG = "🟡 正在啟動助理模型，第一次啟動會花 1～2 分鐘載入模型，請稍候..."

# ── 助理客戶端：chat_stream／chat_collect／啟動停止的回傳訊息 ──────────
STRATA_ERR_TIMEOUT = "⚠️ 助理回答太久沒有回應，請稍後再試"
STRATA_ERR_NOT_CONNECTED = "🔴 連不到助理模型：請先按上方「啟動助理模型」，或稍後再試"
STRATA_ERR_BUSY = "⚠️ 助理正在回答其他問題，請等它回答完再送出"
STRATA_ERR_UNAVAILABLE = "⚠️ 助理暫時無法回答，請稍後再試"
STRATA_ERR_STREAM_CUT = "⚠️ 與助理的連線中斷了（助理可能剛被關閉），請稍後再試"
STRATA_ERR_STREAM_GENERIC = "⚠️ 助理回答發生問題，請稍後再試"
STRATA_ERR_EMPTY_ANSWER = "⚠️ 助理沒有回答出內容，請稍後再試"
STRATA_ERR_CLI_MISSING = "❌ 找不到助理模型的啟動程式，請洽管理員確認 Strata 已正確安裝"
STRATA_ERR_START_FAILED = "❌ 助理模型啟動失敗，請洽管理員查看 Strata 記錄"
STRATA_START_ONLINE_MSG = "🟢 助理模型已上線，可以開始對話與導演"
STRATA_START_LATE_MSG = (
    "⚠️ 助理模型啟動後迟迟沒上線：可能還在載入，請稍後再按一次，或洽管理員查看 Strata 記錄"
)
STRATA_ERR_STOP_FAILED = "❌ 助理模型停止失敗，請洽管理員查看 Strata 記錄"
STRATA_STOPPED_MSG = "🛑 助理模型已關閉"
STRATA_ERR_STOP_UNABLE = "⚠️ 助理模型目前無法停止，請洽管理員查看 Strata 記錄"

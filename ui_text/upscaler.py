"""
upscaler 頁面的 UI 文案（UPSCALER_ 前綴）＋ 任務管理/進度/歷史紀錄共用的
狀態文案（TASK_ 前綴，Spec 任務 5）。

含數字／變數的訊息以 {} 模板常數存放，呼叫端 .format(...) 組回；
值與遷移前逐字節完全相同（測試與 e2e 以這些字串斷言）。
"""

# ---------------------------------------------------------------------------
# upscaler 頁面（views/upscaler/view.py）
# ---------------------------------------------------------------------------
UPSCALER_TAB_UPSCALE = "🔍 影片超解析放大"
UPSCALER_HEADING = "### 🔍 影片超解析放大 (Video Resolution Upscaler)"
UPSCALER_INTRO = "上傳來源影片，使用神經網路超解析模型無損放大影片畫質，自動保留原始音訊與影格率。"
UPSCALER_INPUT_VIDEO_LABEL = "上傳來源影片"
UPSCALER_MODEL_LABEL = "超解析模型 (upscale_models)"
UPSCALER_REFRESH_BTN = "🔄 重新整理"
UPSCALER_ADVANCED_ACCORDION = "🎛️ 進階輸出設定"
UPSCALER_SCALE_ORIGINAL = "模型原生倍率（不額外縮放）"
UPSCALER_SCALE_HALF = "輸出再縮小至 1/2"
UPSCALER_SCALE_QUARTER = "輸出再縮小至 1/4"
UPSCALER_SCALE_LABEL = "輸出縮放"
UPSCALER_SCALE_INFO = "本機模型都是 4 倍放大；縮小輸出可加快後續處理並減小檔案"
UPSCALER_FORMAT_AUTO = "自動（推薦）"
UPSCALER_FORMAT_LABEL = "輸出格式"
UPSCALER_BITDEPTH_8_LABEL = "8-bit（兼容性最佳）"
UPSCALER_BITDEPTH_10_LABEL = "10-bit（漸層更平滑）"
UPSCALER_BITDEPTH_LABEL = "位元深度"
UPSCALER_BITDEPTH_INFO = "10-bit 色彩漸層較不易出現色帶，部分播放器可能不支援"
UPSCALER_GENERATE_BTN = "🚀 開始影片超解析放大"
UPSCALER_STOP_BTN = "🛑 中斷放大任務"
UPSCALER_OUTPUT_VIDEO_LABEL = "超解析成果影片"
UPSCALER_TAB_HISTORY = "📜 放大紀錄"

# upscaler 生成器進度訊息
UPSCALER_MSG_SERVER_UPDATING = "⚠️ 伺服器維護/更新中，暫停提交放大任務"
UPSCALER_MSG_NO_VIDEO = "❌ 請先上傳欲放大的來源影片"
UPSCALER_MSG_NO_MODEL = "❌ 請先選擇超解析模型"
UPSCALER_MSG_SERVER_OFFLINE = "❌ 後端伺服器離線: {}"
UPSCALER_MSG_UPLOADING = "⚡ 前處理中：正在上傳影片至 ComfyUI 後端..."
UPSCALER_MSG_UPLOAD_FAILED = "❌ 影片上傳失敗: {}"
UPSCALER_MSG_STOPPED = "⚠️ 放大任務已中斷"

# ---------------------------------------------------------------------------
# 生成頁共用元件（components/media_player.py）：進度條／播放器卡片／成對按鈕
# ---------------------------------------------------------------------------
TASK_READY = "🟢 準備就緒"
TASK_OUTPUT_VIDEO_LABEL = "生成影片"
TASK_RECOVER_BTN = "🔄 恢復上次輸入與成果"
TASK_EXTRACT_FRAME_BTN = "🖼️ 提取最後一幀"
TASK_DOWNLOAD_FRAME_BTN = "💾 下載最後一幀"
TASK_FRAME_NO_VIDEO_MSG = "⚠️ 目前沒有可提取的影片，請先生成影片或按上方按鈕恢復上次成果"
TASK_FRAME_FAILED_MSG = "❌ 最後一幀提取失敗，請確認影片檔案完好後再試一次"
TASK_FRAME_READY_MSG = "🖼️ 最後一幀已準備完成，請點擊右側「💾 下載最後一幀」儲存圖片"
TASK_STOP_GEN_BTN = "🛑 停止生成"
TASK_GENERATE_BTN_DEFAULT = "🚀 開始生成影片"

# ---------------------------------------------------------------------------
# 任務狀態／進度訊息（task_manager/manager.py、task_manager/comfy_progress.py）
# 這些 task.message 由輪詢迴圈寫入、經 build_progress_html 顯示給使用者，
# 同時也被 logger 記錄（單一模組一份常數）。
# ---------------------------------------------------------------------------
TASK_MSG_PREPROCESS = "⚡ 前處理中：正在準備提交任務..."
TASK_MSG_SUBMITTING = "⚡ 前處理中：正在提交任務至後端..."
TASK_MSG_QUEUED = "⏳ 排隊中..."
TASK_MSG_QUEUED_SOON = "⏳ 排隊中...（即將提交）"
TASK_MSG_QUEUED_AHEAD = "⏳ 排隊中...（前面還有 {} 個工作）"
TASK_MSG_QUEUED_WAITED = "⏳ 排隊中... (已等待 {})"
TASK_MSG_SUBMIT_FAILED = "❌ 提交失敗: {}"
TASK_MSG_WORKER_ERROR = "❌ 任務執行異常: {}"
TASK_MSG_INTERRUPTED_BY_USER = "⚠️ 任務已被手動中斷"
TASK_MSG_INTERRUPTED_SINGLE = "⚠️ 任務已被中斷"
TASK_MSG_INTERRUPTED_LOOP = "⚠️ 任務已中斷"
TASK_MSG_SAMPLING_STEPS = "⚡ 影片生成中: {}/{} 步"
TASK_MSG_SAMPLING_STEPS_ELAPSED = "⚡ 影片生成中: {}/{} 步 (耗時 {})"
TASK_MSG_SAMPLING_PLAIN = "⚡ 影片生成中..."
TASK_MSG_SAMPLING_PLAIN_ELAPSED = "⚡ 影片生成中... (耗時 {})"
TASK_MSG_LOADING_MODELS = "⚡ 前處理中：正在載入模型... (耗時 {})"
TASK_MSG_COMPOSITING = "⚡ 後處理中：正在合成影片... (耗時 {})"
TASK_MSG_SAVING = "⚡ 後處理中：正在儲存影片... (耗時 {})"
TASK_MSG_COMPLETED = "✅ 影片生成完成！耗時 {}"
TASK_MSG_GEN_FAILED = "❌ 生成失敗，請查看後端錯誤記錄。"
TASK_MSG_BACKEND_OFFLINE = "⚠️ 後端模型已離線，任務已中止（請確認後端後重新提交）"

# 已耗時間可讀格式（UI 訊息與 logger 記錄共用）
TASK_TIME_HMS = "{}小時{}分{}秒"
TASK_TIME_MS = "{}分{}秒"
TASK_TIME_S = "{}秒"

# ---------------------------------------------------------------------------
# 歷史紀錄共用元件（components/history_gallery.py，minimax/upscaler 兩頁共用）
# ---------------------------------------------------------------------------
TASK_HISTORY_EMPTY_CHOICE = "— 暫無歷史紀錄 —"
TASK_HISTORY_LABEL_TEMPLATE = "[{}] {} | {}"
TASK_HISTORY_LABEL_MARKED_TEMPLATE = "{} [{}] {} | {}"
TASK_HISTORY_ICON_INTERRUPTED = "⚠️"
TASK_HISTORY_ICON_FAILED = "❌"
TASK_HISTORY_SELECT_HINT = "請選擇上方任務"
TASK_HISTORY_VIDEO_MISSING = "⚠️ 找不到該影片檔案"
TASK_STATUS_LABEL_INTERRUPTED = "已中斷"
TASK_STATUS_LABEL_FAILED = "失敗"
TASK_HISTORY_DEFAULT_INFO = "選擇上方任務查看詳細資訊與播放。"
TASK_HISTORY_REFRESH_BTN = "🔄 刷新歷史紀錄"
TASK_HISTORY_DROPDOWN_LABEL = "選取歷史任務"
TASK_HISTORY_DELETE_BTN = "🗑️ 刪除此紀錄"
TASK_HISTORY_VIDEO_LABEL = "影片播放"

# 任務詳細資料 Markdown（{} 依序：status_label, task_type, t_str, status_label,
# step, total_steps, message, prompt）
TASK_HISTORY_INFO_FAILED = """
        ### 📜 任務詳細資料（{}）
        * **任務類型**：`{}`
        * **建立時間**：{}
        * **狀態**：{}（進行到 {}/{} 步）
        * **說明**：{}
        * **提示詞**：
        ```text
        {}
        ```
        """

# 完整任務詳細資料 Markdown（{} 依序：task_type, t_str, elapsed, 檔案名稱, prompt）
TASK_HISTORY_INFO_DONE = """
    ### 📜 任務詳細資料
    * **任務類型**：`{}`
    * **建立時間**：{}
    * **生成耗時**：{} 秒
    * **檔案名稱**：`{}`
    * **提示詞**：
    ```text
    {}
    ```
    """

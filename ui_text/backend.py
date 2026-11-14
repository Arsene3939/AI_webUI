"""backend 區塊的 UI 文案（由對應負責人填入；常數一律以 BACKEND_ 前綴命名）。

涵蓋 ComfyUI 後端 toolbar（components/comfy_toolbar.py）與後端客戶端
（core/comfy_client.py）回傳給工具列／狀態列的中文訊息。
logger 記錄文字與英文註解不在此區。
"""

# ── 後端 toolbar：按鈕文字與狀態列訊息（維護按鈕文案見 ui_text.common）──
BACKEND_CHECK_BTN = "⚡ 檢查後端模型狀態..."
BACKEND_STOP_BTN = "🛑"
BACKEND_BTN_STARTING = "🟡 正在啟動後端模型..."
BACKEND_BTN_RUNNING = "🟢 後端模型運作中"
BACKEND_BTN_START = "⚡ 啟動後端模型"
BACKEND_GATE_MAINT_MSG = "⚠️ 伺服器維護/更新中，暫停啟動後端"
BACKEND_ALREADY_RUNNING_MSG = "🟢 後端模型已經在運作中，無須重複啟動"
BACKEND_STARTING_MSG = "🟡 正在啟動後端模型，請稍候..."
BACKEND_FORCE_STOP_MSG = "🛑 後端模型已強制關閉（已中斷 {} 個進行中的工作）"  # 呼叫端 .format(len(active))
BACKEND_STOP_GUARD_MSG = (
    "⚠️ 無法關閉後端模型：目前仍有 {} 個工作正在排队或生成中，"
    "請等待完成，或先到對應頁面按下停止按鈕"
)  # 呼叫端 .format(len(active))

# ── 客戶端 check_server：連線狀態回傳訊息 ──────────────────────────────
BACKEND_SERVER_ONLINE_MSG = "🟢 ComfyUI 後端運作中"
BACKEND_SERVER_BAD_STATUS_MSG = "🔴 ComfyUI 回應異常 ({})"  # 呼叫端 .format(resp.status_code)
BACKEND_SERVER_OFFLINE_MSG = "🔴 ComfyUI 未連線 (離線中)"

# ── 客戶端 check_system_resources：資源不足警告與原因行模板 ────────────
BACKEND_RES_FAIL_PREFIX = "⚠️ 伺服器運算資源不足："
BACKEND_RES_REASON_RAM = "可用記憶體 {} GB (需 > {:g} GB)"
BACKEND_RES_REASON_GPU_UTIL = "GPU 佔用率 {:.1f}% (需 < {:g}%)"
BACKEND_RES_REASON_VRAM = "可用 GPU 顯存 {} GB (需 > {:g} GB)"

# ── 客戶端 start_comfyui_backend：啟動流程回傳訊息 ─────────────────────
BACKEND_START_ALREADY_MSG = "🟢 後端已經在運作中，無須重複啟動"
BACKEND_START_NO_MAIN_MSG = "❌ 找不到 ComfyUI 核心主程式: {}"  # 呼叫端 .format(main_py)
BACKEND_START_NO_PY_MSG = "❌ 找不到 Python 解譯器: {}"  # 呼叫端 .format(COMFY_PYTHON)
BACKEND_START_SPAWN_FAIL_MSG = "❌ 啟動進程失敗: {}"  # 呼叫端 .format(str(e))
BACKEND_START_READY_MSG = "🟢 後端已成功啟動並就緒！"
BACKEND_START_LOADING_MSG = "⏳ 已送出啟動指令，正在背景載入中，約需 5~10 秒..."

# ── 客戶端 stop_comfyui_backend：停止流程回傳訊息 ──────────────────────
BACKEND_STOP_ALREADY_OFF_MSG = "🔴 後端本來就未在運作中。"
BACKEND_STOP_OK_MSG = "🛑 後端已成功關閉。"
BACKEND_STOP_FAIL_MSG = "⚠️ 嘗試關閉後端失敗，請手動檢查終端機。"

# ── 客戶端上傳／提交／監控下載流程（monitor_download_with_progress 等）──
BACKEND_MSG_FILE_MISSING = "檔案不存在: {}"          # FileNotFoundError 內容（UI 顯示）
BACKEND_MSG_UNKNOWN_ERROR = "未知錯誤"                # error 欄位缺失時的佔位
BACKEND_MSG_QUEUE_REJECT = "ComfyUI 拒絕執行: {} ({})"  # error_msg (node_errors JSON)
BACKEND_MON_FAILED_MSG = "❌ {}"                       # 前一步回傳訊息加叉
BACKEND_MON_SUBMITTING = "📤 正在提交任務..."
BACKEND_MON_SUBMIT_FAILED = "❌ 提交失敗: {}"
BACKEND_MON_QUEUED = "⏳ 已加入排隊隊列 (ID: {}...)"
BACKEND_MON_SAVING = "📥 正在儲存影片..."
BACKEND_MON_SUCCESS = "✅ 影片生成成功！耗時 {} 秒"
BACKEND_MON_SAMPLING = "⚡ 影片生成中... (耗時 {})"
BACKEND_MON_WAITING = "⏳ 排隊中... (已等待 {})"
BACKEND_TIME_HMS = "{}小時{}分{}秒"  # 已耗時間可讀格式（與 task 側同文案）
BACKEND_TIME_MS = "{}分{}秒"
BACKEND_TIME_S = "{}秒"

# ── 客戶端 free／clear：顯存釋放與佇列清空回傳訊息 ─────────────────────
BACKEND_FREE_OK_MSG = "🟢 已成功釋放 GPU 顯存與卸載模型快取"
BACKEND_FREE_STATUS_MSG = "⚠️ 釋放請求回傳狀態碼 {}"
BACKEND_FREE_FAIL_MSG = "❌ 釋放失敗: {}"
BACKEND_CLEAR_OK_MSG = "🟢 已成功清空所有排隊等待中的任務"
BACKEND_CLEAR_STATUS_MSG = "⚠️ 清空佇列回傳狀態碼 {}"
BACKEND_CLEAR_FAIL_MSG = "❌ 清空失敗: {}"

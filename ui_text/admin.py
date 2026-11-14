"""admin 區塊的 UI 文案（管理員專區共用骨架＋各模組管理頁＋AdminManager 回傳訊息）。

涵蓋 core/base_admin_tab.py、core/comfy_admin_tab.py、core/admin_manager.py、
views/minimax/admin_tab.py、views/upscaler/admin_tab.py。
含 IP／數字／狀態值的訊息以 {} 模板常數存放，呼叫端 .format(...) 組回。

任務篩選值（ADMIN_FILTER_*）同時是管理頁下拉文案與 task_manager.get_all_tasks
的比對值，兩邊都 import 同一份常數，不會一邊改字一邊對不上。
刻意留下的技術協定值：「無可移除」是清單佔選的內部偵測標記，不進 ui_text。
"""

# 任務篩選下拉（文案＝比對值，UI 與 task_manager 共用同一份）
ADMIN_FILTER_ALL_DEVICES = "全部裝置"
ADMIN_FILTER_ALL_STATUS = "全部狀態"
ADMIN_FILTER_DONE = "已完成"
ADMIN_FILTER_ACTIVE = "生成中/排隊中"
ADMIN_FILTER_FAILED = "失敗/中斷"

# ── 共用骨架（BaseAdminTab）：分頁標題、區塊標題、按鈕與說明 ──────────────
ADMIN_TAB_TITLE_DEFAULT = "⚙️ 管理員專區"
ADMIN_PAGE_HEADING_MD = "## 🛠️ {}"  # 呼叫端 .format(tab_title)
ADMIN_ACCESS_NOTE_MD = "此分頁僅對本機操作者 (127.0.0.1) 或已授權之管理員 IP 開放。"
ADMIN_SECTION_STATUS_MD = "### 🚦 伺服器服務狀態切換"
ADMIN_TOGGLE_TO_MAINT_BTN = "切換為維護模式"
ADMIN_RESTORE_OK_BTN = "恢復正常服務"
ADMIN_SECTION_HW_MD = "### 🖥️ 硬體資源即時狀態 (Hardware Dashboard)"
ADMIN_REFRESH_HW_BTN = "🔄 刷新硬體狀態"
ADMIN_SECTION_DEVICES_MD = "### 📱 連線裝置總覽"
ADMIN_REFRESH_DEVICES_BTN = "🔄 刷新裝置列表"
ADMIN_SECTION_THRESHOLDS_MD = "### 📏 後端啟動資源門檻"
ADMIN_THRESHOLDS_DESC_MD = "ComfyUI 啟動前的資源檢查標準；調整後按下儲存，下次啟動檢查立即採用新值。"
ADMIN_SLIDER_MIN_RAM_LABEL = "最低可用記憶體 (RAM, GB)"
ADMIN_SLIDER_MAX_GPU_LABEL = "GPU 使用率上限 (%)"
ADMIN_SLIDER_MIN_VRAM_LABEL = "最低可用顯存 (VRAM, GB)"
ADMIN_THRESHOLDS_SAVE_BTN = "💾 儲存門檻設定"
ADMIN_SECTION_IPLIST_MD = "### 🛡️ 管理員名單設定"
ADMIN_IPLIST_DESC_MD = "在下方輸入指定裝置的 IP 位址，加入後該裝置連線時即可直接操作管理員專屬功能。"
ADMIN_IP_ADD_LABEL = "新增管理員 IP"
ADMIN_IP_ADD_PLACEHOLDER = "請輸入欲授權的 IP 位址，例如 192.168.0.11..."
ADMIN_IP_ADD_BTN = "➕ 加入名單"
ADMIN_IP_REMOVE_LABEL = "選取欲移除的管理員 IP"
ADMIN_IP_REMOVE_BTN = "🗑️ 移除此 IP"
ADMIN_SECTION_POWER_MD = "### 💻 電腦電源"
ADMIN_POWER_DESC_MD = (
    "⚠️ 「電腦關機」會關閉這台執行 WebUI 與後端的實體電腦；"
    "按下後有短暫倒數緩衝，期間可點「取消關機」中止。"
)
ADMIN_SHUTDOWN_BTN = "🛑 電腦關機"
ADMIN_CANCEL_SHUTDOWN_BTN = "✋ 取消關機"

# ── ComfyUI 管理專區（ComfyUIAdminTab）──────────────────────────────────
ADMIN_COMFY_TAB_TITLE = "⚙️ ComfyUI 管理專區"
ADMIN_COMFY_BACKEND_SECTION_MD = "### ⚡ ComfyUI 後端與顯存控制"
ADMIN_PURGE_VRAM_BTN = "🧹 立即釋放 GPU 顯存 (Purge VRAM)"
ADMIN_RESTART_BACKEND_BTN = "🔄 重啟 ComfyUI 後端進程"
ADMIN_COMFY_QUEUE_SECTION_MD = "### 📋 ComfyUI 生成佇列 (Queue Status)"
ADMIN_INTERRUPT_TASK_BTN = "🛑 中斷當前運算任務"
ADMIN_CLEAR_QUEUE_BTN = "🗑️ 清空所有等待中排隊佇列"
ADMIN_REFRESH_QUEUE_BTN = "🔄 刷新佇列狀態"

# ── MiniMax 管理頁（全域任務歷史＋導演提示詞）───────────────────────────
ADMIN_MINIMAX_TAB_TITLE = "⚙️ 管理員專區 (Super User)"
ADMIN_MINIMAX_SECTION_HISTORY_MD = "### 🗂️ 全域跨裝置任務歷史紀錄"
ADMIN_FILTER_DEVICE_LABEL = "篩選裝置"
ADMIN_FILTER_STATUS_LABEL = "篩選狀態"
ADMIN_REFRESH_TASKS_BTN = "🔄 刷新列表"
ADMIN_CLEAN_FAILED_BTN = "🧹 一鍵清理失敗與中斷任務"
ADMIN_TASK_PICK_DD_LABEL = "選取歷史任務 (全部裝置)"
ADMIN_DELETE_TASK_BTN = "🗑️ 刪除此任務"
ADMIN_VIDEO_PREVIEW_LABEL = "產出影片預覽"
ADMIN_TASK_DETAIL_INIT_MD = "請從上方選取任務檢視詳細參數"
ADMIN_DIRECTOR_SECTION_MD = "### 🎬 導演系統提示詞"
ADMIN_DIRECTOR_PROMPT_LABEL = "每次「優化提示詞」導演所遵循的指示（直接編輯後儲存，下一次生成立即生效）"
ADMIN_DIRECTOR_RELOAD_BTN = "↺ 從檔案重新載入"
ADMIN_DIRECTOR_SAVE_BTN = "💾 儲存系統提示詞"
ADMIN_DIRECTOR_RELOAD_OK_HTML = '<div class="director-ok">✅ 已從檔案載入最新內容</div>'
ADMIN_DIRECTOR_SAVED_OK_HTML = '<div class="director-ok">✅ {}</div>'  # 呼叫端 .format(save 回傳 msg)

# ── 超解析管理頁（UpscalerAdminTab）────────────────────────────────────
ADMIN_UPSCALER_TAB_TITLE = "⚙️ 超解析管理專區"
ADMIN_UPSCALER_SECTION_MD = "### 🔍 超解析放大模型與緩存管理"
ADMIN_CLEAN_CACHE_BTN = "🧹 清理超解析臨時分塊快取 (Clean Tile Cache)"
ADMIN_CACHE_CLEANED_MSG = "✅ 已清理超解析臨時快取資料夾。"

# ── AdminManager：權限與操作回傳訊息 ──────────────────────────────────
ADMIN_NO_PERM_MSG = "⚠️ 權限不足"
ADMIN_NO_PERM_LOCAL_MSG = "⚠️ 權限不足，僅限本機管理員操作"
ADMIN_NO_PERM_THRESHOLDS_MSG = "⚠️ 權限不足：僅管理員可調整啟動資源門檻"
ADMIN_NO_PERM_SHUTDOWN_MSG = "⚠️ 權限不足：僅管理員可執行電腦關機"
ADMIN_NO_PERM_CANCEL_MSG = "⚠️ 權限不足：僅管理員可取消關機"

ADMIN_STATE_OK_TEXT = "🟢 正常服務中"  # 切換成功訊息的內嵌標籤（維護側共用 COMMON_MAINT_BTN）
ADMIN_TOGGLE_OK_MD = "✅ 已成功切換為：{}"

# 資源門檻儲存後的成功訊息（呼叫端 .format(msg, RAM, GPU, VRAM 現值)）
ADMIN_THRESHOLDS_SAVED_MD = (
    "✅ {}\n\n"
    "目前生效門檻：可用記憶體 **≥ {} GB** ｜ "
    "GPU 使用率 **≤ {}%** ｜ 可用顯存 **≥ {} GB**"
)

ADMIN_RESTART_BUSY_MSG = (
    "⚠️ 無法重啟後端：仍有 {} 個工作在排队或運算中，"
    "請先以「🛑 中斷當前運算任務」與「🗑️ 清空所有等待中排隊佇列」清空後再重啟"
)
ADMIN_INTERRUPTED_MSG = "🛑 已送出中斷請求 (Prompt ID: {})"
ADMIN_QUEUE_NO_TASK_MSG = "目前無正在執行的生成任務"

# 管理頁任務清單：狀態標籤＋下拉選項格式（icon [type] ID | 時間 | 提示詞）
ADMIN_STATUS_DONE_LABEL = "已完成"
ADMIN_STATUS_RUNNING_LABEL = "運算中"
ADMIN_STATUS_QUEUED_LABEL = "排隊中"
ADMIN_STATUS_FAILED_LABEL = "失敗/中斷"
ADMIN_TASK_ICON_DONE = "✅"
ADMIN_TASK_ICON_RUNNING = "⚡"
ADMIN_TASK_ICON_QUEUED = "⏳"
ADMIN_TASK_ICON_FAILED = "❌"
ADMIN_TASK_CHOICE_FMT = "{} [{}] ID:{} | {} | {}"

ADMIN_TASK_PICK_MSG = "請選擇上方任務"
ADMIN_TASK_MISSING_MSG = "⚠️ 找不到該任務紀錄"
ADMIN_TASK_DELETED_MSG = "✅ 任務已成功刪除"
ADMIN_CLEANED_MSG = "🧹 已清除 {} 個失敗或中斷的任務"
ADMIN_NO_TASKS_PLACEHOLDER = "— 查無符合條件的任務 —"
ADMIN_IP_REMOVE_PLACEHOLDER = "— 目前無可移除的管理員 IP —"

# ── 管理員 IP 名單：操作回傳訊息（{} 槽放使用者輸入的 IP）───────────────
ADMIN_IP_EMPTY_MSG = "⚠️ 請輸入有效的 IP 位址"
ADMIN_IP_BAD_FORMAT_MSG = "❌ '{}' 不是正確的 IP 格式 (例如 192.168.0.11)"
ADMIN_IP_IS_LOCAL_MSG = "ℹ️ '{}' 本身已具有本機管理員權限，無需重複加入"
ADMIN_IP_EXISTS_MSG = "ℹ️ IP '{}' 已在管理員名單中"
ADMIN_IP_ADDED_MSG = "✅ 已成功將 IP '{}' 加入管理員名單"
ADMIN_IP_PICK_MSG = "請從選單中選取要移除的管理員 IP"
ADMIN_IP_NOT_IN_LIST_MSG = "⚠️ IP '{}' 不在自訂名單中"
ADMIN_IP_REMOVED_MSG = "✅ 已將 IP '{}' 從管理員名單中移除"

# ── 電腦電源：關機排定／取消的回傳與 OS 倒數提示 ────────────────────────
ADMIN_SHUTDOWN_OS_NOTICE = "AI WebUI 管理員發起的關機（{} 秒後），可在管理頁點「取消關機」中止"
ADMIN_SHUTDOWN_FAIL_MSG = "❌ 無法安排關機：{}"
ADMIN_SHUTDOWN_SCHEDULED_MSG = (
    "🛑 已安排電腦在 **{} 秒後關機**。"
    "要中止請立刻點下方「✋ 取消關機」，或留意畫面上的系統倒數提示。"
)
ADMIN_CANCEL_FAIL_MSG = "❌ 取消關機失敗：{}"
ADMIN_CANCEL_NONE_MSG = "ℹ️ 目前沒有待中止的關機程序{}"  # 呼叫端視情況塞（detail）
ADMIN_CANCEL_OK_MSG = "✅ 已取消待執行的關機，電腦不會關掉。"

# ── AdminManager HTML 建置器：狀態徽章 ──────────────────────────────────
ADMIN_BADGE_OK_HTML = (
    '<div style="padding: 8px 16px; border-radius: 8px; background: #ecfdf5; '
    'border: 1.5px solid #6ee7b7; color: #047857; font-weight: 700; font-size: 0.95rem;">'
    '🟢 系統狀態：正常服務中 (OK)'
    '</div>'
)
ADMIN_BADGE_UPDATING_HTML = (
    '<div style="padding: 8px 16px; border-radius: 8px; background: #fff1f2; '
    'border: 1.5px solid #fda4af; color: #e11d48; font-weight: 700; font-size: 0.95rem;">'
    '🔧 系統狀態：維護更新中 (UPDATING)'
    '</div>'
)

# ── AdminManager HTML 建置器：管理員 IP 名單面板（{} 槽放內網 IP／chips）──
ADMIN_IP_LOCAL_CHIPS_HTML = """
        <span style="display: inline-block; background: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-size: 0.88rem; font-weight: 600; margin: 3px;">127.0.0.1 (本機)</span>
        <span style="display: inline-block; background: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-size: 0.88rem; font-weight: 600; margin: 3px;">{0} (本機內網)</span>
        """
ADMIN_IP_NONE_CHIP_HTML = '<span style="color: #64748b; font-size: 0.88rem; margin-left: 6px;">(目前尚未加入其他管理員 IP)</span>'
ADMIN_IP_CHIP_ADMIN_HTML = '<span style="display: inline-block; background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-size: 0.88rem; font-weight: 600; margin: 3px;">{0}</span>'
ADMIN_IP_LIST_HTML = """
        <div style="background: #ffffff; border: 1.5px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; line-height: 1.8;">
            <div style="font-size: 0.85rem; color: #475569; font-weight: 600; margin-bottom: 6px;">固定本機權限：</div>
            <div>{0}</div>
            <div style="font-size: 0.85rem; color: #475569; font-weight: 600; margin-top: 10px; margin-bottom: 6px;">手動授權的管理員名單：</div>
            <div>{1}</div>
        </div>
        """

# ── AdminManager HTML 建置器：硬體資源面板文字（卡片骨架與配色留呼叫端）──
ADMIN_HW_TITLE_RAM = "🧠 記憶體 (RAM)"
ADMIN_HW_TITLE_GPU = "⚡ GPU 核心負載"
ADMIN_HW_TITLE_VRAM = "🎮 GPU 顯存 (VRAM)"
ADMIN_HW_TITLE_DISK = "💾 輸出磁碟空間"
ADMIN_HW_VAL_USAGE = "{} / {} GB"  # RAM／VRAM 用量列（呼叫端 .format(已用, 總量)）
ADMIN_HW_SUB_FREE = "可用 {} GB ({}%)<br>啟動門檻：可用 ≥ {} GB"  # RAM／VRAM 共用
ADMIN_HW_SUB_GPU = "晶片即時運算佔用<br>啟動門檻：≤ {}%"
ADMIN_HW_VAL_DISK = "{} GB 可用"
ADMIN_HW_SUB_DISK = "總量 {} GB ({}% 已用)"

# ── AdminManager HTML 建置器：生成佇列面板 ──────────────────────────────
ADMIN_QUEUE_OFFLINE_HTML = '<div style="padding: 12px; background: #fff1f2; border: 1.5px solid #fecdd3; border-radius: 8px; color: #e11d48; font-weight: 600;">🔴 ComfyUI 後端未連線</div>'
ADMIN_QUEUE_RUNNING_HTML = '<div style="margin-bottom: 8px; color: #1e293b;">⚡ <b>正在運算任務</b>：<code>{0}</code></div>'
ADMIN_QUEUE_IDLE_HTML = '<div style="margin-bottom: 8px; color: #64748b;">☕ 目前無正在執行的生成任務</div>'
ADMIN_QUEUE_PENDING_HTML = '<div style="color: #1e293b;">⏳ <b>排隊中 ({0} 個)</b>：<ul style="margin: 4px 0 0 18px; padding: 0;">{1}</ul></div>'
ADMIN_QUEUE_PENDING_EMPTY_HTML = '<div style="color: #64748b;">🟢 佇列無排隊中的任務</div>'

# ── AdminManager HTML 建置器：連線裝置總覽表格 ──────────────────────────
ADMIN_DEVICES_EMPTY_HTML = '<div style="padding: 12px; color: #64748b;">暫無連線裝置紀錄</div>'
ADMIN_DEVICES_THEAD_HTML = (
    "<thead>\n"
    '                <tr style="background: #f8fafc; border-bottom: 1.5px solid #e2e8f0; text-align: left; color: #475569;">\n'
    '                    <th style="padding: 10px 12px;">裝置代碼 (Device ID)</th>\n'
    '                    <th style="padding: 10px 12px;">連線 IP</th>\n'
    '                    <th style="padding: 10px 12px;">總任務數</th>\n'
    '                    <th style="padding: 10px 12px;">成功生成</th>\n'
    '                    <th style="padding: 10px 12px;">最後活躍時間</th>\n'
    "                </tr>\n"
    "            </thead>"
)

# ── 任務詳細資料 Markdown（{} 依序：代碼/裝置/類型/狀態/訊息/時間/耗時/
#    寬/高/種子/長度/檔名/提示詞）────────────────────────────────────────
ADMIN_TASK_DETAIL_MD = """
        ### 📜 任務詳細資料 (管理員檢視)
        * **任務代碼**：`{0}`
        * **所屬裝置**：`{1}`
        * **任務類型**：`{2}`
        * **當前狀態**：`{3}` ({4})
        * **建立時間**：{5}
        * **總耗時**：{6} 秒
        * **解析度**：`{7} x {8}`
        * **隨機種子**：`{9}`
        * **影片長度**：`{10} 秒`
        * **產出檔案**：`{11}`
        * **提示詞**：
        ```text
        {12}
        ```
        """

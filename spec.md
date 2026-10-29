# 使用手冊與規範
## 伺服器維護旗標 (`SERVER_STATUS`)，每次開始更動程式碼前要改
- **目的**：
  - 當管理者或開發者需要對伺服器進行更新、模型替換或代碼維護時，可平滑將 WebUI 切換至維護模式，防止使用者在維護期間發送生成請求導致任務異常或損壞。
- **旗標定義與介面 (`config.py`)**：
  - 常數：`SERVER_STATUS_OK = "OK"`, `SERVER_STATUS_UPDATING = "UPDATING"`
  - 全域變數：`SERVER_STATUS`（預設為 `SERVER_STATUS_OK`）
  - 介面函式：`get_server_status() -> str`、`set_server_status(status: str) -> None`
- **使用方式**：
  1. **代碼/配置檔設定**：
     - 在修改代碼前，於 `config.py` 將 `SERVER_STATUS = SERVER_STATUS_UPDATING`。
     - 或在 Python 腳本/控制台中執行：`from config import set_server_status, SERVER_STATUS_UPDATING; set_server_status(SERVER_STATUS_UPDATING)`。
  2. **環境變數設定**：
     - 在啟動伺服器前於終端設定：`set SERVER_STATUS=UPDATING`（Windows）或 `export SERVER_STATUS=UPDATING`（Linux）。
  3. **維護完成後恢復**：
     - 將 `config.py` 改回 `SERVER_STATUS = SERVER_STATUS_OK`，或調用 `set_server_status(SERVER_STATUS_OK)`，或取消環境變數。
## 注意事項
- 應避免UI介面出現過多開發相關字詞，讓使用者只看到他需要看到的東西

# 任務規劃與實作進度：

## 開放super user權限與頁面:
**為super user額外設計一個UI**
- 讓使用`localhost` (跟前端伺服器同一台主機)的使用者作為super user開啟網頁
- 保留原本的所有功能，並新增一個`管理員操作`頁籤

### 身分識別與權限控管機制：
1. **本機連線識別 (Localhost Super User Detection)**：
   - 透過 Gradio 請求物件 (`request: gr.Request`) 讀取客戶端 IP 位址 (`request.client.host`)。
   - 若連線來源為本機主機 (`"127.0.0.1"`, `"::1"`, `"localhost"` 以及本機網卡 IP)，即自動識別為 **Super User（系統管理員）**。
   - 若連線來自手機、外部裝置或區網其他 IP（例如 `192.168.x.x`），則作為 **一般使用者**。
2. **介面動態呈現**：
   - 一般使用者連線時：介面僅呈現原本的 I2V、T2V、R2V 與個人歷史紀錄等標準功能，「管理員操作」頁籤維持隱藏 (`visible=False`)。
   - Super User（本機）開啟時：保留原本的所有功能，並在頁籤最右側展開專屬的「⚙️ 管理員操作」頁籤。
   - 後端安全性：所有管理員操作 API 在後端同步驗證來源 IP，防止外部裝置透過偽造請求直接呼叫管理員介面。

---

### `管理員操作` 頁籤規劃內容：

#### 1. 全域跨裝置歷史紀錄管理 (Global Task Management)
- **跨裝置歷史檢視與篩選**：
  - 突破一般裝置只能查看自身 `device_id` 任務的限制，管理員可調閱全伺服器所有連線裝置生成的歷史紀錄。
  - **裝置篩選下拉選單**：支援切換「所有裝置」或單獨選取特定裝置，聚焦檢視該裝置歷史。
  - **狀態篩選下拉選單**：支援篩選「全部」、「已完成」、「排隊/生成中」、「失敗/中斷」。
- **全域任務清理與檔案維護**：
  - 管理員可手動刪除任何裝置的特定歷史任務（同步安全移除實體影片檔案與關聯素材）。
  - 提供 **「🧹 一鍵清理所有失敗/中斷任務」** 功能。

#### 2. 伺服器運作狀態與維護模式即時切換 (Server Maintenance Controls)
- **維護模式即時開關 (`SERVER_STATUS` UI 控制器)**：
  - 管理者可直接在 UI 介面上切換伺服器運作旗標：`🟢 正常服務中` / `🔧 伺服器維護中`。
- **後端模型服務進程與顯存管理**：
  - **「🔄 重啟後端模型服務」**：一鍵重啟後端進程。
  - **「🧹 釋放 GPU 顯存暫存 (Free VRAM)」**：調用 ComfyUI `/free` API 一鍵清空顯存快取。

#### 3. 即時排隊與運算佇列監控 (Live Queue & Active Task Monitor)
- **當前執行與等待佇列儀表**：即時呈現 Running 與 Pending 佇列狀態。
- **管理員介入**：提供「強制中斷當前任務」與「清空等待佇列」按鈕。

#### 4. 電腦硬體與伺服器資源即時儀表板 (Hardware & System Dashboard)
- 監控系統記憶體 (RAM)、GPU 核心使用率、GPU 顯存 (VRAM) 與輸出磁碟剩餘空間。

#### 5. 連線裝置總覽 (Connected Devices Overview)
- 統計當前伺服器已知的所有使用者裝置短碼、累計生成任務數與最後活躍時間。

---

## 前端伺服器與後端comfy伺服器的terminal最小化至 Windows System Tray（已完成）

### 實作內容與架構：
1. **單一整合托盤圖示 (Single Integrated Tray Icon)**：
   - 採用 `pystray` 搭配專屬應用圖示 (`assets/app_icon.ico` / `app_icon.png`) 與 Windows AppUserModelID（`MiniMaxH3.AIWebUI.Server`）。
   - 擺脫黑色 cmd 與 python 通用圖示。
2. **全背景無彈出啟動 (Silent Launch)**：
   - 透過 `run_tray.bat` 執行 `tray_supervisor.py`。
   - 使用 `STARTF_USESHOWWINDOW` 與 `SW_HIDE` 啟動前端 WebUI 進程，啟動時完全不彈出黑色控制台黑視窗，直接收納於系統匣。
3. **托盤整合控制選單**：
   - 🎬 WebUI 前端終端機 (顯示 / 隱藏切換)
   - ⚡ ComfyUI 後端終端機 (顯示 / 隱藏切換)
   - 🌐 開啟 WebUI 網頁
   - ▶️ 啟動 ComfyUI 後端
   - ⏹️ 停止 ComfyUI 後端
   - ❌ 退出並關閉所有服務
4. **最小化自動收進托盤 (Intercept Minimize)**：
   - 守護執行緒以低頻率偵測終端機視窗的 `IsIconic(hwnd)` 狀態。
   - 當使用者點擊視窗右上角「—」最小化按鈕時，自動執行 `ShowWindow(hwnd, SW_HIDE)`，使視窗退縮至系統匣托盤而不滯留在 Windows 工作列。
5. **ComfyUI 後端啟動桌面通知 (Windows Desktop Notification)**：
   - 當任何連線（WebUI 首頁工具列、管理員頁籤或手動觸發）要求啟動 ComfyUI 後端服務時，後端呼叫 `windows_notifier.send_windows_notification`。
   - 透過本機 IPC 通知托盤守護行程，立即彈出 Windows 原生系統通知泡泡：
     > ⚡ **MiniMax-H3 後端啟動通知**
     > 已收到連線請求，正在啟動 ComfyUI 後端服務...

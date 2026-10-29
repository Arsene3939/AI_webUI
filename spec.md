# 使用手冊與規範
## 伺服器維護旗標 (`SERVER_STATUS`)，**每次開始更動程式碼前要改**
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

# 接下來要執行的任務與詳細規劃：

## 開放super user權限與頁面:
**為super user額外設計一個UI**
- 讓使用`localhost` (跟前端伺服器同一台主機)的使用者作為super user開啟網頁
- 保留原本的所有功能，並新增一個`管理員操作`頁籤

### 身分識別與權限控管機制：
1. **本機連線識別 (Localhost Super User Detection)**：
   - 透過 Gradio 請求物件 (`request: gr.Request`) 讀取客戶端 IP 位址 (`request.client.host`)。
   - 若連線來源為本機主機 (`"127.0.0.1"`, `"::1"`, `"localhost"`)，即自動識別為 **Super User（系統管理員）**。
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
  - **裝置篩選下拉選單**：支援切換「所有裝置」或單獨選取特定裝置（如 `dev_a1b2c3`），聚焦檢視該裝置歷史。
  - **狀態篩選下拉選單**：支援篩選「全部」、「已完成」、「排隊/生成中」、「失敗/中斷」。
  - 點擊歷史任務即可即時播放預覽影片，並完整查閱提示詞、尺寸解析度、隨機種子、生成秒數與耗時等各項設定參數。
- **全域任務清理與檔案維護**：
  - 管理員可手動刪除任何裝置的特定歷史任務（同步安全移除 `outputs/` 中的實體影片檔案與關聯素材）。
  - 提供 **「🧹 一鍵清理所有失敗/中斷任務」** 功能，快速清除無效紀錄並釋放硬碟空間。

#### 2. 伺服器運作狀態與維護模式即時切換 (Server Maintenance Controls)
- **維護模式即時開關 (`SERVER_STATUS` UI 控制器)**：
  - 管理者無須進入後台修改代碼或重新啟動伺服器，直接在 UI 介面上切換伺服器運作旗標：
    - 當前狀態徽章：`🟢 正常服務中 (OK)` / `🔧 伺服器維護中 (UPDATING)`
    - 操作按鈕：「切換為維護模式」/「恢復正常服務」
  - 切換後即時對所有連線裝置生效，外部裝置頂部將同步顯示紅底維護橫幅並阻斷新任務發送。
- **後端模型服務進程與顯存管理**：
  - 顯示 ComfyUI 後端當前連線狀態、運作進程與連接埠。
  - **「🔄 重啟後端模型服務」**：一鍵優雅重啟後端進程。
  - **「🧹 釋放 GPU 顯存暫存 (Free VRAM)」**：調用 ComfyUI 內建 `/free` API（卸載閒置模型快取並釋放 PyTorch 顯存），在長時間未生成或顯存碎片化時一鍵清空顯存。

#### 3. 即時排隊與運算佇列監控 (Live Queue & Active Task Monitor)
- **當前執行與等待佇列儀表**：
  - 即時向 ComfyUI `/queue` 查詢當前狀態，清楚呈現：
    - 目前正在執行的任務（Running）：顯示任務代碼、提交裝置 ID、生成類型、已耗時。
    - 排隊等待中的任務（Pending）：顯示排隊順序、提交裝置 ID、已等待秒數。
- **管理員介入與佇列控制**：
  - **「🛑 強制中斷當前任務」**：針對卡死或誤發的生成任務進行單點中斷出隊。
  - **「🗑️ 清空等待佇列」**：一鍵取消所有排隊中的生成任務，防止佇列過載。

#### 4. 電腦硬體與伺服器資源即時儀表板 (Hardware & System Dashboard)
- **直觀簡潔的硬體狀態卡片**（避免複雜混亂的終端機日誌，以清楚易讀的進度條與數值呈現）：
  - **系統記憶體 (RAM)**：已用 / 可用 / 總容量（如 `可用 58.2 GB / 總量 128.0 GB`）。
  - **GPU 核心使用率**：當前運算佔用百分比（如 `18%`）。
  - **GPU 顯存 (VRAM)**：已用 / 可用 / 總顯存（如 `可用 18.4 GB / 總量 24.0 GB`）。
  - **輸出磁碟剩餘空間 (Storage Disk)**：監控 `outputs/` 所在磁碟的剩餘可用空間（如 `F: 槽可用 450 GB`），防止長時間運行後磁碟塞滿導致崩潰。
  - 提供 **「🔄 刷新硬體數據」** 按鈕與定時更新。

#### 5. 連線裝置總覽 (Connected Devices Overview)
- 統計當前伺服器已知的所有使用者裝置：
  - 裝置 ID（短碼）、累計生成任務數、最後活躍時間。
  - 協助管理員了解目前伺服器使用者分布與負載情況。

## 前端伺服器與後端comfy伺服器的terminal最小化
- 幫前端伺服器與後端comfy伺服器做一個icon，讓他可以在windwos系統顯示正確圖示跟應用程式名稱，而不是只看到一個`python`在運行
- 開啟前端伺服器與後端comfy伺服器時，將它們的terminal收進 windows的system tray，點擊system tray展開的應用程式列表中的圖示可以打開對應終端。
- 視窗最小化時直接收進system tray，不留在工作列

---

- **維護模式下的前端表現**：
  - **頁面橫幅**：WebUI 頂部標題下方呈現紅色高亮醒目警示框 `🔧 伺服器維護/更新中`。
  - **後端狀態欄**：顯示 `🔧 伺服器維護/更新中`，點擊啟動後端會被安全阻斷並提示 `⚠️ 伺服器維護/更新中，暫停啟動後端`。
  - **生成按鈕**：I2V、T2V、R2V 分頁按下生成時立即彈出 `⚠️ 伺服器維護/更新中，暫停提交生成任務`，不建立背景任務。

### 4.2 前處理結束立即更新為「影片生成中」詳細規劃
- **問題分析**：
  - 先前進度邏輯限定 `task.total_steps > 0 and task.step > 0` 才會判定為 sampling 階段並顯示 `⚡ 影片生成中`。
  - 由於 ComfyUI 的 WebSocket `progress` 事件僅在算完第 1 步時才會首次發送（第 0 步取樣期間 `step` 仍為 0），且此前 `total_steps` 初始值為 0，導致在取樣器節點剛啟動算第 0 步時，輪詢迴圈將其判定為 `elif task.prompt_id in running:`，並反覆覆蓋為 `task.stage = "preprocessing"` 及 `⚡ 前處理中：正在載入模型...`。
  - 使用者在前端看到的現象是：進度條必須等跑到 >0% 才會突然跳出「影片生成中」，前處理明明已結束卻長期停留在「載入模型中」。
- **修正架構**：
  1. **預先賦予總步數 (`task_manager.create_task`)**：
     - 建立任務時自傳入參數提取：`task.total_steps = int(saved_params.get("steps", 0))`，確保任務在未連上 WebSocket 前就具備明確的目標步數。
  2. **節點級取樣識別 (`task_manager._ws_listener`)**：
     - 傳入 `prompt_graph`，監聽 `executing` 事件中的 node key 與 class type。
     - 當執行到 `SamplerCustomAdvanced`、`KSampler` 等取樣節點時，立刻將 `task.stage = "sampling"`，並設定 `task.message = f"⚡ 影片生成中: {task.step}/{task.total_steps} 步"`。
  3. **輪詢邏輯優先維護取樣狀態 (`task_manager._monitor_worker`)**：
     - 將 `elif task.stage == "sampling" or (task.total_steps > 0 and task.step > 0):` 調至 `elif task.prompt_id in running:` 之前。
     - 即使 `task.step == 0`，只要 `task.stage == "sampling"`，狀態字串立刻顯示為 `⚡ 影片生成中: 0/{task.total_steps} 步 (耗時 {time_str})`，杜絕被 `preprocessing` 覆蓋。

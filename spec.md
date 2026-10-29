# 接下來要執行的任務與詳細規劃：

## 1. ~~當有已經在執行的生成任務時，又再次按下生成影片按鈕，直接中斷先前的生成任務並送出當前生成任務，而不是排隊~~
## 1. UI互動邏輯改動：
- 在生成任務開始後，'開始生成影片'按鈕變為'停止生成'，並且若有其他裝置的使用者在生成任務開始後發送其他生成任務，要能進入隊列等待生成。

### 詳細規劃：
- **按鈕狀態與動態切換機制 (`app.py`)**：
  - 在 I2V、T2V、R2V 三大分頁中，配置生成按鈕與停止按鈕配對（`btn` 與 `stop_btn`）：
    - 平時/未生成狀態：顯示「🚀 開始生成影片」（`variant="primary"`，可點擊），「🛑 停止生成」隱藏 (`visible=False`)。
    - 生成任務開始後：按鈕即時變更為「🛑 停止生成」（`variant="stop"`，`visible=True`），「🚀 開始生成影片」隱藏 (`visible=False`)。
    - 使用者點擊「🛑 停止生成」時：
      - 觸發中斷處理回調，取消前端進行中的 generator event，並呼叫後端 `task_manager.interrupt_task` / `interrupt_device_tasks(device_id)` 立即停止該裝置的生成任務。
      - 按鈕即時復原為「🚀 開始生成影片」（`variant="primary"`），進度條更新為中斷狀態提示。
    - 任務正常完成或失敗時：按鈕自動恢復為「🚀 開始生成影片」（`variant="primary"`）。
    - 斷線重新載入或 ID 切換時：`restore_device_state` 與 `poll_active_task_progress` 根據當前裝置是否有進行中任務，動態設定按鈕為「開始生成影片」或「停止生成」。
- **多裝置佇列排隊機制 (`task_manager.py` & `comfy_client.py`)**：
  - 移除先前的「發起新任務時強制中斷其他任務」邏輯。
  - 當裝置 A 正在生成影片時，若裝置 B 發起新生成任務：
    - 裝置 B 的任務正常提交並排入 ComfyUI 佇列 (`queue_prompt`)。
    - 裝置 B 的 UI 顯示 `⏳ 排隊中... (已等待 X秒)`，進度維持於等待狀態。
    - 當裝置 A 生成完畢後，ComfyUI 自動調度執行裝置 B 的任務，裝置 B 依序進入前處理、取樣生成與後處理合成，達成多裝置公平排隊。
  - 精確鎖定中斷範圍：`interrupt_execution` 僅針對使用者指定要取消的 `prompt_id` 進行取消與出隊，不誤殺其他裝置正在排隊或執行的任務。

## 2. '啟動後端模型'按鈕的行為
- 前端伺服器收到啟動後端的請求後，應先檢查電腦資源(可用記憶體 > 50GB，GPU占用 < 20%，可用GPU VRAM > 10GB)，如果不滿足條件，在狀態欄顯示警告(ex: ⚠ 伺服器運算資源不足)

### 詳細規劃：
- **電腦運算資源檢測模組 (`comfy_client.py` / `config.py`)**：
  - 新增 `check_system_resources() -> Tuple[bool, str, Dict[str, Any]]` 函式：
    1. **可用記憶體 (RAM Available)**：透過 `psutil.virtual_memory().available` 取得可用容量，門檻值：`> 50.0 GB`。
    2. **GPU 佔用率 (GPU Utilization)**：優先透過 `nvidia-smi` 查詢 `utilization.gpu`，門檻值：`< 20.0%`。
    3. **可用 GPU VRAM (Free VRAM)**：透過 `nvidia-smi` 或 `torch.cuda.mem_get_info()` 查詢可用顯存容量，門檻值：`> 10.0 GB`。
  - 若所有條件皆符合，回傳 `(True, "", stats)` 允許啟動。
  - 若任一條件不符合，回傳 `(False, warning_msg, stats)`，組裝明確精確之警示訊息（例如：`⚠️ 伺服器運算資源不足：可用記憶體不足 (30.1 GB <= 50.0 GB)；可用 GPU 顯存不足 (3.4 GB <= 10.0 GB)`）。
- **啟動按鈕互動與狀態欄警示 (`app.py`)**：
  - 修改 `on_start_backend()` 事件處理：
    - 收到啟動請求後，先調用 `check_system_resources()` 進行資源前置審查。
    - 若資源不足：
      - 阻斷啟動流程，不呼叫 `start_comfyui_backend`。
      - 在後端狀態欄 (`backend_status_msg`) 顯示警告訊息（如 `⚠️ 伺服器運算資源不足：...`）。
      - 啟動按鈕維持原樣（`⚡ 啟動後端模型`），方便使用者釋放資源後再次點擊。
    - 若資源充足：
      - 進入正常啟動程序，按鈕顯示「🟡 正在啟動後端模型...」，啟動完成後變更為「🟢 後端模型運作中」。
- **自動化測試與驗證規劃**：
  - 單元測試 (`tests/test_comfy_client.py` / `tests/test_app_state.py`)：
    - 測試各項資源指標門檻值的判定邏輯（記憶體 < 50GB、GPU >= 20%、VRAM <= 10GB 分別與綜合觸發警示）。
    - 測試資源充足時順利通過審查。
    - 測試多裝置發送任務時正確進入佇列並依序處理。
    - 測試點擊「停止生成」時按鈕與任務狀態的即時中斷與復原。
  - 端到端測試 (`test_e2e.py` & `run_tests.bat`)：
    - 驗證完整使用流程不受阻斷，所有單元測試與 E2E 測試 100% 通過。

## 3. 多裝置佇列併發排隊與 UI 進度狀態即時更新優化 + 伺服器維護旗標

### 問題根因分析：
1. **Gradio 預設並發限制（WebUI 伺服器層卡塞）**：
   - Gradio 在未顯式設定 `demo.queue(default_concurrency_limit=None)` 時，其內部 Event Queue 的 `default_concurrency_limit` 預設為 `1`。
   - 當裝置 B 正在生成影片時，其 generator 佔用了該唯一的並發通道；此時裝置 A 按下「開始生成影片」，請求被卡在 Gradio 伺服器最外層佇列，`handle_i2v_generate` 根本尚未被執行，無法向 ComfyUI 提交 Prompt 與建立 Task，導致裝置 A 前端無法即時顯示「⏳ 排隊中... (已等待 X秒)」。直到裝置 B 完成後，Gradio 才放行裝置 A 執行生成。
2. **WebSocket progress 廣播事件未過濾 prompt_id**：
   - ComfyUI 透過 WebSocket 廣播 `progress` 事件時，若未校驗事件資料中的 `prompt_id`，多裝置併發時可能導致取樣步數互相干擾。

### 詳細規劃與改動措施：
- **Gradio 佇列解除並發限制 (`app.py`)**：
  - 在定義完 Gradio Blocks 後，顯式呼叫 `demo.queue(default_concurrency_limit=None)`。
  - 在 `launch_webui()` 函式啟動前確保 queue 設置生效。
  - 在 I2V、T2V、R2V 生成按鈕的 `.click(...)` 事件監聽器上明確宣告 `concurrency_limit=None`，確保所有連線裝置皆可同時進入 generator 邏輯並發送佇列查詢。
- **任務狀態與 ComfyUI 佇列即時對齊 (`task_manager.py`)**：
  - 任務送出 `queue_prompt()` 後，第一時間將狀態設定為 `task.status = "queued"`、`task.stage = "pending"`，進度訊息為 `⏳ 排隊中...`。
  - 在背景監控迴圈 `_monitor_worker` 輪詢 `/queue` 時，若 `task.prompt_id in pending`，持續設定 `task.status = "queued"`、`task.stage = "pending"`，進度訊息顯示 `⏳ 排隊中... (已等待 {time_str})`。
  - 在 `_ws_listener` 中增加 `p_id = data.get("prompt_id")` 檢查，若不匹配則略過，杜絕取樣步數跨裝置污染。
- **伺服器維護/更新中旗標機制 (`config.py` & `app.py`)**：
  - 在 `config.py` 定義狀態旗標常數與取得/設定函式：
    - `SERVER_STATUS_OK = "OK"`
    - `SERVER_STATUS_UPDATING = "UPDATING"`
    - `get_server_status() -> str`、`set_server_status(status: str)`
  - 開始修改伺服器前將旗標設為 `UPDATING`，完成後設回 `OK`。
  - 當旗標為 `UPDATING` 時：
    - `build_header_html()` 在頁面頂部以醒目樣式呈現 `🔧 伺服器維護/更新中`。
    - 後端狀態列顯示 `🔧 伺服器維護/更新中`。
    - 啟動後端按鈕阻斷操作並提示 `⚠️ 伺服器維護/更新中，暫停啟動後端`。
    - I2V、T2V、R2V 生成按鈕攔截請求並提示 `⚠️ 伺服器維護/更新中，暫停提交生成任務`。
- **測試驗證**：
  - 在 `tests/test_task_manager.py` 驗證多裝置佇列 pending 狀態維持與隔離。
  - 在 `tests/test_app_state.py` 驗證 `UPDATING` 與 `OK` 狀態切換下的 UI 橫幅與生成拒絕/恢復機制。
  - 運行 79 項單元測試與完整 E2E 測試，保證 100% 通過。

## 4. 前處理結束立即更新為「影片生成中」與伺服器維護旗標使用規範

### 4.1 伺服器維護旗標 (`SERVER_STATUS`) 規範與使用手冊
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

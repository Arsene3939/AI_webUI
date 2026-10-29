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

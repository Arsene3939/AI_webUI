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

---

# 接下來要執行的任務與詳細規劃：

## 1. 修改任意watch範圍內的檔案觸發auto-reload重啟後會出現error，或是process直接卡死

## 2. 在管理員頁面新增系統資源門檻的設定: RAM、VRAM、gpu usage三項，管理員可以在頁面直接調整

---

# 本輪（2026-11-01）施工規畫

## 任務 1：auto-reload 重啟卡死／error（已重現定案）
- **實測重現结论**（7861 隔離埠實跑 dev-reload）：
  - 沒有長連線時：改檔 → reload 乾淨完成（對照組，config 秒回 200）。
  - 使用者情境：關掉舊 process 時卡在 `Waiting for connections to close. (CTRL+C to force quit)` —
    瀏覽器分頁持有的長連線（gradio queue/websocket/SSE 邊緣狀態、LAN 瀏覽器半關 socket）不會自己關，
    uvicorn `timeout_graceful_shutdown` 預設為 **None＝無限等** → 整個 reloader 卡死。
  - 使用者貼的 urllib3 `KeyboardInterrupt` traceback：就是卡死後人手按 Ctrl+C，
    把當時正在進行的背景 HTTP（輪詢／導演呼叫 thread）打斷的雜訊，不是獨立 bug；卡死解掉它就跟著消失。
- **修法**：`app.py` 兩處啟動路徑都加 `timeout_graceful_shutdown`：
  - `_run_dev_reload()`：`timeout_graceful_shutdown=3`（dev 重啟 3 秒後強制收掉殘留連線，reload 總時間 ≤ ~5s）。
  - `launch_webui()`（正式/e2e 路徑）：`timeout_graceful_shutdown=5`，Ctrl+C 關server也不再无限等。
- 附帶保障（已存在，不用改）：reload 殺掉進行中任務後，重启時的 `reconcile_orphaned_tasks`
  會把僵屍 queued/running 降為 interrupted，歷史不會爛掉。
- 驗證：7861 重現環境改檔計時（修前無限等／修後數秒內 `Application startup complete`）。

## 任務 2：管理頁「後端啟動資源門檻」設定（RAM／VRAM／GPU 使用率）
- 現況：門檻是 `config.py` 常數（`MIN_STARTUP_RAM_GB=50／MAX_STARTUP_GPU_UTIL=40／MIN_STARTUP_VRAM_GB=6`），
  只能改 env 重啟生效；`check_system_resources()` 的預設引數在 import 時就固化。
- **作法**：
  1. `config.py`：新增 `SYSTEM_THRESHOLDS_FILE`（outputs/system_thresholds.json，同 admin_ips.json 的持久化模式）
     ＋ `get_system_thresholds()`／`set_system_thresholds()`（讀檔覆寫 env 預設，含範圍驗證）。
  2. `core/comfy_client.py check_system_resources()`：預設引數改 `None`，呼叫時才向
     `config.get_system_thresholds()` 取-current 值（修掉 import 期固化）。
  3. `BaseAdminTab`（三個管理頁共享）新增「📏 後端啟動資源門檻」區：
     三個滑桿（最低可用 RAM GB／GPU 使用率上限 %／最低可用 VRAM GB）＋儲存按鈕＋狀態訊息；
     儲存走 super-user 門護（同 admin IP 名單）；另加 `blocks.load` 每次開頁從檔案重抓現值
     （規避「PAGE 單例建置期快照」陷阱，同任務 3 教訓）。
  4. 硬體儀表板 HTML 順帶顯示目前門檻（管理員一眼對照即時值 vs 門檻）。
- 測試：門檻 get/set _roundtrip、check_system_resources 讀到檔案覆寫值、管理頁 UI 標記存在。

## 驗收程序
1. 旗標 `UPDATING` → 實作 → 改回 `OK`。
2. `pytest tests/` 全綠 → 依序兩個 e2e → 7861 dev-reload 實測 reload 計時。
3. 回填完成紀錄。

---

# 本輪（2026-11-01）施工完成紀錄

## 任務 1：auto-reload 重啟卡死／error — ✅ 已修復＋實測驗證
- **根因**：瀏覽器分頁持有的「回應進行中」長連線（gradio SSE 事件流）。換新 process 時，
  uvicorn 優雅關閉會无限等這種連線結束（`timeout_graceful_shutdown` 預設 None），
  卡在最经典那句 `Waiting for connections to close. (CTRL+C to force quit)`，reloader 跟著卡死。
- **實測前後對照**（同腳本同情境，兩條未結束的 SSE 連線）：
  - 修前（grace=None）：完全重現卡死，觀察 12 秒仍未結束（无限等）。
  - 修後（grace=3）：出現同樣的 Waiting 訊息，但 3 秒後 uvicorn 自動
    `Cancel 2 running task(s), timeout graceful shutdown exceeded` 強制收掉，**3.1 秒完成關閉**。
- **修改**：`config.py` 新增 `WEBUI_SHUTDOWN_TIMEOUT`（env 可調，預設 5 秒）；
  `app.py` 三條啟動路徑全部套用（dev-reload 用 3 秒、launch_webui 兩種模式用 5 秒）。
- 使用者貼的 urllib3 `KeyboardInterrupt` traceback = 卡死後人手 Ctrl+C 打斷背景 HTTP 輪詢的雜訊，
  卡死解掉後不再出現。
- 備註：Windows 下 reloader 是用 CTRL+C 事件叫子 process 關（`basereload.py restart()`），
  子 process 收到後走的正是上述優雅關閉路徑，故上限一加就收口。

## 任務 2：管理員頁面系統資源門檻設定（RAM／VRAM／GPU 使用率）— ✅ 完成
- `config.py`：`SYSTEM_THRESHOLDS_FILE`（outputs/system_thresholds.json，原子寫入）
  ＋ `get_system_thresholds()`／`set_system_thresholds()`（env 預設為底片、存檔覆寫、範圍驗證＋讀取時鉗位、損毀檔靜默退回）。
- `core/comfy_client.py check_system_resources()`：門檻改為**呼叫當下**取值（修掉預設引數 import 期固化），
  管理頁存檔後下次啟動檢查立即採用新值，不用重啟。
- 三個管理頁（minimax／upscaler／strata）共享的「📏 後端啟動資源門檻」區：
  三個滑桿＋儲存按鈕＋狀態訊息；儲存走 super-user 門護（非管理員顯示權限不足）；
  `wire_page_load(blocks)` 每次開頁從檔案重抓現值（規避建置期快照陷阱）。
- 硬體儀表板三張卡（RAM／GPU／VRAM）順帶顯示目前門檻，即時值與門檻一眼對照。
- 新增測試 7 個：門檻 get/set roundtrip、範圍拒絕、讀取鉗位、損毀退回、
  check_system_resources 讀到檔案覆寫值、管理頁元件＋存檔流程＋開頁重抓、儀表板含門檻標示。

## 驗收結果
- 單元測試：**216 passed**（含新增 7 個）；minimax e2e、upscaler e2e 依次全數通過，零殘留。
- `SERVER_STATUS` 已改回 `OK`；所有重現用暫存檔已清除。
- 導演功能：使用者已實機確認功能與 UI 正常（先前殘留的待實測項就此結案）。
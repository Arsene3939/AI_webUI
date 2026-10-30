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

> **✅ 2026-10-30 實作完成紀錄**：任務 1 與任務 2 已按下列規劃全部實作完成。
> - `Task` 已新增 `module` 欄位（舊紀錄自動由 `task_type` 推導，無需遷移）。
> - `TaskManager` 已內建 FIFO 串列 dispatcher（常駐 daemon 執行緒，一張 GPU 一次一個工作，
>   排隊訊息為 `⏳ 排隊中...（前面還有 N 個工作）`）。
> - `interrupt_device_tasks(device_id, module=...)` 模組化中斷；`interrupt_task` 已移除無條件通用 `/interrupt`；
>   upscaler 提交前的搶占中斷已移除。
> - 歷史畫廊 / 會話恢復 / 輪詢全面 module 化，minimax 與 upscaler 紀錄完全互不串檔。
> - 驗證結果：unit tests **103 項全數通過**（新增 9 項涵蓋 module 相容、模組化中斷、
>   FIFO 串列調度、排隊訊息）；`upscaler_test_e2e.py` 新增 **Step 6.5 跨模組並發階段**
>   （實測 upscale prompt 提交時間 = minimax 任務完成時間 +0.00s，證明後端零重疊、優雅排隊）；
>   minimax E2E 8 階段與 upscaler E2E 9 階段皆綠燈。

## 0. 重複提醒：注意事項
- 應避免UI介面出現過多開發相關字詞，讓使用者只看到他需要看到的東西
- 很多東西其實使用者根本不在乎，例如：支援電腦與手機... 

## 1. 管理員模式的關閉後端按鈕應可以強制關閉，無視現有正在執行的任務

## 2. bug排查
- 檢查log，似乎有一個生成任務花費很長時間，生成到7/13步的時候被我手動強制關閉comfy的terminal中斷，但我似乎沒有看到它的歷史紀錄
- 列出可能的問題與解法

## 3. 排版問題
- 現在我用電腦版網頁開啟時，網頁呈現一個很窄的直幅頁面。 雖然主要使用是手機，但也希望電腦版網頁能有更好的視覺體驗。
- 在完全不影響手機版網頁UI的情況下，優化電腦版UI的排版。

## e2e測試留下的檔案跟歷史紀錄、裝置ID等清理
- 現在e2e測試完後會有哪些紀錄殘留？會有哪些是需要留的嗎? 列出所有不需要的殘留物、清理當前的殘留物並讓之後的e2e測試都可以自動清理。
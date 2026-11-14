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

## 1. 管理員頁面新增"電腦關機"按鈕

## 2. 調用strata後端作為影片導演（方案B：minimax 進階參數的導演模型下拉多一個 Strata 選項）
- 本機strata的安裝路徑"F:\Strata\terminal\current"
- ✅ 2026-11-03 定案：不再做顯存自動讓位（實測可讓出的量太少，作廢），改為
  「啟動助理模型」按鈕＋原本的系統資源檢查擋下。詳見本輪施工規畫。

## 3. (規劃，還不實作)hide-terminal-into-system-tray，評估可行性
- 規劃一個讓伺服器的terminal可以在以下任意情況，都能開啟後自動縮到system tray(完全不留在工作列)，並且在system tray找到後可以點開查看log
  1. 開機啟動後自動呼叫.bat
  2. 手動雙擊.bat
  3. 在terminal直接輸入localwebui (我自己加入的環境變數，在"C:\Users\Arsene\Desktop\tools\system\localwebUI.bat")
  4. 開機啟動後自動執行localwebui指令
- 還沒有決定開機啟動要用甚麼方式，你可以評估完hide-terminal-into-system-tray的實際實現方式，再幫我決定哪一種開機啟動最好
- 如果使用bat不容易做到這個功能，你也可以考慮其他作法(例如直接呼叫python 而不是再包一層bat，用pyqt或是pystray等套件)
- 需要做此規劃的有: strata, comfy 兩個後端，以及前端伺服器(本專案webui)

## 4. (規劃，還不實作)開機啟動的方式(依3.的實作規劃決定)

---

# 本輪（2026-11-02 第 2 輪）施工規畫

## 任務 1（實作）：管理員頁面「電腦關機」按鈕
- **位置**：`BaseAdminTab`（三個管理頁共享）新增「💻 電腦電源」區：警示文字＋「🛑 電腦關機」按鈕（紅色）＋「✋ 取消關機」按鈕＋狀態訊息。
- **行為**：點關機 → `shutdown /s /t 15 /c "..."`（15 秒倒數，視窗會顯示系統倒數提示）→ 狀態欄顯示「已在 15 秒後關機，可按取消關機中止」；點取消 → `shutdown /a`。
- **把關**：`AdminManager.on_shutdown_pc / on_cancel_shutdown` 皆走 super-user 門護（本機／管理員名單 IP），非管理員只回權限訊息、不執行任何指令。
- 延遲秒數放 `config.ADMIN_PC_SHUTDOWN_DELAY_S`（env 可調，預設 15）。
- 測試：非管理員拒絕（且不觸發 subprocess）、管理員路徑以 mock 驗證 `shutdown /s /t` 與 `/a` 參數、UI 標記存在。

## 任務 2（僅規畫）：Strata 後端作為影片導演
- **現況**：導演走 ComfyUI 圖內 Qwen3-VL（`core/director_builder.py`＋`core/director_client.py`，
  CLIPLoader/TextGenerate 路線），與影片生成共用 ComfyUI 顯存，需載入導演模型才能用。
- **目標架構**：導演改呼叫本機 Strata（`F:\Strata\terminal\current`）推理服務；
  生成任務送出前用 Strata 的 runtime 停機機制（`strata runtime stop`／管理協定 `runtime.*` 動作）
  把 Strata 佔用的顯存釋放給 ComfyUI，生成結束後再把 Strata 拉起（`strata runtime start --profile …`）。
- **待驗證事項（實作前 Investigation）**：
  1. `strata serve` 的推理 API 端點與相容性（OpenAI `/v1/chat/completions`？）、預設 port、金鑯需求（`STRATA_API_KEY`）。
  2. 「專家顯存釋放」確切機制：runtime stop（完全釋放）vs 引擎層 expert offload（部分釋放）→ 選哪種讓位策略。
  3. `strata runtime start|status|stop` CLI 的無訊息呼叫方式與等待就緒的輪詢方式（`strata status`）。
  4. profile 名稱與導演模型的 run config（導演用哪個模型、size 是否 ≥ 現有 Qwen3-VL 品質）。
- **規劃接點**（實作時）：`config` 加 `DIRECTOR_BACKEND = comfy|strata`＋Strata 端點/profile 設定；
  `director_client` 依旗標分流（strata 路線走 HTTP chat 補完，不吃 ComfyUI）；
  `task_manager.start_background_task` 前掛「讓位鉤子」（先 `runtime.stop` 再排队生成）＋生成完成回調「讓回」。
  本輪不動工。

## 任務 3（僅規畫）：hide-terminal-into-system-tray
### 舊 branch `system/hide-terminal-into-system-tray`（f970f10）失敗原因分析
1. **console 窗戶不屬於被啟動的 process**：Windows 的 console 視窗由 conhost／Windows Terminal 擁有，
   不是 python 的 pid（conhost 也不是 python 的子程序）。舊實作的 `get_hwnds_for_pid(python+children)`
   根本找不到那個視窗 → 所有 `SW_HIDE`／`SW_RESTORE`／最小化攔截全部打空 → 視窗留在工作列。
2. **`CREATE_NEW_CONSOLE` 與 `SW_HIDE` 互相矛盾**：webui 子程序用「開新可見 console」啟動，
   `STARTUPINFO.wShowWindow=SW_HIDE` 對新建 console 不可靠 → 一出生就有一張工作列視窗，事後再藏已來不及。
3. **supervisor 自己就是那張工作列視窗**：run.bat 用 `python tray_supervisor.py`（一般 python 有 console），
   supervisor 自己的視窗（title "MiniMax-H3 Server Tray Supervisor"）常駐工作列 — 使用者看到
   「tray 有 icon 但工作列仍有視窗」主要是這一張＋第 2 點那張。
4. **對 console 行為做外部手腳（0.15s 輪詢 IsIconic→SW_HIDE）在 Windows 上是死路**：
   無法跨程序 subclass console 視窗，加上 1 的 hwnd 找不到，雙重失效。
5. **branch 基線過舊**：啟動命令還是重構前的 `python -m gradio app.py`、`comfy_client` 模組路徑也已移動
   （現為 `core.comfy_client`），對今天的 master 根本跑不起來。
### 新做法方向（結論：不要「藏 console」，要「根本不建立 console」）
- 單一常駐程式 `launcher/tray_supervisor.py`，用 **`pythonw.exe`** 執行（零 console、零工作列）；
  所有子程序（webui／comfy／strata）以 `creationflags=CREATE_NO_WINDOW` 啟動，
  stdout/stderr **直接重導到 `outputs/logs/*.log`** → 工作列天然乾淨，日誌不依賴 console。
- pystray 缽單圖示選單：WebUI／ComfyUI／Strata 三個服務各一區（狀態顯示＋啟動／停止＋
  「📄 開啟 Log」= 用系統自備方式開 log 檔（要即時追蹤就 `powershell Get-Content -Wait`，
  只在管理員主動點時才出現視窗）＋「開啟 WebUI 網頁」＋「結束所有服務」。
- 相依：pystray／Pillow／psutil 皆已在 venv（已查證，無需新安裝）。
- 四種啟動情境统一收斂到「thin launcher」：
  1. 開機啟動→自動呼叫 .bat：.bat 內容＝`start "" pythonw launcher\tray_supervisor.py`（一瞬即返）＋排程任務（見任務 4）。
  2. 手動雙擊 .bat：同上；bat 雙擊無可避免會閃一下黑窗（約 0.1s，bat 自身 console 立刻退出）；
     若要零閃爍改建 `TraySupervisor.lnk`（捷徑直達 pythonw＋工作目錄），雙擊捷徑即可。
  3. terminal 打 `localwebui`：現有 `localwebUI.bat`→`run.bat` 改成啟動 supervisor 後立即返回 terminal
     （現有前台 run.bat 保留為 run_fg.bat 給要看 rolllog 的日子）。
  4. 開機啟動＋localwebui：即 1+3 組合，排程任務跑同一支 .bat。
- ComfyUI 啟動／停止直接沿用 `core.comfy_client`（同 venv 內 import）；Strata 用
  `strata runtime start|stop`（subprocess，CREATE_NO_WINDOW）。
- 本輪不動工，先評估可行性與範圍：**可行**，且比舊做法簡單（核心只是 pythonw＋CREATE_NO_WINDOW＋log 檔化）。

## 任務 4（僅規畫）：開機啟動方式
- 評估三案：
  - **Startup 資料夾捷徑**：最簡單，但只在登入後跑、無倒數重試、bat 閃窗最明顯。
  - **HKLM/HKCU Run 機碼**：類似 Startup，無延遲／重試參數，除錯不便。
  - **工作排程器（Task Scheduler）**（建議）：`schtasks /create /tn LocalWebUI /sc onlogon /delay 0000:30 /tr "…bat"`
    ＋失敗自動重試＋可隱藏執行；與四種情境的 .bat thin launcher 完全相容，也能用
    `install_autostart.bat`／`uninstall_autostart.bat` 一鍵安裝／解除。
- **結論：採工作排程器（使用者登入後觸發、延遲 30 秒）**，理由：延遲讓 GPU／顯存先穩定再拉起服務、
  有重試與事件記錄、解除乾淨；待任務 3 實作完成後一併提供安裝腳本。本輪不動工。

## 驗收程序
1. 旗標 `UPDATING` → 實作任務 1 → 改回 `OK`。
2. `pytest tests/` 全綠 → minimax e2e → upscaler e2e。
3. 回填完成紀錄（任務 2–4 為規畫產出，無程式碼變動）。

---

# 本輪（2026-11-02 第 2 輪）施工完成紀錄

## 任務 1（實作）：管理員頁面「電腦關機」— ✅ 完成
- 三個管理頁共享新增「💻 電腦電源」區：「🛑 電腦關機」＋「✋ 取消關機」＋狀態訊息。
- 關機＝`shutdown /s /t 15`（`config.ADMIN_PC_SHUTDOWN_DELAY_S` 可調）：排定倒數、留反悔窗口；
  取消＝`shutdown /a`；沒有待取消程序時給友善提示。
- 兩個動作皆 super-user 門護（本機／管理員名單 IP）；非管理員只回權限訊息、不觸發任何系統指令；
  排定／取消成功皆寫入工作區 log（log level 為 warning）。
- 新測試 1 組（拒非管理員＋mock 驗證指令參數＋取消兩分支）。

## 任務 2（規畫）：Strata 作為影片導演 — 規畫已在上（本輪不動工）
- 重點：導演改走 `F:\Strata\terminal\current` 的推理服務；生成任務送出前用 Strata runtime
  停機（`strata runtime stop`／管理協定 `runtime.*`）釋放顯存給 ComfyUI，生成後再拉起。
- 四個待驗證項已列（推理 API 相容性與 port／金鑯、釋放機制層級、CLI 無訊息化與就緒輪詢、導演模型 profile）。
- ※ 2026-11-03 更新：顯存自動讓位設計經實測作廢（12GB 卡可讓量太少），改採方案 B，見下一輪。

## 任務 3（規畫）：hide-terminal-into-system-tray — 舊 branch 失敗原因定案＋新方案（本輪不動工）
- 舊 branch（f970f10）失敗核心：①console 窗戶屬於 conhost 不屬於 python pid，
  `get_hwnds_for_pid` 找不到視窗 →  hide/restore/最小化攔截全打空；②`CREATE_NEW_CONSOLE`
  與 `SW_HIDE` 矛盾，子服務一出生就是工作列視窗；③supervisor 本身用 `python`（有 console）
  執行，自己就是那張常駐工作列的窗；④輪詢 IsIconic 的外部攔截思路在 Windows 是死路；
  ⑤branch 基線過舊（`python -m gradio app.py`／`comfy_client` 舊路徑），對現行 master 跑不起來。
- 新方向＝**根本不建立 console**：`pythonw` 跑 `launcher/tray_supervisor.py`，
  子程序全部 `CREATE_NO_WINDOW`＋stdout/stderr 重導 `outputs/logs/*.log`；
  tray 選單提供各服務 啟動／停止／開 log（要用時才出現視窗）。
  pystray／Pillow／psutil 已在 venv，無需新裝。四種啟動情境收斂成 thin launcher（.bat 或 .lnk）。

## 任務 4（規畫）：開機啟動 — 建議工作排程器（登入後觸發、延遲 30 秒、可重試、除錯有記錄），
  待任務 3 實作時一併提供 `install_autostart.bat`／`uninstall_autostart.bat`。本輪不動工。

## 驗收結果
- 單元測試：**227 passed**；minimax e2e、upscaler e2e 依次全數通過；旗標已改回 `OK`；零殘留。

---

# 本輪（2026-11-03）施工規畫

> 前情：2026-11-02 曾實作「Strata 專家顯存自動讓位＋導演自動切換後端」，實測發現
> 12GB 卡上 Strata 實際能讓位的顯存太少（上限約 4GB），設計不實際，**全部進度已回撤**。
> 本輪改採使用者定案的**方案 B**，並把 /strata 頁從 mock 改建為真實功能。
> UI 紅線（沿用注意事項）：**不出現顯存/VRAM/API/端點等開發者字眼**，維持跟 comfy 兩頁
> 一致的「啟動後端模型」設計；資源不足就用原本的系統資源檢查機制擋下。

## 任務 1（實作）：/strata 頁 — 助理模型啟動toolbar
- 新 `components/strata_toolbar.py`（對稱 `components/comfy_toolbar.py`）：
  - 按鈕文字狀態機：「⚡ 啟動助理模型」→ 按下且資源檢查通過 →「🟡 正在啟動助理模型...」→
    上線 →「🟢 助理模型運作中」；維護中 →「🔧 伺服器維護/更新中」。旁邊 🛑 停止钮＋狀態訊息列。
  - 啟動流程：維護閘門 → 已在運作直接回報 → `check_system_resources()`（用管理頁設定的
    同一套門檻與訊息，**不另設新門檻**）→ 通過才呼叫
    `strata runtime start --profile launch-iq3_s-256k`（subprocess、CREATE_NO_WINDOW）→
    輪詢 `/health` 直至就緒（上限 `STRATA_START_TIMEOUT_S`，預設 180s）。
  - 停止：`strata runtime stop --profile …`；交談進行中被停止，交談串流會以友善訊息收尾。
  - 5 秒 timer 輪詢 `/health` 決定按鈕狀態（本機 localhost，開銷可忽略）。
- 頁面同時保留 shell 共用的 ComfyUI toolbar（現況已有），兩顆按鈕文案區隔：
  「啟動後端模型」（ComfyUI，影片生成用）vs「啟動助理模型」（Strata，對話／導演用）。

## 任務 2（實作）：/strata 頁 — 真實智慧對話
- `core/strata_client.py`（新）：health／chat 補完（OpenAI 相容 `/v1/chat/completions`，
  **SSE 串流**逐段出字）／start／stop 全部封裝；所有失敗回友好中文、不丟例外到 UI。
- 對話頁：`gr.Chatbot` 串流出字；側欄＝系統提示詞、創意度、
  ~~「敏感內容濾網」核取方塊~~（※ 2026-11-03 使用者追加決定：此開關移除，
  一律採預設不拒絕的自由回答；引擎 per-request 欄位 `experimental_speed_projection`
  固定 projection on）、工作類型模板（一般對話／分鏡腳本／提示詞打磨／寫作，
  選模板自動帶入系統提示詞）、可選圖片附件（助理能看圖；引擎未開圖片解讀時自動降為純文字）。
- 助理沒開 → 回覆「請先按上方啟動助理模型」，不碰 ComfyUI。

## 任務 3（實作）：導演方案 B（minimax「優化提示詞」可用 Strata）
- 「⚙️ 進階參數 → 導演模型」下拉一律多一個選項「Strata 智慧助理」
  （`components/video_params.py`＋`components/director_block.py` 的清單與定時刷新同步）。
- `core/director_client.call_director`：選到該選項 → 走 Strata 對話補完（同一套統一導演
  系統提示詞；有第一幀圖且助理能看圖則附圖），完全不碰 ComfyUI；選其他模型 → 原 ComfyUI
  路線不動。Strata 沒開 → 「Strata 助理目前沒開著：請先到 💬 Strata 頁啟動，或改用其他導演模型」。
- **不做**自動讓位／自動切換後端／新門檻；ComfyUI 路線的資源情境由既有機制處理。

## 任務 4（實作）：Strata 管理頁改造（移除 Ollama 假設定）
- `views/strata/admin_tab.py` 重寫：端點 URL＋金鑰儲存至 `outputs/strata_settings.json`
  （env 可覆寫 `STRATA_BASE_URL`/`STRATA_API_KEY`，同 thresholds 持久化模式）；
  「測試連線」→ 真實顯示助理狀態（model／上線與否／可否看圖，用白話）。
- `config.py` 新增 Strata 區塊：設定檔 get/set、`STRATA_CLI_PATH`、`STRATA_LAUNCH_PROFILE`、
  `STRATA_START_TIMEOUT_S`、`DIRECTOR_STRATA_LABEL`。

## 任務 5（追加，2026-11-03 使用者追加）：UI 文案集中管理
- **目標**：把 WebUI 上會出現的所有文字訊息集中到同一個資料夾，未來改文案只動一處。
- **做法**：新套件 `ui_text/`（文案集中包）：
  - `common.py`（跨頁共用：維護中、資源不足、權限、啟動／停止等通用訊息）
  - `header.py`／`minimax.py`／`upscaler.py`／`strata.py`／`director.py`／`admin.py`／`backend.py`
    依頁面／區塊分組；`__init__.py` 全部 re-export，全站統一 `from ui_text import XXX`。
- **邊界（規則）**：只搬「使用者看得到的文字」（按鈕、標籤、占位文字、狀態訊息、警示、Markdown 文案）；
  資料值（模型檔名、解析度/取樣器技術名稱、目錄路徑、CSS/JS）**不搬**，仍留在 config／各模組。
- **動態訊息**：含數字／變數的訊息以模板常數存放（例：`⚠️ 伺服器運算資源不足：{reasons}`），
  呼叫端用 `.format(...)` 組回，文字本體只存在 ui_text。
- **值不變原則**：搬移前後字串完全相同（測試與 e2e 對既有文字的斷言不受影響）；
  新 /strata 頁的文案直接從 ui_text 取用。
- **測試**：既有全套必須全綠（值相同所以斷言不動）；新增 1 組測試驗證 ui_text 关键常數
  存在且被各模組實際引用（grep 式來源掃描，避免文案又散回各檔案）。

## 測試計畫
- config：settings 存檔／讀取／env 覆寫。
- strata_client：health 解析、SSE 逐段解析（含 [DONE]／keep-alive 註解行）、
  濾網欄位（True/False/不帶）、圖片 part、start/stop subprocess 參數、全路徑不丟例外。
- toolbar：維護中／已在運作／資源不足→不呼叫啟動／啟動成功輪詢就緒。
- 對話 handler：沒開→提示、串流組歷史、模板帶入系統提示詞。
- 導演：Strata 選項在清單與刷新中存活、label→Strata 路徑、沒開→錯誤訊息、
  ComfyUI 路徑回歸（調整 test_director 斷言以含新選項）。
- 執行順序照舊：旗標 UPDATING → 實作 → 改回 OK → pytest 全綠 → minimax e2e → upscaler e2e。

---

# 本輪（2026-11-03）施工完成紀錄

## 任務 1（實作）：/strata 助理模型啟動 toolbar — ✅ 完成
- 新 `components/strata_toolbar.py`：「⚡ 啟動助理模型／🟡 正在啟動助理模型...／🟢 助理模型運作中／
  🔧 維護中」按鈕狀態機＋🛑 停止＋狀態列，與 comfy toolbar 同構；5 秒輪詢 `/health`。
- 啟動前過**同一套**系統資源檢查（管理頁門檻，不另設新門檻）；擋下時原訊息＋一句
  「可能是影片生成後端正在使用中」的可操作提示。
- 啟動＝`strata runtime start --profile launch-iq3_s-256k`（subprocess、不視窗化）＋輪詢就緒
  （上限 180s）；停止＝`runtime stop`。

## 任務 2（實作）：真實智慧對話 — ✅ 完成
- 新 `core/strata_client.py`：health／SSE 串流補完（容忍 keep-alive 與壞行）／啟動／停止／
  圖片 data URI；所有失敗都是友善中文，不丟例外到 UI。
- 對話頁真實串流出字；侧欄：工作類型模板（4 種，帶入角色設定）、助理角色設定、
  創意度、可選圖片（引擎未開圖片解讀時自動降純文字並註明）。歷史取最近 12 輪。
  （※ 敏感內容濾網核取方塊已依使用者追加決定移除，見下方追加任務紀錄。）

## 任務 3（實作）：導演方案 B — ✅ 完成
- 「⚙️ 進階參數→導演模型」清單尾端常在「Strata 智慧助理」選項（build＋5s 刷新都含）；
  選它走助理對話補完（統一導演系統提示詞、可附圖、創作模式不帶濾鏡），完全不碰 ComfyUI；
  沒開→「請先到 💬 Strata 頁按啟動助理模型，或改用其他導演模型」。
- 沒有 ComfyUI 導演模型時下拉仍可用（預設值自動落到 Strata 選項）；不做任何顯存讓位。

## 任務 4（實作）：Strata 管理頁 — ✅ 完成
- 移除 Ollama 假設定；位址／金鑰存 `outputs/strata_settings.json`（env 可覆寫、破檔退回預設、
  URL 自動正規化）；「檢查助理狀態」用白話顯示模型／記憶容量／可否看圖；super-user 門護儲存。

## 驗收結果（任務 1–4）
- 單元測試：**256 passed**；minimax e2e、upscaler e2e 依次全數通過；旗標 `OK`；零殘留。

## 任務 5（追加·實作）：UI 文案集中管理 — ✅ 完成
- 新套件 `ui_text/`：common／backend／minimax／upscaler／strata／admin／chrome 七檔，
  `__init__.py` 全部 re-export；全站 30 個來源檔改為 `from ui_text import XXX`，
  約 370 個文案常數（含 {} 模板），搬移前後字串逐字相同。
- 動態訊息改模板常數（資源警告、排队中/生成中進度、耗時格式、資源門檻摘要…），
  呼叫端 `.format(...)` 組回；HTML 面板（硬體儀表板／佇列／裝置表／IP 名單）整段進 ui_text。
- 任務篩選下拉採「文案＝比對值」協定：管理頁與 task_manager 引用同一份 `ADMIN_FILTER_*`
  常數，不會一邊改字一邊對不上。
- 刻意不搬（已有檔內註記）：模型檔名／解析度與取樣器技術值／CSS/JS／logger 文字／
  「無可移除」內部標記／導演給模型的提示詞框架。
- 新守門測試 `tests/test_ui_text.py`：文案不得散回來源檔（AST 掃描比對）、ui_text 只准
  依賴 config（杜絕循環 import）、篩選協定檢查。
- 驗收：單元測試 **260 passed**；minimax e2e、upscaler e2e 全數通過；旗標 `OK`；零殘留。

## 追加任務 6（2026-11-03 使用者追加）：移除敏感內容開關 — ✅ 完成
- 使用者決定：「直接移除敏感內容開關，預設直接開啟（預設不拒絕）」。
- /strata 對話頁移除「敏感內容濾網」核取方塊；對話一律傳 `filter_on=False`
  → 引擎 `experimental_speed_projection=True`（projection on＝預設不拒絕的自由回答）。
- 導演路線原本就是不拒絕（filter_on=False），語意不變；`strata_client` 的
  `filter_on` 參數保留（None＝不帶欄位，引擎預設同样是 on）。
- 順帶修正文案集中搬移時的措辭走樣（值不變原則破洞，由測試擋下現形）：
  「目前沒有可用的導演模型：請先下載導演模型，或改選『Strata 智慧助理』」、
  「⚠️ 後端模型沒上線：請先按頁面上方的『啟動後端模型』再試一次」、
  頁標「💬 Strata 智慧助理系統」回復可直接操作/可對照的完整措辭。
- 驗收：單元測試 **260 passed**；minimax e2e、upscaler e2e 全數通過；旗標 `OK`；零殘留。
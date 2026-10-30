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
> **✅ 2026-10-31 (第三輪) 完成紀錄**：任務 1、2 為評估（結論已寫進各節），任務 3 已實作。
> - **任務 1 結論**：taskmanager 現階段**不建議大拆**（953 行仍屬單一領域可讀範圍、外部 8+ 個 import
>   端依賴單例、拆分只有可讀性效益無新功能）；下次動到監控執行緒時再依
>   `task_models → history_store → comfy_progress` 的順序由低風險縫隙抽出，TaskManager 維持 facade。
> - **任務 2 結論**：以路徑分頁**可行**且是「刷新留在原頁」的正解（gradio 6.30 查證：`gr.Tab` 已無
>   `url_path`、`Blocks` 無 path 參數，故須走 `gr.mount_gradio_app`＋FastAPI/uvicorn 的多 Blocks 掛載；
>   同程序內 task_manager 單例與 LocalStorage device ID 天然共用）。屬中等規模啟動重構，建議獨立排期；
>   只想先解決刷新痛点可用 location.hash 同步分頁的過渡 JS（約 20 行）替代。
> - **任務 3（奇怪文字方塊）**：根因＝`backend-status-box` class 自帶背景/框線/min-height 48px 一層
>   ＋gradio `.block` 包装被主題描邊一層 ⇒ 空訊息時兩層空白方塊。修法＝CSS 把該 class 改為無任何
>   方塊描繪的自然文字行（透明底、無框、min-height 1.6em 防跳動、0.9rem 淺色字），
>   `.block:has(> .backend-status-box)` 同時脫掉包装層描繪；順手移除完全無人使用的死 CSS
>   `res-display-box`。三個 admin tab 的操作訊息同步適用。元件檔零修改。
> - 驗證：unit tests **156 項全數通過**（新增 3 項防回歸：feedback 行不得再有方塊描繪、
>   `.block:has` 脫殼規則必須存在、死 class 不得復活）。
> - `SERVER_STATUS` 已於施工前切 UPDATING、完工後恢復 OK。

## 0. 重複提醒：注意事項
- 應避免UI介面出現過多開發相關字詞，讓使用者只看到他需要看到的東西
- 很多東西其實使用者根本不在乎，例如：支援電腦與手機... 
- 開始施工前要改SERVER_STATUS旗標

## 1. 評估taskmanager是否應該模組化
> **✅ 2026-10-31 (第四輪) 已依使用者指示實作**：以「不改變外部 import」為原則完成 facade 拆分，
> 下方評估保留作決策背景。
### 現況分析
- `task_manager.py` 原本 953 行、單一 `TaskManager` 類別（27 個方法）＋ `Task` dataclass ＋模組級單例。
  职责可分成 7 塊：
  1. 任務模型與欄位（Task/params/還原）
  2. 歷史持久化（`_load_history`/`_save_history`/`delete_task`/`delete_failed...`）
  3. 上傳媒體歸檔（`_archive_file`，配合 `outputs/inputs/`）
  4. FIFO 串列調度器（`_dispatcher_loop`＋GPU 隔離＋排隊訊息）
  5. 每任務監控執行緒（`_monitor_worker` 188 行、`_ws_listener` 63 行：HTTP 輪詢＋WS＋看門狗）
  6. 後端同步/救回（`sync_task_with_server`/`reconcile_orphaned_tasks`/`_prompt_alive_on_server`）
  7. 裝置查詢與中斷 API（get_*、interrupt_*）
### 評估
| 面向 | 評估 |
|---|---|
| 目前規模 | 953 行尚在「單一領域模組」可讀範圍內；真正大的只有 `_monitor_worker`（188 行） |
| 測試現況 | 153→156 項單元測試直接打這個模組（monkeypatch 檔案路徑／requests），是重構安全網 |
| 風險 | 全專案 8 個以上的 import 端都吃 `task_manager` 單例；拆分後單例/執行緒/鎖若分屬不同模組，容易引入狀態不同步的隱蔽 bug |
| 效益 | 拆檔不會帶來新功能，只會改善可讀性；目前唯一的痛点是監控執行緒混雜輪詢/WS/進度解析 |
### 結論（建議）
- **現階段不建議大拆**；維持 `task_manager.py` 作為 facade（外部 import 面不變）。
- 若日後要動監控邏輯（例如 strata 任務納入管理器、進度協定變更），屆時再按縫隙抽出：
  `task_models.py`（Task 欄位/序列化）→ `history_store.py`（讀寫/清除歷史與歸檔）→
  `comfy_progress.py`（`_monitor_worker`＋`_ws_listener` 的純輪詢/WS 協定），
  調度器與裝置 API 留在 TaskManager。順序由風險最低（models）開始。
### 實施紀錄（2026-10-31 第四輪，依使用者指示提前執行）
- 使用者指示：「以不改變 app 的 import 為原則，task_manager 自己再去 import 其他模組」。
- `task_manager.py` → **`task_manager/` package（facade）**：
  - `__init__.py`：外部介面＋**可 monkeypatch 的常數面**（`HISTORY_FILE`/`INPUTS_ARCHIVE_DIR`/
    `OUTPUT_DIR`/`requests`/`queue_prompt`/`download_output_file`）。所有 import 端
    （app/core/components/views/e2e/tests）**一行都不用改**。
  - `models.py`＝Task＋裝置比對；`history_store.py`＝歷史持久化/殭屍降格；
    `media_archive.py`＝上傳歸檔/清除；`server_sync.py`＝/history+/queue 同步、orphan 核對、
    prompt 存活探測；`comfy_progress.py`＝提交＋WS 監聽＋輪詢看門狗；
    `manager.py`＝TaskManager（註冊表/裝置查詢/FIFO 調度器/單例）。
  - 關鍵機制：子模組以 `import task_manager as _pkg` **延遲讀取** facade 常數與 comfy_client 名稱，
    因此 `monkeypatch.setattr(task_manager, "HISTORY_FILE", ...)`、`@patch("task_manager.queue_prompt")`、
    `@patch("task_manager.requests.get")` 等測試打樁在呼叫點照常生效（conftest/tests/e2e 零修改）。
  - `TaskManager._monitor_worker`/`_save_history`/`_ws_listener` 保留為薄委派（測試直接 patch/呼叫它們）。
- 順帶修出一個被使用者改 `DEFAULT_QUALITY_LEVEL`（5→1 極速預覽）後浮現的 config bug：
  `normalize_quality_choice` 的 MP 解析分支用 `quality_level_to_mp`（對垃圾值靜默回 1.0 MP），
  導致無法辨識的值永遠被映射到 1.0 MP 檔位、永遠輪不到 `DEFAULT_QUALITY_LEVEL` fallback。
  修法＝新增 `_parse_mp_strict()`（無法解析回 None），garbage 一律落到新預設值；
  `quality_level_to_mp` 本身的寬鬆 1.0 fallback 維持不影響其他呼叫端。
  （test_config 內兩條靠「預設恰好是 1.0 MP」巧合成立的斷言已改為直接驗證語義。）
- 驗證：unit tests **156 項全數通過**（拆分前後同數）；minimax E2E 8 階段全綠
  （提交/排队/WS 進度/下載/歷史刪除全程走拆分後路徑）、零殘留。
## 2. 評估以網頁路徑(/)分開管理頁面的可行性
- 這樣做是不是可以實現使用者重新整理網頁時，會留在原本頁面的機制
### 現況分析
- 目前是**單一 Blocks**：各 view（MiniMaxView/UpscalerView/strata）在 `views/` 已類別化，但它們全部
  渲染在同一 Blocks 內，分頁靠 gradio 的 `gr.Tabs`，**URL 始終是 `/`** ⇒ 重新整理一律回到預設分頁。
- gradio 6.30 查證：`gr.Tab` **沒有** `url_path` 參數（5.x 曾有、6.30 已不存在）、`gr.Blocks` 也沒有
  path 參數 ⇒ 內建深連結不可用；`gr.mount_gradio_app` 可用（把多個 Blocks 掛在同一 port 的不同路徑）。
### 兩條路線比較
| | A. 多 Blocks 掛載（真實路徑 /, /upscaler, /strata） | B. 單 Blocks＋JS 把分頁選取同步到 location.hash |
|---|---|---|
| 刷新留在原頁 | ✅ 瀏覽器原生行為 | ✅ 用 JS 還原點擊（hack） |
| 可深連結/前進後退 | ✅ | ❌（hash 可但脆弱） |
| 實作成本 | 中：`launch()` 改 FastAPI+uvicorn+`mount_gradio_app`；css/theme/head/queue/allowed_paths 要逐 app 套用（現在只在 launch 一次性給）；header/sidebar/SessionContext 每頁重建 | 低～中：一段 head JS 監聽 `.tab` 按鈕並寫 hash；依賴 gradio 內部 DOM，升級易斷 |
| 狀態共用 | 同一 process ⇒ `task_manager` 單例、LocalStorage device ID 天然共用；但跨頁切换是整頁 reloader，未提交的表單輸入會丟（有「恢復上次輸入」兜底） | 同一頁內切換，狀態不丟 |
| 對 e2e/測試衝擊 | 大（兩個 e2e runner 要改多頁導航） | 小 |
### 結論（建議）
- **可行**，而且 A 是正解（真正實現「刷新留在原頁」＋可收藏/分享各模組 URL），但屬於中等規模的啟動重構，
  建議列為獨立工程再排期；views/ 的類別化結構已經替 A 鋪好路。
- 如果只想先解決「重新整理跑回首頁分頁」這個小痛点，可先做 B（約 20 行 JS）過渡，日後升級到 A。
### 方案 A 詳細規劃（尚未實作）
#### A-1. 階層規劃（URL 與檔案結構）〔2026-10-31 依使用者構想修訂〕
```
URL：
  /                    → 導向頁：讀 LocalStorage last_page 自動跳轉上次使用的模組頁；
                         首次造訪導向 /minimax（各模組頁載入時寫 last_page）
  /minimax             → MiniMax 頁（頁內 tabs：T2V/I2V/R2V/歷史/管理）
  /upscaler            → 畫質增強 Upscaler 頁
  /strata              → Strata 頁
  /minimax/i2v 等      → tab 級「假路由」URL：只掛 3 個 app，
                         FastAPI catch-all 讓 /minimax/* 都回 minimax 的 index，
                         頁內 JS tab-router 讀 pathname 點選對應 gr.Tab，
                         點 tab 時 history.pushState 寫回 pathname。
                         ⇒ 深連結/刷新留存/的外觀全部成立，但不產生 12 個 mount。

檔案：
  webapp/
    __init__.py
    shell.py          # 共用外殼：header/sidebar/SessionContext/CSS·theme·head 套用（每頁一次）
                      # ＋ last_page 寫入 JS
    tab_router.js     # tab↔pathname 雙向同步（含 gradio tab DOM 選擇器，升級需重驗）
    pages_minimax.py  # 組 MiniMax Blocks（內部使用既有 MiniMaxView）
    pages_upscaler.py # 組 Upscaler Blocks（既有 UpscalerView）
    pages_strata.py   # 組 Strata Blocks（既有 StrataView）
    server.py         # FastAPI 组装：mount_gradio_app ×3 ＋ / 導向 app ＋ /<module>/* catch-all + uvicorn
  app.py              # 瘦身为入口：保留 launch_webui() 外殼（PortGuardian/reconcile/維護 banner）
```
- `views/` 現有的 MiniMaxView/UpscalerView/StrataView **不動**：它們已經把元件建好，
  只是目前全塞在同一 Blocks；改為各頁各自 `with gr.Blocks(...)` 內 render 一次。
- `task_manager`、`AdminManager`、`config` 都是同程序單例，三個頁面天然共用，無需改動。
- ⚠️ 設計紅線：**tab 不等於 mount**。把每個 tab 掛成獨立 Blocks（共 12＋個 app）會讓
  SessionContext/timer/CSS/queue websocket 全部翻倍、tab 切換變整頁 reload（丟未提交表單）、
  e2e 矩陣失控——URL 外觀用假路由達成，app 邊界維持 3 個。
- ⚠️ `/minimax/admin` 只是可見性捷徑，不是權限界線；admin 動作的真正防呆仍是後端
  `is_super_user`（IP/session）檢查，不得因有 URL 而鬆動。

#### A-2. 改動範圍
| 項目 | 改動 | 風險 |
|---|---|---|
| 啟動棧 | `demo.launch()` → FastAPI＋`gr.mount_gradio_app`×3＋`/` 導向 app＋uvicorn（保留 PortGuardian 檢查、`reconcile_orphaned_tasks`、啟動 banner） | 中：mount 後 queue/static/websocket 路徑由 gradio 自動處理，但 watch 模式（`-m gradio app.py`）與多頁掛載的相容性**必須先驗證**，不行就 dev 只掛單頁 |
| tab 子路徑假路由 | FastAPI catch-all 讓 `/<module>/*` 回傳該模組 index＋頁內 JS tab-router（pathname⇄gr.Tab 雙向同步、pushState）；`/` 讀 LocalStorage `last_page` 跳轉 | 中：JS 依賴 gradio 內部 tab DOM，gradio 升級需重驗（有 e2e 最深連結測試守住）；`/minimax/admin` URL 僅為捷徑，權限仍由 is_super_user 把關 |
| theme/css/head | 由 launch 參數改為**每頁 Blocks 建立時**套用（shell.py 統一給）；熱重載修復的 reload 分支同步改到 shell | 低（已有防回歸測試护航） |
| 跨頁切換 | header/sidebar 加 `<a href="/upscaler">` 連結取代跨模組 tab；頁內 tabs 不動 | 低；注意整頁 reload 會丟未提交表單（「恢復上次輸入」兜底） |
| device ID / LocalStorage | 同 origin，DEVICE_STORAGE_SECRET 機制照舊共用，不動 | 低 |
| 輪詢負荷 | check_server 0.5s timer、進度輪詢：每個「開著的分頁」各跑一套＝與現況相同（多頁切換後舊分頁 timer 隨整頁卸載自然消失，負擔反而比單一頁更多 tab 時更小） | 低 |
| 維護模式 banner | SERVER_STATUS UPDATING 顯示邏輯每頁 header 各自渲染（現有 build_header_html 重用） | 低 |
| allowed_paths/queue | 逐 app 設定（同一份設定抽到 shell 常數） | 低 |
| 單元測試 | `test_app_state` 的 launch_webui port 診斷、`test_reload_style_guard` 改接新 server factory；其餘不動 | 中 |
| e2e | 兩個 runner 增加「進到對應頁」導航步驟；admin 步驟隨各頁管理 tab | 中：這是最大塊的既有投資保護 |
#### A-3. 任務規劃（執行順序）〔配合修訂版 IA〕
1. **可行性验证 spike（半天）**：最小實驗——FastAPI＋`mount_gradio_app` 掛 2 個 Blocks，
   驗證 6.30 的 queue/websocket/static 路徑、watch 模式相容性、`gr.Timer` 於離頁時是否停止輪詢、
   **catch-all 回傳 index＋pushState 改 pathname 後 gradio 功能（上傳/queue）不受影響**。
   ⚠️ 驗證不過就退回「3 mounts 無 tab 子路徑」或純 B 方案，不硬做。
2. `webapp/shell.py`：抽出共用外殼（Blocks 建立參數、header、sidebar、SessionContext、樣式套用、
   `last_page` LocalStorage 寫入）。
3. `pages_*.py`×3：各頁組裝（把現在 app.py 內 view 執行序搬到對應頁）。
4. `server.py`＋app.py `launch_webui()` 改造（含 PortGuardian、reconcile、維護 banner、watch 模式行為、
   `/<module>/*` catch-all、`/` 導向 app）。
5. `tab_router.js`：pathname⇄gr.Tab 雙向同步（先只給 minimax 的五個 tab 啟用，跑通再套 upscaler/strata）。
6. header/sidebar 加跨頁連結；移除跨模組 tab（頁內 tabs 保留）。
7. 單元測試適配（launch_webui/reload-style 接新 server factory）＋全量回歸（目標：156+ 項綠）。
8. e2e 兩支適配：模組級 URL 直達測試（/minimax、/upscaler、/strata、`/` 跳轉）＋
   **僅一條**最深 tab 連結測試（如 /minimax/i2v）；矩陣控制不住就不加。全綠＋零殘留檢查。
9. 完成紀錄寫入 spec、SERVER_STATUS 恢復 OK。
- 粗估：spike 半天；完整實施 1.5～2.5 個工作日當量（tab 假路由多半天～一天）；
  風險集中在啟動棧、假路由 JS、e2e 適配。
## 3. UI裡的奇怪文字方塊
- 參考"E:\Screenshots\螢幕擷取畫面 2026-10-31 035820.png"，該圖片中，"啟動後端模型"按鈕跟"提取最後一幀"按鈕底下，都有一個空白的文字方塊(而且是兩層)，它們分別對應到的是伺服器狀態回饋欄，以及提取last frame時的文字提示欄。能讓他們像任務的狀態回饋欄一樣不被任何方塊包著、自然的排版在網頁UI中嗎?
### 根因
- 兩個方塊是 `gr.Markdown("", elem_classes=["backend-status-box"])`：
  `comfy_toolbar.py`（後端狀態訊息）與 `media_player.py`（最後一幀提示訊息）。
  「兩層」= 我們的 `.backend-status-box` CSS 自帶背景/框線/min-height 48px 畫了一層，
  gradio 的 `.block` 包装層又被主題描了一層 ⇒ 空訊息時變成兩層空白方塊。
### 解法
- `styles.py`：`.backend-status-box` 改為**無描繪的自然文字行**（transparent、無框線/內距、
  min-height 1.6em 保留一行高度防跳動、0.9rem 淺色字），並用
  `.block:has(> .backend-status-box)` 把包装層的背景/框線也脫掉（兩種 nesting 情境都罩住）。
- 順手移除 `res-display-box` 全部 CSS：查證全專案**沒有任何元件使用**此 class（死 CSS）。
- 其餘同 class 的 feedback（3 個 admin tab 的操作訊息）一併變成同款自然文字行。
- 元件檔（comfy_toolbar/media_player）不用改，純 CSS 修正＋3 項防回歸測試。
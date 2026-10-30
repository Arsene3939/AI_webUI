# AI WebUI 整合式工作台 (MiniMax / Video Upscaler / Strata LLM)
## 📂 專案檔案結構

```text
F:\program_file\AI_webUI\
├── app.py                         # 系統整合進入點 (精簡裝配，~470行)
├── config.py                      # 全域常數設定、解析度計算與維護旗標
├── comfy_client.py                # ComfyUI API 通訊、WebSocket 進度與進程管理
├── task_manager.py                # 執行緒安全之多裝置任務佇列與儲存管理器
├── workflow_builder.py            # MiniMax-H3 工作流 JSON 節點圖構建器
├── frame_extractor.py             # 影片最後一幀抽取工具 (PyAV 主路徑 + ffmpeg 備援)
├── logger.py                      # 終端機彩色格式化日誌模組
├── core/                          # 核心抽象與系統管理 (OOP 架構)
│   ├── __init__.py
│   ├── base_view.py               # 抽象視圖基類 BaseView (定義生命週期契約)
│   ├── comfy_view.py              # ComfyUI 系列視圖基類 ComfyUIBaseView
│   ├── session_context.py         # 裝置 Session 與狀態管理器
│   ├── admin_manager.py           # 管理員權限、IP 正規化與維護狀態控制
│   ├── port_guardian.py           # 連接埠 7860 佔用排查與自動清理工具
│   ├── base_admin_tab.py          # 通用管理員抽象基類 (Template Method)
│   └── comfy_admin_tab.py         # ComfyUI 後端專屬管理員抽象基類
├── components/                    # 模組化可複用 UI 元件 (DRY 原則)
│   ├── __init__.py
│   ├── styles.py                  # 全域 CSS 與客戶端 JS 腳本
│   ├── header.py                  # 頂部導航橫幅 HeaderComponent
│   ├── dashboard_sidebar.py       # 左上方展開式 Dashboard 控制台元件
│   ├── comfy_toolbar.py           # ComfyUI 後端模型狀態與啟停工具列
│   ├── video_params.py            # 視訊生成共用參數卡片 (VideoParamsComponent)
│   ├── media_player.py            # 播放器/進度條/最後一幀下載卡片 (VideoPlayerCardComponent)
│   └── history_gallery.py         # 歷史紀錄檢視器元件 (HistoryGalleryComponent)
├── views/                         # 三大核心功能模組視圖
│   ├── __init__.py
│   ├── minimax/                   # 模組 1: MiniMax-H3 視訊生成
│   │   ├── __init__.py
│   │   ├── view.py                # MiniMaxView (I2V/T2V/R2V/歷史/管理員)
│   │   ├── admin_tab.py           # MiniMaxAdminTab (跨裝置任務監控與清理)
│   │   └── tabs/                  # I2V, T2V, R2V 獨立子頁面
│   ├── upscaler/                  # 模組 2: 視訊超解析放大
│   │   ├── __init__.py
│   │   ├── view.py                # UpscalerView (參數/播放器/歷史/管理員)
│   │   └── admin_tab.py           # UpscalerAdminTab (Tile 快取與超解析狀態)
│   ├── strata/                    # 模組 3: Strata Qwen3.8 LLM
│   │   ├── __init__.py
│   │   ├── view.py                # StrataView (Chatbot/設定/管理員)
│   │   └── admin_tab.py           # StrataAdminTab (LLM 端點與金鑰設定)
│   └── admin/                     # 向前相容管理員視圖別名
│       ├── __init__.py
│       └── view.py                # AdminPanelView
├── outputs/                       # 生成影片下載目錄與 task_history.json 保存庫
├── e2e_tests/                     # 端到端 (E2E) 整合測試套件目錄
│   ├── minimax_test_e2e.py        # MiniMax-H3 全生命週期真實使用者 E2E 測試
│   └── upscaler_test_e2e.py       # Video Upscaler 超解析全生命週期 E2E 測試
├── run.bat                        # Windows 一鍵啟動 WebUI 批次檔 (Port 7860, gradio 熱重載模式)
├── run_tests.bat                  # 全自動測試套件執行腳本 (Unit Tests + 2x E2E Tests)
├── test_e2e.py                    # 端到端整合測試向下相容入口
├── spec.md                        # 專案需求與功能詳細規格文件
├── requirements.txt               # 專案 Python 相依套件列表
└── tests/                         # 單元測試目錄 (122 項測試 100% 通過)
    ├── test_admin_tabs.py         # 測試管理員 Tab 繼承架構、IP 正規化與組件生成
    ├── test_app_state.py          # 測試 UI 初始化、工作階段恢復、定時輪詢、中斷觸發
    ├── test_comfy_client.py       # 測試伺服器探針、上傳、下載、佇列中斷邏輯
    ├── test_config.py             # 測試 17k+5 幀數吸附、16 像素對齊、品質檔次正規化
    ├── test_logger.py             # 測試日誌輸出與格式器
    ├── test_frame_extractor.py    # 測試最後一幀抽取正確性、ffmpeg 備援與下載鈕 UI 契約
    ├── test_queue_multidevice.py  # 多裝置/多模組排隊壓力、中斷互動、重啟幽靈任務恢復等進階場景
    ├── test_task_manager.py       # 測試多裝置任務隔離、module 隔離、串列排隊調度與模組化中斷
    ├── test_upscaler.py           # 測試超解析模型掃描、工作流拓撲與 UI 綁定
    └── test_workflow_builder.py   # 測試 I2V, T2V, R2V 工作流節點拓撲正確性
```

---

## 🧩 核心組件說明

整體架構採四層式分層：**裝配入口 (`app.py`) → 核心抽象 (`core/`) → 可重用元件 (`components/`) → 功能視圖 (`views/`)**，
底層由三大系統引擎（`config.py` / `comfy_client.py` / `task_manager.py`）與統一日誌（`logger.py`）支撐。

### 🔩 系統引擎（專案根目錄）

- **`app.py` — 系統裝配進入點**
  在單一 `gr.Blocks` 內實例化並串接所有元件與視圖：Dashboard 模組切換（三大視圖容器可見性互斥）、
  裝置會話恢復（`restore_device_state`，頁面載入時綁定 55 個元件的輸入/播放器/按鈕狀態）、
  手動 Device ID 切換、`gr.Timer(1s)` 任務進度輪詢（`poll_active_task_progress`，跨會話保證即使重新整理或切換模組也能接回進行中任務），
  以及依管理者身分動態顯示三大管理分頁。`demo.queue(default_concurrency_limit=None)` 允許各裝置不限並發地提交串流進度請求。

- **`config.py` — 全域設定與計算定律**
  集中管理 ComfyUI 後端位址（`COMFY_SERVER_URL`，預設 `http://127.0.0.1:8188`）、WebUI 主機埠、
  MiniMax-H3 四大模型檔名（UNET/CLIP/Video VAE/Audio VAE）、長寬比與畫質等級選項（1~10 級對應 0.2~2.0 MP）、
  多組 `normalize_*` 防呆正規化函式，以及 `SERVER_STATUS` 維護旗標（檔案 `.server_status` + 環境變數 + 全域變數三層解析）。
  內建兩套核心計算定律：**解析度計算器**（`calculate_dimensions`：依目標百萬畫素將寬高吸附至 32 的倍數；
  I2V「原圖比例」模式以網格搜尋在面積誤差 ±18% 內找扭曲最小的組合）與**幀數吸附定律**
  （`align_frame_count`：MiniMax-H3 要求總幀數滿足 `17k + 5`，24 fps 下由 `duration_to_frames` 自動換算）。
  另提供 `get_upscale_models()` 動態掃描 `upscale_models` 模型目錄。

- **`comfy_client.py` — 唯一 ComfyUI 後端通訊層**
  封裝所有對 ComfyUI 的 REST/Process 操作：探針 `/system_stats`、啟動資源預檢
  （`check_system_resources`：可用 RAM > 50GB、GPU 佔用 < 20%、可用 VRAM > 9.5GB，psutil + nvidia-smi + torch 三層備援）、
  後端進程啟停（自動生成 ComfyUI-Desktop venv 進程、以 port 8188 反查 PID 清理）、媒體上傳 `/upload/image`、
  工作流提交 `/prompt`、任務中斷（`/api/jobs/{id}/cancel`、佇列移除 `/queue delete`、`/interrupt`）、
  產出下載 `/view` → 存至 `outputs/`、顯存釋放 `/free`、佇列清空，以及 `get_system_dashboard_data()`
  彙整 RAM/GPU/磁碟/佇列資料供管理儀表板。模組層級變數 `_COMFY_PROCESS` 追蹤由本 WebUI  spawn 的後端進程。

- **`task_manager.py` — 執行緒安全任務佇列與持久化**
  全域單例 `task_manager` 管理所有 `Task` 物件。每個生成請求建立一筆 `Task`
  （任務類型 `I2V/T2V/R2V/UPSCALER`、**所屬模組 `module`（minimax/upscaler/strata）**、參數、device_id、
  狀態機 `queued → running → completed/failed/interrupted`、進度/階段/當前節點），
  歷史以原子寫入持久化至 `outputs/task_history.json`（僅保留最近 100 筆），
  輸入影像/影片同步歸檔至 `outputs/inputs/`。所有查詢皆經 `_is_same_device` 執行嚴格裝置隔離，並可帶
  `module=` 執行模組隔離（歷史畫廊、會話恢復、輪詢皆為模組意識）。
  **`start_background_task` 為全域 FIFO 串列調度**：任務暫存於待調度佇列（訊息 `⏳ 排隊中...（前面還有 N 個工作）`），
  由常駐 dispatcher 執行緒確認後端空閒後，一次一個依序提交 ComfyUI——不同模組的任務優雅排隊，
  不再互相搶占 GPU 或誤殺對方的任務。工作者執行緒：提交 → 開啟專屬 WebSocket 監聽 `progress`/`executing`
  推播（換算精確步數百分比與階段）→ 每 0.5 秒輪詢 `/history` 與 `/queue` 雙保險 → 完成後自動下載影片並標記。
  `interrupt_device_tasks(device_id, module=...)` 支援模組化中斷（各模組 🛑 只停自己的任務），
  `delete_task` 會同步從佇列清除尚未排隊執行的工作。
  **重啟救援**：載入歷史時，仍在 WebUI 佇列中、從未送達 ComfyUI 的 queued/running 任務
  （`prompt_id` 為空）會自動降級為已中斷並提示重新提交，避免裝置介面永久卡在「排隊中」；
  已送達後端的任務則維持原狀，由 `/history` 同步機制自動接手復原。
  亦提供 `get_all_tasks`、裝置總彙整等管理者全域視角。

- **`workflow_builder.py` — MiniMax-H3 工作流圖構建器**
  純函式組裝 ComfyUI API 格式節點圖（UNET/CLIP/雙 VAE 載入器、影像與文字編碼、Latent 生成、
  `res_multistep` 取樣、VAE 解碼與 SaveVideo），三大生成模式各一把 builder：`build_i2v_workflow`、
  `build_t2v_workflow`、`build_r2v_workflow`。影格長度由 `duration_to_frames` 自動換算為 17k+5 幀。

- **`logger.py` — 統一彩色日誌**
  ANSI 色彩控制台格式化器 + 統一 `[時間][等級][模組]` 格式；Windows 下自動強制 stdout/stderr UTF-8 輸出。

### 🧱 `core/` 物件導向抽象層

- **`base_view.py` `BaseView`**：所有功能視圖的抽象基類，定義生命週期契約——
  `render()` 建構佈局、`register_events()` 綁定事件、`get_restore_components()` / `restore_state()` 會話恢復協議。
- **`comfy_view.py` `ComfyUIBaseView`**：繼承 `BaseView`，疊加維護模式檢查（`is_maintenance_mode`），
  為 MiniMax 與 Upscaler 兩大 ComfyUI 模組共用。
- **`session_context.py` `SessionContext`**：以兩個 `gr.BrowserState`（`minimax_device_id`、`minimax_active_task_id`）
  將裝置身分與活躍任務 ID 常駐瀏覽器 localStorage；所有任務、歷史、進度隔離皆以這個 device_id 為基準。
- **`admin_manager.py` `AdminManager`**：靜態特權與維運中樞——超级用戶判定（loopback + 本機內網卡 +
  `outputs/admin_ips.json` 白名單，含 IPv4-mapped IPv6 `::ffff:` 正規化）、維護模式切換、
  硬體/佇列/裝置/全域任務等管理 HTML 儀表板渲染、管理員 IP 增刪與權限防護。
- **`base_admin_tab.py` → `comfy_admin_tab.py`（Template Method 繼承鏈）**：
  `BaseAdminTab` 渲染通用區塊（服務狀態切換、硬體儀表板、裝置總覽、管理員 IP 名單），
  預留 `render_custom_content` / `register_custom_events` 鉤子；`ComfyUIAdminTab` 再疊加
  Purge VRAM、後端重啟（同样有活躍任務防護）、ComfyUI 佇列監控與中斷/清空，預留 `render_comfy_content` / `register_comfy_events`
  給各模組專屬管理 tab（MiniMax 全域任務管理、Upscaler Tile 快取、Strata LLM 端點設定）。
- **`port_guardian.py` `PortGuardian`**：啟動前 port 7860 佔用探測，佔用時印出 Windows 診斷
  （netstat 反查 PID、taskkill 建議指令），確保固定連接埠而不跳號。

### 🎛 `components/` 可重用 UI 元件

- **`styles.py`**：全域 CSS（卡片化、主按鈕、狀態框、側欄收合拉頁籤高對比化）與 `<head>` JS
  （裝置代碼一鍵複製、✏️ 觸發 ID 切換列、側欄樣式）。
- **`header.py`**：頂部橫幅——系統名稱、內網連線網址、可複製的 6 碼 Device ID 徽章、維護模式紅色警示橫幅，
  以及隱藏的手動切換裝置 ID 列。
- **`dashboard_sidebar.py`**：左側可收合 `gr.Sidebar` 控制台，以 `gr.Radio` 三選一切換核心模組
  （minimax / upscaler / strata），驅動三個視圖容器的可見性；
  收合方式：展開時點右上角「‹」拉頁籤，收起時點螢幕左緣「›」拉頁籤（高對比可見樣式）。
- **`comfy_toolbar.py`**：ComfyUI 後端工具列——啟動按鈕（資源預檢 + 狀態循環 ⚡/🟡/🟢）、🛑 一鍵關閉後端
  （有任務在排隊/生成中時自動擋下，不會誤斷進行中的工作），由 `gr.Timer(0.5s)` 輪詢刷新按鈕狀態。
- **`video_params.py` `VideoParamsComponent`**：MiniMax 三個生成 tab 共用的參數卡片
  （長寬比、畫質等級、即時輸出解析度預覽、時長/步數/FPS 滑桿，進階折疊區：種子+🎲、去噪、取樣器、調度器）。
- **`media_player.py`**：`build_progress_html()` 黃色進度條（步數→百分比、狀態訊息兩行截斷）、
  `VideoPlayerCardComponent`（狀態條 + 🔄 恢復上次輸入與成果按鈕 + 輸出播放器 +
  🖼️ 提取最後一幀 / 💾 下載最後一幀（`gr.DownloadButton`，由 `frame_extractor` 於伺服器端抽幀）、
  `ActionButtonsComponent`（🚀 生成 / 🛑 停止成對按鈕）。
- **`history_gallery.py`**：歷史畫廊（刷新、下拉選單、選取播放、刪除），列表來自
  `task_manager.get_completed_tasks_for_device`，目前以單一 `task_type` 參數過濾。

### 🗂 `views/` 三大功能模組

- **`views/minimax/`（模組 1：MiniMax-H3 視訊生成，穩定）**
  `MiniMaxView` 聚合三個子分頁——`I2VTab`（首幀/尾幀圖片，自動偵測原圖比例並鎖死無扭曲輸出）、
  `T2VTab`（純文字生成）、`R2VTab`（參考圖/影片/音訊驅動），各以 Gradio generator 串流 yield 進度；
  另含歷史畫廊與 `MiniMaxAdminTab`（全域跨裝置任務篩選、預覽、刪除、一鍵清理失敗任務）。
  每個分頁的播放器卡片提供「🖼️ 提取最後一幀 → 💾 下載最後一幀」流程：
  點擊後由後端（PyAV，ffmpeg 備援）抽出目前影片的最後一幀存成 PNG，下載鈕隨即出現供使用者儲存。
  `restore_state` 依任務類型回覆 I2V(14) / T2V(12) / R2V(19) 元件的恢復更新，並依活躍任務類型切換六個生成/停止按鈕。
- **`views/upscaler/`（模組 2：視訊超解析放大，Beta）**
  `UpscalerView` 提供來源影片上傳、超解析模型下拉選單（掃描 `upscale_models` 目錄）、生成/中斷、
  專屬放大紀錄 tab 與 `UpscalerAdminTab`（Tile 快取清理，目前為佔位實作）。
  `workflow_builder.py` 建構 6 節點拓撲：`UpscaleModelLoader → LoadVideo → GetVideoComponents →
  ImageUpscaleWithModel → CreateVideo → SaveVideo`，保留原始 FPS 與音軌。
  搶占與歷史串紀錄問題已修復：任務經全域串列佇列與 minimax 和平共處、互不搶占，
  專屬紀錄 tab 以 `module="upscaler"` 嚴格隔離，不再出現其他模組的任務。
- **`views/strata/`（模組 3：Strata Qwen3.8 LLM，尚未實作後端）**
  `StrataView` 目前為對話 UI 骨架（Chatbot、系統提示詞、Temperature），回覆為佔位 mock；
  `StrataAdminTab` 提供 LLM API Base/Key 設定介面（Ollama/vLLM/OpenAI 相容），實際串接為後續任務。
- **`views/admin/`**：`AdminPanelView` 為 `MiniMaxAdminTab` 的向前相容別名。

### 🔁 一次生成任務的完整資料流

```text
使用者點擊生成（generator 函式，串流 yield 進度 HTML）
  ├─ 1. 維護旗標檢查 / 參數防呆 / 後端探針 check_server
  ├─ 2. comfy_client.upload_media_file → 圖片或影片傳入 ComfyUI input 目錄
  ├─ 3. workflow_builder → 組出 ComfyUI API prompt 節點圖
  ├─ 4. task_manager.create_task → 建 Task、歸檔輸入、寫入 task_history.json
  ├─ 5. task_manager.start_background_task → 進入全域 FIFO 串列佇列（跨模組任務在此排隊，互不搶占）
  │        └─ 常駐 dispatcher 確認後端空閒 → /prompt 提交 → 工作者執行緒
  │             ├─ WebSocket 監聽 progress/executing + 0.5s 輪詢 /history、/queue
  │             └─ 完成 → /view 下載影片至 outputs\ → Task 標記 completed → dispatcher 取出下一個任務
  ├─ 6. 生成器每 0.5s yield build_progress_html + 影片路徑，直到終態
  └─ 7. gr.Timer(1s) poll_active_task_progress 兜底：重新整理/切換模組/背景完成都能接回
```

### 📁 `outputs/` 執行期資料

- 生成/下載的影片檔（`時間戳_檔名.mp4`）、`task_history.json`（任務持久化庫）、
  `inputs/`（輸入媒體歸檔）、`admin_ips.json`（管理員白名單）。

---

## 🚀 快速啟動指南

### 1. 啟動 WebUI
雙擊執行專案目錄下的 `run.bat`：
```cmd
F:\program_file\AI_webUI\run.bat
```
啟動後終端機會印出本機與行動裝置連線資訊：
```text
============================================================
MiniMax-H3 Gradio WebUI Starting (Port: 7860)...
Local Access: http://127.0.0.1:7860
Mobile LAN Access: http://192.168.1.100:7860
ComfyUI Backend: http://127.0.0.1:8188
============================================================
```

### 2. 啟動 ComfyUI 後端
WebUI 首頁工具列內建後端管理器：
- **檢查與啟動**：若 ComfyUI 尚未啟動，點擊頂部 **「⚡ 檢查後端模型狀態...」** 按鈕，系統將自動啟動 ComfyUI 背景服務並掛載模型庫。
- **終止後端**：點擊 **「🛑」** 按鈕可一鍵釋放後端 GPU 記憶體並優雅關閉進程；
  若仍有工作正在執行或排隊中，系統會拒絕關閉並提示剩餘工作數，避免誤殺任何人的生成任務。

---

## 🔧 伺服器維護與更新旗標 (Server Maintenance Mode)

系統內建全域維護狀態控制旗標，讓管理者在進行模型庫更新、代碼部署或除錯時，可隨時將 WebUI 切換至維護模式，防止使用者在維護期間發送生成任務：

### 1. 啟用維護模式 (UPDATING)
- **方式 A（修改配置檔）**：
  在 `config.py` 中將旗標修改為：
  ```python
  SERVER_STATUS = SERVER_STATUS_UPDATING
  ```
- **方式 B（環境變數啟動）**：
  在啟動 WebUI 前設定環境變數：
  ```cmd
  set SERVER_STATUS=UPDATING
  run.bat
  ```
- **方式 C（Python 程式調用）**：
  ```python
  from config import set_server_status, SERVER_STATUS_UPDATING
  set_server_status(SERVER_STATUS_UPDATING)
  ```

### 2. 維護模式下的系統行為
- **醒目警示橫幅**：WebUI 頁面頂部以紅色背景高亮顯示 `🔧 伺服器維護/更新中`。
- **後端狀態同步**：狀態列即時顯示 `🔧 伺服器維護/更新中`，點擊啟動按鈕會安全攔截並提示 `⚠️ 伺服器維護/更新中，暫停啟動後端`。
- **安全防護機制**：I2V、T2V、R2V 生成按鈕會主動阻斷任務提交，並顯示 `⚠️ 伺服器維護/更新中，暫停提交生成任務`，防止在維護中產生損毀任務。

### 3. 解除維護模式恢復服務 (OK)
維護與更新作業完成後，將旗標改回 `SERVER_STATUS_OK`（或移除環境變數）即可瞬間恢復所有功能：
```python
from config import set_server_status, SERVER_STATUS_OK
set_server_status(SERVER_STATUS_OK)
```

---

## 📱 手機行動端連線說明

1. **同網域 Wi-Fi**：請確保手機與運行 WebUI 的電腦連線至相同的 Wi-Fi 路由器。
2. **網址前綴**：手機瀏覽器網址列請務必輸入 `http://`，例如：
   ```text
   http://192.168.1.100:7860
   ```
   > ⚠️ 請勿輸入 `https://`，以免因無 SSL 憑證導致連線失敗。
3. **防火牆連接埠放行**：若手機無法開啟網頁，請至 Windows Defender 防火牆新增「輸入規則」，放行 TCP 連接埠 `7860`。

---

## 🧪 自動化測試與品質保證

專案具備健全的三階段測試體系，涵蓋 122 項單元測試與雙核心端到端 (E2E) 測試套件。

### 一鍵執行所有測試
雙擊執行專案根目錄下的 `run_tests.bat`，系統將自動依序執行三階段驗證：
```cmd
F:\program_file\AI_webUI\run_tests.bat
```
執行階段包含：
1. `[1/3] Running Unit Tests (pytest)...`：122 項單元測試 100% 通過
2. `[2/3] Running MiniMax End-to-End (E2E) Test Suite...`：MiniMax 8 階段使用者生命週期測試
3. `[3/3] Running Video Upscaler End-to-End (E2E) Test Suite...`：Upscaler 9 階段使用者生命週期測試
   （含跨模組並發排隊與歷史隔離驗證）

---

### 1. 單元測試 (pytest)
```cmd
pytest tests/ -v
```
測試內容涵蓋：
- `test_admin_tabs.py`：驗證管理員 Tab 繼承架構 (`BaseAdminTab` -> `ComfyUIAdminTab` -> `MiniMax`/`Upscaler`/`Strata`)、IPv4-mapped IPv6 正規化、組件建立契約。
- `test_app_state.py`：驗證多裝置會話恢復、背景輪詢定時器、中斷任務事件、移除自訂尺寸防呆機制。
- `test_comfy_client.py`：驗證 ComfyUI 探針、佇列中斷 API、素材上傳、影片二進位串流下載。
- `test_config.py`：驗證 $17k + 5$ 幀數換算定律、16/32 像素對齊、百萬像素解析度換算。
- `test_logger.py`：驗證日誌輸出與格式器。
- `test_task_manager.py`：驗證嚴格裝置隔離、執行緒安全佇列、工作階段持久化、
  `module` 欄位新舊紀錄相容、模組化中斷不誤殺、FIFO 串列調度一次一工作與排隊訊息。
- `test_frame_extractor.py`：驗證最後一幀抽取正確性（紅藍雙色影片證明取到尾幀）、
  PyAV 失敗時 ffmpeg 備援生效、非法/損毀檔案回傳 None、最後一幀下載鈕 UI 契約。
- `test_upscaler.py`：驗證超解析模型掃描、工作流拓撲生成與 UI 視圖綁定。
- `test_queue_multidevice.py`：排隊機制進階場景——多裝置交錯到達的 FIFO 公平性、
  停止鈕之裝置／模組雙重隔離、定向中斷後佇列自動續跑、刪除排隊中任務、
  管理員全域屠殺清場、**重啟後未提交幽靈排隊任務自動降級為已中斷**（防 UI 永久卡「排隊中」）、
  重啟歷史不會被重新調度、多執行緒併發提交不遺失不重複不重疊。
- `test_workflow_builder.py`：驗證 I2V, T2V, R2V 工作流 JSON 節點拓撲正確性。

---

### 2. 端到端整合測試套件 (e2e_tests/)
在不依賴外部即時 GPU 運算的情況下，透過高仿真 In-Process Mock ComfyUI 伺服器，模擬真實使用者透過瀏覽器開啟 WebUI 操作的完整生命週期：

#### (1) MiniMax 影片生成端到端測試 (`e2e_tests/minimax_test_e2e.py`)
```cmd
python e2e_tests/minimax_test_e2e.py
```
- **Step 1**: 啟動 ComfyUI 後端與連線驗證 (`/system_stats`)
- **Step 2**: 前端 WebUI 伺服器啟動與 HTTP 200 健康檢查
- **Step 3**: 模擬使用者載入網頁與會話還原（舊版相容性與下拉選單正規化）
- **Step 4 & 5**: 發起即時 I2V 生成請求（自適應尺寸計算）並監聽串流進度推播直到 100% 完成
- **Step 6**: 使用者下載生成之 MP4 影片，校驗二進位 Magic Header (`ftyp` / `isom`)
- **Step 7**: 歷史畫廊檢索與多裝置隔離驗證（包含任務刪除與跨裝置防洩漏）
- **Step 8**: 優雅關閉 WebUI 與後端伺服器

#### (2) Video Upscaler 超解析端到端測試 (`e2e_tests/upscaler_test_e2e.py`)
```cmd
python e2e_tests/upscaler_test_e2e.py
```
- **Step 1**: 啟動 ComfyUI 後端與連線驗證
- **Step 2**: 前端 WebUI 伺服器啟動與 HTTP 200 健康檢查
- **Step 3**: 模擬使用者載入網頁並自動掃描 `upscale_models` 目錄發現可選模型
- **Step 4 & 5**: 發起影片超解析請求 (`utility-gan_upscaler.json` 6 節點拓撲驗證）並監聽串流進度直到完成
- **Step 6**: 使用者下載放大後影片並校驗二進位標頭完整性
- **Step 6.5**: 跨模組並發驗證：同一裝置先提交 MiniMax I2V、執行中再提交放大任務，
  證明串列調度器讓兩者依序完成（放大任務提交至後端的時間點落在 I2V 任務完成之後）、
  互不搶占不誤殺，且同裝置下兩邊歷史畫廊完全隔離
- **Step 7**: 超解析專屬歷史畫廊檢索與跨裝置隔離驗證（包含任務刪除）
- **Step 8**: 優雅關閉 WebUI 與後端伺服器

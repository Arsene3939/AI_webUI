# AI WebUI 整合式工作台 (MiniMax / Video Upscaler / Strata LLM)

高效、模組化且具備物件導向架構的 Gradio AI 整合前端。內建左上角全域控制台 (Dashboard)，支援三大核心生成與對話模組一鍵切換，並具備嚴格的裝置隔離、任務搶佔與斷線自動重連機制。系統透過 REST API 解耦架構對接 ComfyUI 與 LLM 後端，支援電腦本機與行動裝置跨設備無縫連線。

---

## 📑 目錄

- [✨ 核心功能特色](#-核心功能特色)
- [🎯 三大核心模組實作狀態一覽 (Implementation Status)](#-三大核心模組實作狀態一覽-implementation-status)
- [🏗️ 系統架構與關鍵機制](#️-系統架構與關鍵機制)
  - [1. 模組化與物件導向架構 (Modular & OOP Architecture)](#1-模組化與物件導向架構-modular--oop-architecture)
  - [2. 階層式管理員架構 (Hierarchical Admin Tab & OOP Inheritance)](#2-階層式管理員架構-hierarchical-admin-tab--oop-inheritance)
  - [3. 任務搶佔與即時中斷機制 (Task Preemption)](#3-任務搶佔與即時中斷機制-task-preemption)
  - [4. 斷線重連與背景自動同步 (Session Auto-Sync)](#4-斷線重連與背景自動同步-session-auto-sync)
  - [5. 嚴格裝置隔離與工作階段保存 (Multi-Device Isolation)](#5-嚴格裝置隔離與工作階段保存-multi-device-isolation)
  - [6. 解析度與畫質動態對齊演算 (Dimension Alignment)](#6-解析度與畫質動態對齊演算-dimension-alignment)
  - [7. 幀數對齊定律 (MiniMax 17k + 5 Rule)](#7-幀數對齊定律-minimax-17k--5-rule)
- [🎬 三大核心模組詳細說明](#-三大核心模組詳細說明)
- [📂 專案檔案結構](#-專案檔案結構)
- [📐 參數規範與計算公式](#-參數規範與計算公式)
- [🚀 快速啟動指南](#-快速啟動指南)
- [🔧 伺服器維護與更新旗標 (Server Maintenance Mode)](#-伺服器維護與更新旗標-server-maintenance-mode)
- [📱 手機行動端連線說明](#-手機行動端連線說明)
- [🧪 自動化測試與品質保證](#-自動化測試與品質保證)

---

## ✨ 核心功能特色

1. **左側 Dashboard 側邊欄三大模組整合導航 (gr.Sidebar)**：
   * 採用 Gradio 原生側邊欄 `gr.Sidebar` 取代傳統下拉選單 (`gr.Dropdown`)，支援隨時平滑展開與收合。
   * **🎬 ComfyUI: MiniMax Video Generator**：I2V、T2V、R2V 全模態視訊生成，自動音視頻合流。
   * **🔍 ComfyUI: Video Resolution Upscaler**：視訊超解析放大與畫質增強工作台。
   * **💬 Strata: Qwen3.8-flash-next LLM**：提示詞優化與智慧助理對話工作台。
2. **階層式物件導向管理員介面 (Tab-Level Admin)**：
   * 管理員介面依循物件導向繼承設計，直接嵌入各模組的 Tab 標籤頁內，徹底告別孤立頁面。
   * 支援 Dual-Stack IPv4-mapped IPv6 自動識別，本機 (`localhost` / `127.0.0.1`) 與局域網白名單自動放行。
3. **任務即點即做（零排隊浪費）**：
   * 再次點擊「生成影片」時，系統立即中斷當前裝置正在運算的舊任務與 ComfyUI 佇列，直接提交並執行最新指令，無須手動終止後台進程。
4. **重連自動恢復（免手動重整）**：
   * 使用者在生成期間即便切換 App、熄螢幕或重新開啟瀏覽器，系統自動透過 Device ID 找回會話，背景生成完畢自動更新進度與預覽影片。
5. **直覺化畫質與尺寸運算（防呆無錯）**：
   * 介面全面移除容易誤填的寬高文字框，完全由「長寬比」與「品質檔次（Megapixels）」唯一數學映射，並強制對齊 16/32 像素倍數，杜絕比例畸變。
6. **行動端原生友善 (Mobile First)**：
   * 大尺寸拇指操作按鈕、滑動標籤頁、自動辨識區網 IP 顯示手機掃碼連線資訊。

---

## 🎯 三大核心模組實作狀態一覽 (Implementation Status)

針對三個模組的實際功能完備度，以下詳述各模組當前狀態、已落地功能與後續待對接項目：

| 模組名稱 | 類別與定位 | 實作狀態 | 當前已實作功能 (Done) | 待實作 / 規劃中功能 (Pending) |
| :--- | :--- | :---: | :--- | :--- |
| **🎬 ComfyUI: MiniMax Video Generator** | 視訊生成核心 | **✅ 100% 完整就緒** | • 圖生影片 (I2V / `fl2va`，支援首幀必填、尾幀選填)<br>• 文生影片 (T2V / `t2va`，純文字驅動音視訊)<br>• 參照生影片 (R2V / `ref2va`，支援 4 圖 + 視訊 + 音訊與 `<Picture 1>` 錨定)<br>• 自適應原圖比例網格搜尋演算 (誤差 < 0.3%)<br>• $17k+5$ 幀數吸附定律與 32 像素硬體編碼對齊<br>• 任務搶佔與即時中斷機制 (`TaskManager.interrupt_device_tasks`)<br>• 斷線背景自動輪詢與工作階段恢復 (`BrowserState`)<br>• 獨立歷史紀錄畫廊與單筆記錄刪除<br>• 專屬 MiniMax 管理員 Tab (跨裝置任務過濾、參數檢視、強制終止) | • 多段提示詞關鍵幀插值動畫 (Keyframe Interpolation) |
| **🔍 ComfyUI: Video Resolution Upscaler** | 視訊超解析放大 | **🟡 介面與架構就緒<br>後端工作流待對接** | • 視訊上傳拖曳與預覽卡片<br>• 放大倍率選擇 (2x / 4x)<br>• 超解析模型選擇 (RealESRGAN_x4plus, Compact, HAT)<br>• 分塊大小 (Tile Size: 128~512px) 與融合邊界 (Tile Blending) 參數卡片<br>• 播放器卡片與進度條 UI<br>• 歷史超解析紀錄列表佈局<br>• 專屬 Upscaler 管理員 Tab (繼承 `ComfyUIAdminTab`，具備顯存清理、重啟後端、Tile Cache 介面) | • ComfyUI 超解析工作流節點圖生成器 (`views/upscaler/workflow_builder.py`)<br>• 後端視訊音訊分離與音軌無損合成分離管線 (VHS_LoadVideo -> UpscaleModelLoader -> ImageUpscaleWithModel -> VHS_VideoCombine)<br>• 實體 Tile Cache 暫存目錄清理邏輯 |
| **💬 Strata: Qwen3.8-flash-next LLM** | 智慧助理與提示詞優化 | **🟡 介面與架構就緒<br>推論端點待對接** | • 現代化對話聊天室 (`gr.Chatbot`)<br>• 系統提示詞設定 (預設 MiniMax 專用分鏡提示詞工程師角色)<br>• 溫度 (Temperature)、Top-P、Max Tokens 調節滑桿<br>• 對話控制操作 (清空、重試、撤銷)<br>• 本地 Echo 回應處理器 (用於前端排版、對話流與狀態流轉測試)<br>• 專屬 Strata 管理員 Tab (繼承 `BaseAdminTab`，支援後端端點 URL、API Key 憑證與模型切換) | • 實體 LLM API 串流對接：本機 Ollama / vLLM 或 OpenAI 相容 API (`/v1/chat/completions` SSE 串流)<br>• MiniMax 提示詞優化器 (Prompt Refiner) 一鍵聯動 (產出提示詞一鍵發送至 I2V/T2V 欄位)<br>• 對話歷程儲存與 Markdown / JSON 匯出 |
| **⚙️ 階層式管理員系統 (Admin Tab)** | 系統運維與後端控制 | **✅ 100% 完整就緒** | • 物件導向階層設計 (`BaseAdminTab` -> `ComfyUIAdminTab` -> 各模組專屬 Tab)<br>• 嵌入各模組 Tab 內部，操作直覺不孤立<br>• 伺服器狀態維護模式開關 (UPDATING / OK)<br>• Dual-Stack IPv4-mapped IPv6 (`::ffff:127.0.0.1`) 自動正規化免白名單登入<br>• 後端進程重啟與 GPU 顯存釋放 (Purge VRAM)<br>• 跨裝置任務監控、詳情檢視與強制終止 | • 系統效能圖表歷史追蹤 (Prometheus/Grafana 導出) |

---

## 🏗️ 系統架構與關鍵機制

```mermaid
flowchart TD
    subgraph Client ["Client Browser / Mobile Phone"]
        UI["Gradio WebUI (HTML5 / Mobile CSS)"]
        Dashboard["Dashboard Sidebar (gr.Sidebar Left Dock)"]
        BS["gr.BrowserState (Device ID & Task ID)"]
        Timer["gr.Timer (1.0s Background Poll)"]
    end

    subgraph Core_Views ["Modular OOP Views (views/)"]
        MiniMaxV["MiniMaxView (I2V / T2V / R2V / Admin Tab)"]
        UpscalerV["UpscalerView (Upscale / History / Admin Tab)"]
        StrataV["StrataView (Chatbot / System Prompt / Admin Tab)"]
    end

    subgraph Admin_Hierarchy ["OOP Admin Hierarchy (core/ & views/*/admin_tab.py)"]
        BaseAdmin["BaseAdminTab (Maintenance, HW Dashboard, Devices, Whitelist)"]
        ComfyAdmin["ComfyUIAdminTab (Purge VRAM, Restart Backend, Queue Status)"]
        MMAdmin["MiniMaxAdminTab (Task Filter & Inspection)"]
        UpAdmin["UpscalerAdminTab (Tile Cache Management)"]
        StAdmin["StrataAdminTab (LLM Endpoint & API Key)"]
        BaseAdmin --> ComfyAdmin
        ComfyAdmin --> MMAdmin
        ComfyAdmin --> UpAdmin
        BaseAdmin --> StAdmin
    end

    subgraph Backend_Services ["Backend Services"]
        ComfyUI["ComfyUI Backend (:8188)"]
        LLM["LLM Inference Service (Ollama / vLLM / OpenAI API)"]
    end

    Dashboard -->|"切換可見視圖"| Core_Views
    MiniMaxV -->|"包含"| MMAdmin
    UpscalerV -->|"包含"| UpAdmin
    StrataV -->|"包含"| StAdmin
    MiniMaxV -->|"REST / WS"| ComfyUI
    UpscalerV -.->|"超解析工作流 (待接)"| ComfyUI
    StrataV -.->|"SSE 串流 (待接)"| LLM
```

### 1. 模組化與物件導向架構 (Modular & OOP Architecture)
為了解決原先單一 `app.py` 超過 2400 行、程式碼臃腫且嚴重缺乏抽象的問題，系統完成了全面的模組化與物件導向重構：
- **`core/base_view.py` (`BaseView`)**：定義所有視圖的生命週期標準契約（`render`, `register_events`, `restore_state`, `poll_progress`）。
- **`core/comfy_view.py` (`ComfyUIBaseView`)**：繼承 `BaseView`，封裝 ComfyUI 後端狀態工具列與維護模式安全攔截。
- **`components/`**：高度封裝可複用元件（長寬比與品質滑桿、影片播放器與進度條、ComfyUI 啟停工具列、頂部橫幅、歷史畫廊），落實 **DRY** 原則。
- **`app.py`**：縮減至 470 餘行，僅負責全域佈局裝配與事件調度。

### 2. 階層式管理員架構 (Hierarchical Admin Tab & OOP Inheritance)
管理員介面不再作為獨立孤立的頁面，而是以 `gr.Tab("⚙️ 管理員")` 的形式自然融入各個視圖內部，並採用 **範本方法模式 (Template Method Pattern)** 實現繼承封裝：
1. **`BaseAdminTab` (通用管理員基類)**：
   - 封裝全域通用的「伺服器維護模式開關 (UPDATING / OK)」、「連線裝置管理」、「伺服器硬體負載監控」與「管理員 IP 白名單管理」。
2. **`ComfyUIAdminTab(BaseAdminTab)` (ComfyUI 後端管理員基類)**：
   - 擴充 ComfyUI 後端專用的「釋放 GPU 顯存 (Purge VRAM)」、「一鍵重啟後端進程」、「佇列狀態監控與中斷所有任務」。
3. **具體視圖專屬管理員 Tab**：
   - **`MiniMaxAdminTab(ComfyUIAdminTab)`**：加入跨裝置影片生成任務監控、任務參數詳情檢視與任務刪除。
   - **`UpscalerAdminTab(ComfyUIAdminTab)`**：加入超解析專屬之 Tile Cache 快取管理與超解析進程狀態。
   - **`StrataAdminTab(BaseAdminTab)`**：加入 LLM 端點 URL 配置、API Key 憑證設定與模型規格切換。

#### 🛡️ 管理員權限與本機 IP 正規化修復 (IPv4-mapped IPv6 Fix)
在 Windows 與 Uvicorn/FastAPI 雙棧網路環境下，本機請求的 `request.client.host` 常以 IPv4-mapped IPv6 形式呈現（如 `::ffff:127.0.0.1` 或 `::ffff:192.168.x.x`）。系統透過 `AdminManager.normalize_ip()` 進行標準化提取，並結合 `ipaddress.ip_address.is_loopback` 邏輯，確保本機 `localhost` 與 `127.0.0.1` 100% 具備管理員權限，同時各模組的管理員 Tab 統一受 `AdminManager.is_super_user()` 集中式權限校驗保護。

### 3. 任務搶佔與即時中斷機制 (Task Preemption)
- **觸發時機**：當使用者在影片尚未生成完畢前，調整參數並再次點擊「生成影片」按鈕。
- **後端處置**：
  1. `task_manager.interrupt_device_tasks(device_id)`：向該裝置的背景監控執行緒發出 `cancel_event.set()`，停止後續輪詢。
  2. `comfy_client.interrupt_execution(prompt_id)`：向 ComfyUI 發送 API 請求：
     - `POST /queue`：從 `queue_running` 與 `queue_pending` 刪除指定任務。
     - `POST /api/jobs/{prompt_id}/cancel`：取消特定任務 Job。
     - `POST /interrupt`：強制中斷當前 GPU 核心上的取樣運算。
  3. `Task` 狀態即時標記為 `"interrupted"`。
- **無縫接續**：舊任務中斷完成後，前端立即上傳最新素材並提交新工作流至 ComfyUI，實現「最新點擊優先執行」。

### 4. 斷線重連與背景自動同步 (Session Auto-Sync)
- 任務開始時，工作階段將任務識別碼寫入客戶端 `session_task_state` (`gr.BrowserState`)。
- 若使用者關閉瀏覽器或切換應用程式，伺服器背景執行緒仍持續監控並下載產出影片至 `outputs/` 目錄。
- 當使用者重新開啟網頁時：
  - `demo.load` 觸發 `restore_device_state`，恢復先前的參數與最後產出的影片。
  - 前端掛載之 `task_poll_timer`（每 1 秒觸發一次）自動調用 `poll_active_task_progress` 檢查進行中任務。
  - 任務一旦於背景完成，進度面板立即自動推播 100% 完成狀態，並將影片載入播放器中，**全程無須使用者手動點擊恢復或重新整理頁面**。

### 5. 嚴格裝置隔離與工作階段保存 (Multi-Device Isolation)
- 透過 `gr.BrowserState` 保存加密的 `minimax_device_id`（預設隨機產生 6 位數短 ID，例如 `71c8f5`）。
- 每個裝置的所有任務記錄、參數快照與歷程影片獨立歸屬於該 `device_id`。
- 「歷史生成紀錄」選單經過嚴格權限過濾，A 裝置絕對無法檢視或下載 B 裝置生成的影片。
- 支援「✏️ 手動切換裝置 ID」功能，更換手機或清除 Cookie 時，只需輸入舊的 6 位數 ID 即可瞬間找回所有歷程。

### 6. 解析度與畫質動態對齊演算 (Dimension Alignment)
- 前端徹底移除 `custom_w` 與 `custom_h` 輸入框，避免使用者輸入不支援的尺寸或非整數倍數導致報錯。
- **合法輸出影片解析度標準**：
  1. **空間倍數對齊**：MiniMax-H3 的 Spatial VAE compression 為 16x，DiT 空間 Patch 為 2x2（官方節點規範 `CANVAS_MULTIPLE = 32`, `step=32, min=32`），影片編碼同樣要求能被 16 或 32 整除。因此，寬高必須同時為 **32 的整數倍**。
  2. **總像素面積**：緊密貼合所選畫質檔次：$\text{area} = \text{Megapixels} \times 10^6$（基準畫質約 1.03 MP，單幀建議範圍 0.2 MP ~ 2.0 MP，短邊 $\ge 256$，長邊 $\le 2048$）。
  3. **首幀零畸變**：因 ComfyUI `MiniMaxH3ImageToVideo` 節點以 `"disabled"` 裁切直接無襯墊拉伸首幀，長寬比必須極致對齊原圖。
- **自適應原圖比例網格搜尋演算法 (Adaptive AR Grid-Search)**：
  - I2V 與 R2V 預設選用 **「原圖比例 (自動對齊)」**。
  - 上傳圖片時，系統讀取原圖真實尺寸 $(W_{orig}, H_{orig})$ 計算真實比例 $r = W_{orig} / H_{orig}$，並在目標面積 $\pm 18\%$ 範圍內的 32 倍數微調網格中搜尋：
    $$\text{Score} = 100 \times \frac{|\frac{W}{H} - r|}{r} + \frac{|\text{Area} - \text{Target Area}|}{\text{Target Area}}$$
  - 挑選出 $\text{Score}$ 最小的最優整數 $(W, H)$，使拉伸誤差低於 0.3%（甚至 0.00%，例如 1500x1000 輸出 1248x832），同時滿足 32 像素硬體編碼標準。
  - 使用者亦可隨時切換至固定標準比例（16:9, 9:16, 1:1, 4:3, 3:4, 21:9）。

### 7. 幀數對齊定律 (MiniMax 17k + 5 Rule)
MiniMax-H3 的時空潛空間 (Temporal Latent) 遵循嚴格的步進公式：
$$F = 17k + 5 \quad (k \in \mathbb{N}, k \ge 1)$$
系統會根據使用者設定的秒數（預設 24 FPS）自動四捨五入吸附至最接近的有效幀數（例如 5.0 秒 $\approx 120$ 幀，自動吸附至 $k=7$ 的 $124$ 幀），確保 VAE 解碼時不發生時序維度不合的崩潰。

---

## 🎬 三大核心模組詳細說明

### 1. 🎬 ComfyUI: MiniMax Video Generator
| 模式名稱 | 工作流代號 | 核心輸入節點 | 適用情境與特色 |
| :--- | :--- | :--- | :--- |
| **圖生影片** | `I2V` (`fl2va`) | `LoadImage` (首幀), `LoadImage` (可選尾幀) | 靜態插畫動態化、首尾分鏡過渡平滑演繹 |
| **文生影片** | `T2V` (`t2va`) | `CLIPTextEncodeMiniMax` (正負提示詞) | 概念發想、純文字分鏡直接驅動音視訊 |
| **參照生影片** | `R2V` (`ref2va`) | `LoadImage` (1~4張), `VHS_LoadVideo`, `LoadAudio` | 角色固定外貌演繹、動作捕捉遷移、音訊對嘴同步 |

### 2. 🔍 ComfyUI: Video Resolution Upscaler
針對生成品質進一步超解析度增強的專用模組：
- **核心控制**：支援 2x / 4x 放大比例切換，內建 RealESRGAN_x4plus、Compact、HAT 等超解析模型選項。
- **記憶體優化**：具備 Tile Size (128~512px) 與 Tile Blending 重疊融合參數，在大解析度輸出時有效防止顯存溢出 (OOM)。
- **後端狀態**：已建立前端 UI 與專屬管理員 Tab；目前 ComfyUI 節點工作流圖正在對接中。

### 3. 💬 Strata: Qwen3.8-flash-next LLM
專為 AI 影像創作者打造的智慧分鏡與提示詞助理：
- **角色預設**：預設封裝 MiniMax-H3 專業影片提示詞工程師 System Prompt，協助創作者將粗略概念擴充為富含光影、運鏡、粒子細節的高品質英文提示詞。
- **靈活調參**：提供 Temperature、Top-P、Max Tokens 參數控制，支援即時撤銷與清空對話。
- **後端狀態**：前端對話元件、狀態機制與管理員 Tab 已完整就緒，提供本地 Echo 測試，實體 Ollama / vLLM API 串接管線正在對接中。

---

## 📂 專案檔案結構

```text
F:\program_file\AI_webUI\
├── app.py                         # 系統整合進入點 (精簡裝配，~470行)
├── config.py                      # 全域常數設定、解析度計算與維護旗標
├── comfy_client.py                # ComfyUI API 通訊、WebSocket 進度與進程管理
├── task_manager.py                # 執行緒安全之多裝置任務佇列與儲存管理器
├── workflow_builder.py            # MiniMax-H3 工作流 JSON 節點圖構建器
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
│   ├── media_player.py            # 播放器與進度條卡片 (VideoPlayerCardComponent)
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
├── run.bat                        # Windows 一鍵啟動 WebUI 批次檔 (Port 7860)
├── run_dev.bat                    # 開發熱重載啟動批次檔
├── run_tests.bat                  # 全自動測試套件執行腳本
├── test_e2e.py                    # 端到端整合測試套件
├── spec.md                        # 專案需求與功能詳細規格文件
├── requirements.txt               # 專案 Python 相依套件列表
└── tests/                         # 單元測試目錄 (87 項測試 100% 通過)
    ├── test_admin_tabs.py         # 測試管理員 Tab 繼承架構、IP 正規化與組件生成
    ├── test_app_state.py          # 測試 UI 初始化、工作階段恢復、定時輪詢、中斷觸發
    ├── test_comfy_client.py       # 測試伺服器探針、上傳、下載、佇列中斷邏輯
    ├── test_config.py             # 測試 17k+5 幀數吸附、16 像素對齊、品質檔次正規化
    ├── test_logger.py             # 測試日誌輸出與格式器
    ├── test_task_manager.py       # 測試多裝置任務隔離、背景執行緒生命週期與中斷
    └── test_workflow_builder.py   # 測試 I2V, T2V, R2V 工作流節點拓撲正確性
```

---

## 📐 參數規範與計算公式

### 1. 畫質檔次與百萬像素 (Megapixels)

| 檔次標籤 | 百萬像素 (MP) | 16:9 解析度範例 | 適用場合 |
| :---: | :---: | :---: | :--- |
| `1 (0.2 MP - 測試預覽)` | 0.2 MP | $592 \times 336$ | 最快生成、構圖預覽、除錯測試 |
| `2 (0.4 MP - 快速生成)` | 0.4 MP | $848 \times 480$ | 快速出片、日常靈感探索 |
| `3 (0.6 MP - 輕量均衡)` | 0.6 MP | $1040 \times 576$ | 手機觀看、兼顧畫質與運算耗時 |
| `4 (0.8 MP - 高畫質)` | 0.8 MP | $1200 \times 672$ | 社群媒體高畫質短影音 |
| `5 (1.0 MP - 標準推薦)` | 1.0 MP | $1344 \times 752$ | 官方推薦基準畫質、細節豐富 |
| `6 (1.5 MP - 超清旗艦)` | 1.5 MP | $1632 \times 928$ | 大螢幕展示、極致紋理與光影表現 |

### 2. 支援之標準長寬比 (Aspect Ratios)
- `16:9 (橫向風景)`
- `9:16 (直向短影音)`
- `1:1 (正方形頭像)`
- `4:3 (標準電視螢幕)`
- `3:4 (直向構圖)`
- `21:9 (電影寬螢幕)`

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
- **終止後端**：點擊 **「🛑」** 按鈕可一鍵釋放後端 GPU 記憶體並優雅關閉進程。

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

專案具備健全的測試體系，涵蓋 87 項單元測試與端到端 (E2E) 測試。

### 一鍵執行所有測試
雙擊執行專案根目錄下的 `run_tests.bat`：
```cmd
F:\program_file\AI_webUI\run_tests.bat
```

### 1. 單元測試 (pytest)
```cmd
pytest tests/ -v
```
測試內容涵蓋：
- `test_admin_tabs.py`：驗證管理員 Tab 繼承架構 (`BaseAdminTab` -> `ComfyUIAdminTab` -> `MiniMax`/`Upscaler`/`Strata`)、IPv4-mapped IPv6 正規化、組件建立契約。
- `test_app_state.py`：驗證多裝置會話恢復、背景輪詢定時器、中斷任務事件、移除自訂尺寸防呆機制。
- `test_comfy_client.py`：驗證 ComfyUI 探針、佇列中斷 API、素材上傳、影片二進位串流下載。
- `test_config.py`：驗證 $17k + 5$ 幀數換算定律、16/32 像素對齊、百萬像素解析度換算。
- `test_task_manager.py`：驗證嚴格裝置隔離、執行緒安全佇列、工作階段持久化。
- `test_workflow_builder.py`：驗證 I2V, T2V, R2V 工作流 JSON 節點拓撲正確性。

### 2. 端到端整合測試 (E2E)
```cmd
python test_e2e.py
```
在不依賴外部即時 GPU 運算的情況下，透過高仿真 In-Process Mock 伺服器驗證完整生命週期：
1. 後端探針連線驗證
2. 前端 WebUI 啟動與 HTTP 200 健康檢查
3. 舊版工作階段參數自動相容升級
4. 即時提交生成任務與 SSE / 串流進度推播
5. MP4 檔案二進位 Magic Header 完整性校驗
6. 歷史畫廊檢索與嚴格多裝置跨權限防洩漏驗證
7. WebUI 與後端進程之優雅終止釋放

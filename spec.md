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

## 0. 重複提醒：注意事項
- 應避免UI介面出現過多開發相關字詞，讓使用者只看到他需要看到的東西
- 很多東西其實使用者根本不在乎，例如：支援電腦與手機... 

## 1. Sidebar 的設計與 Debug (已完成施工)

### 1.1 問題根因剖析
1. **手機端占滿全版問題**：
   - Gradio 前端打包之 `Index-B3LSO2or.css` 內建媒體查詢：
     `@media (width <= 768px) { .sidebar { width: 100vw !important; left: -100vw !important; } }`
     此規則以 `!important` 強制覆蓋 Python 端傳入的 `width` 參數，導致手機螢幕上一律強制撐滿 100vw。
   - **修復方案**：在 `components/styles.py` 中以更高優先級覆蓋：
     `@media (max-width: 768px) { .sidebar, div[class*="sidebar"] { width: 260px !important; max-width: 80vw !important; left: -260px !important; } }`
     確保無論在任何行動裝置螢幕下，展開寬度一律限制在 260px / 80vw 內。
2. **擠壓原有 UI 問題**：
   - Gradio 原生機制在側邊欄展開時，會於外層容器添加內距：
     `.sidebar-parent:has(.sidebar.open) { padding-left: var(--overlap-amount); }`
     造成主版面被強制往右擠壓變形。
   - **修復方案**：強制將父容器的內距重設為 0：
     `.sidebar-parent, .sidebar-parent:has(.sidebar.open) { padding-left: 0 !important; }`
     並為 `.sidebar.open` 增加陰影浮層效果 (`box-shadow: 6px 0 24px rgba(0,0,0,0.6)` 與 `z-index: 1005`)，實現真正的抽屜式懸浮覆蓋 (Overlay)。
3. **精簡選項與去除贅字**：
   - 全面移除冗長的「使用說明」文字與多餘的快捷按鈕區塊。
   - 僅保留俐落的**三行核心選項** (`gr.Radio` 樣式化卡片)，點擊即切換，無下拉選單遮擋問題。

---

## 2. 準備 Upscaler (影片超解析度放大) 實作分析

為確保後續 Upscaler 模組施工平穩無痛，以下全面盤點目前「尚未就緒的元件」與「高機率產生 Bug 的技術風險」：

### 2.1 目前還沒準備好 (尚未實作) 的部分
1. **ComfyUI 專屬超解析工作流 JSON 節點圖構建器 (`views/upscaler/workflow_builder.py`)**：
   - 需實作類似 MiniMax 的節點圖生成器，定義下列節點之連線拓撲：
     - `VHS_LoadVideo`：輸入影片解碼為 Batched Image Frames 與 Audio。
     - `UpscaleModelLoader`：載入超解析模型檔 (如 RealESRGAN, HAT, Compact)。
     - `ImageUpscaleWithModel` 或 `ImageTileUpscale`：影格分塊放大核心運算。
     - `VHS_VideoCombine`：影格重新合成為 MP4。
2. **音訊無損合流管線 (Audio Preservation)**：
   - 影像超解析模型僅處理視覺影格，若直接將放大後之影格重新編碼，原始影片中的聲音軌道將遺失。
   - 需確保 `VHS_LoadVideo` 的音訊輸出埠直接連線至 `VHS_VideoCombine` 的音訊輸入端，或後端透過 `ffmpeg` 二進位處理無損混流。
3. **任務管理器架構相容 (`task_manager.py`)**：
   - 目前 `Task` 資料結構與 `create_task` 主要專屬 MiniMax 欄位 (`mode`, `aspect_ratio`, `duration`, `quality_level`)。
   - 需擴充支援 `task_type="upscale"`，包含 `scale_factor` (2x/4x)、`model_name`、`tile_size`、`tile_blending` 與來源影片路徑。
4. **ComfyUI 自訂節點與模型權重依賴檢核**：
   - ComfyUI 根目錄需安裝 `ComfyUI-VideoHelperSuite` 插件。
   - ComfyUI `models/upscale_models/` 目錄需具備對應模型檔（如 `RealESRGAN_x4plus.pth`）。
5. **Tile 快取實體清理邏輯 (`on_clean_tile_cache`)**：
   - `UpscalerAdminTab` 的「清理 Tile 快取」按鈕目前為 UI 存根，尚未綁定實際刪除磁碟快取目錄之回呼。

### 2.2 可能會出 Bug 的技術風險與防呆規劃
1. **GPU 顯存溢出 (CUDA Out-of-Memory, OOM)**：
   - **風險**：影片 4x 放大將使像素暴增 16 倍（例如 1080p 放大至 4K）。若單次將整張超大影格送入神經網路，一般顯卡 (8GB~16GB VRAM) 將直接爆發 CUDA OOM 崩潰。
   - **防禦**：必須嚴格啟用分塊放大機制 (`Tile Upscale`，預設 256~512px)，並在邊界重疊 16~32px 進行 Alpha 融合；或依據可用 VRAM 動態限縮單次推論之 Batch Size (如 1~4 幀)。
2. **影格率 (FPS) 失針與音畫不同步**：
   - **風險**：不同輸入影片具有不同幀率（如 23.976, 24, 25, 29.97, 30, 60 FPS）。若 `VHS_VideoCombine` 寫死固定幀率（如 24 FPS），輸出影片將出現畫面播放過快或變慢，導致音畫完全分離。
   - **防禦**：必須從 `VHS_LoadVideo` 讀取並動態傳遞原始影片的真實 FPS，確保輸出與原始輸入 100% 吻合。
3. **影片編碼格式相容性問題**：
   - **風險**：使用者可能上傳特殊編碼（如 HEVC/H.265 10-bit、AV1、Apple ProRes、非標準長寬像素比），ComfyUI 內建 OpenCV 或 ffmpeg 解碼可能引發例外中斷。
   - **防禦**：在提交任務前，後端執行快速格式嗅探與有效性驗證；必要時先由後端 ffmpeg 轉碼為標準 H.264 再送入工作流。
4. **超長運算時長導致輪詢逾時**：
   - **風險**：一段 5~10 秒的影片（120~240 幀），4x 放大耗時常達 2~8 分鐘。若 HTTP / WebSocket 輪詢沒有設定心跳或逾時門檻過短，前端會誤判任務失敗。
   - **防禦**：比照 MiniMax 的背景執行緒架構，以 TaskManager 獨立 Thread 監聽 ComfyUI 進度，定時推播百分比與當前放大影格數 (如 `第 45/120 幀`)。
5. **多任務併行與中斷隔離 (Cross-Module Preemption)**：
   - **風險**：使用者在 Upscaler 生成途中切換至 MiniMax 生成影片，若呼叫全域中斷，可能誤殺正在進行中的超解析運算。
   - **防禦**：中斷邏輯需精確指定 `task_id`，確保 MiniMax 與 Upscaler 各自的任務互不影響。


### 2.3 Upscaler 施工落地檢核 (Execution Checklist)
- [x] **Step 1: 動態模型掃描函式 (`config.py`)**
  - 實作 `get_upscale_models()`，精確掃描 `F:\Comfy_models\upscale_models` 目錄下的 `.safetensors`, `.pth`, `.pt` 模型。
- [x] **Step 2: ComfyUI 超解析工作流生成器 (`views/upscaler/workflow_builder.py`)**
  - 嚴格參照 `utility-gan_upscaler.json`，建構 6 節點 API 拓撲 (`LoadVideo` -> `GetVideoComponents` -> `UpscaleModelLoader` -> `ImageUpscaleWithModel` -> `CreateVideo` -> `SaveVideo`)，無損合流原始音軌與影格率 (FPS)。
- [x] **Step 3: 前端視圖與事件綁定實作 (`views/upscaler/view.py`)**
  - 下拉選單動態載入模型，提供一鍵刷新按鈕。
  - 視訊上傳、放大生成按鈕、中斷按鈕、播放器卡片與進度顯示。
  - 專屬 `HistoryGalleryComponent(task_type="UPSCALER")` 歷史紀錄隔離瀏覽與刪除。
  - 背景定時輪詢 (`task_poll_timer`) 自動更新進度與載入完成影片。
- [x] **Step 4: 單元測試套件建立 (`tests/test_upscaler.py`)**
  - 覆蓋節點拓撲正確性、模型目錄掃描、UI 渲染與任務建立。

### 2.4 端到端測試 (End-to-End Test Suite) 模組化與落地檢核
- [x] **Step 1: 建立專屬 E2E 測試目錄 (`e2e_tests/`)**
  - 搬移並重新命名既有測試：`test_e2e.py` -> `e2e_tests/minimax_test_e2e.py`。
  - 在專案根目錄保留輕量級轉發腳本 `test_e2e.py` 確保向下相容性。
- [x] **Step 2: 實作超解析全生命週期端到端測試 (`e2e_tests/upscaler_test_e2e.py`)**
  - 完整模擬真實使用者生命週期 8 大步驟：
    1. 啟動 Mock ComfyUI 後端與連線驗證。
    2. 啟動前端 WebUI 伺服器並執行 HTTP 200 健康檢查。
    3. 模擬使用者開啟網頁並動態發現 `upscale_models` 模型。
    4. 發起影片超解析請求 (`/handle_upscale_generate`)，校驗 6 核心節點工作流圖。
    5. 即時監聽串流進度更新（前處理 -> 執行中 -> 後處理 -> 100% 完成）。
    6. 模擬使用者下載生成之 MP4 影片並校驗二進位標頭 (`ftyp` / `isom`) 完整性。
    7. 驗證超解析歷史畫廊檢索與嚴格多裝置隔離（含刪除任務操作）。
    8. WebUI 與後端伺服器優雅關閉與資源釋放。
- [x] **Step 3: 自動化測試腳本升級 (`run_tests.bat`)**
  - 三階段依序執行：`pytest` (94 項) -> `minimax_test_e2e.py` -> `upscaler_test_e2e.py`，守護全系統綠燈。
- [x] **Step 4: 伺服器狀態復原**
  - 將 `config.py` 改回 `SERVER_STATUS = SERVER_STATUS_OK`，並同步寫入 `.server_status`。

### 2.5 錯誤根因檢討與 Schema 嚴格防護檢核 (CreateVideo bit_depth Bug Fix)
- [x] **根因分析**：
  - 參考的 `utility-gan_upscaler.json` 為 ComfyUI Web GUI 導出之前端圖檔，其 Widget 預設值為字串 `"bit_depth": "auto"`。
  - ComfyUI 後端 Python 節點 `class CreateVideo`（`comfy_extras/nodes_video.py`）定義為 `io.Int.Input("bit_depth", min=8, max=10, default=8)`，驗證時執行 `int(val)` 強制轉換，導致 Python 拋出 `ValueError: invalid literal for int() with base 10: 'auto'`。
- [x] **測試盲區檢討 (為甚麼 E2E 測試未測出)**：
  - 原 E2E 測試中的 Mock ComfyUI 伺服器僅檢查 6 個核心節點 ID 是否存在（結構完整性），未模擬 ComfyUI 內部 `execution.validate_prompt` 之型別轉型強制驗證。
- [x] **加固修正落地**：
  - [views/upscaler/workflow_builder.py](file:///F:/program_file/AI_webUI/views/upscaler/workflow_builder.py)：修正 `CreateVideo` 節點輸入為合法整數 `"bit_depth": 8`，並移除不存在之 `color_space` 與 `codec`。
  - [e2e_tests/upscaler_test_e2e.py](file:///F:/program_file/AI_webUI/e2e_tests/upscaler_test_e2e.py)：Mock ComfyUI 伺服器新增節點輸入型別嚴格驗證（模擬 ComfyUI 轉型檢查），防止非法型別通過。
  - [tests/test_upscaler.py](file:///F:/program_file/AI_webUI/tests/test_upscaler.py)：單元測試新增 `isinstance(bit_depth, int)` 與範圍斷言。

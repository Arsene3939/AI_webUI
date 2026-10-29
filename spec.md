# 接下來要執行的任務與詳細規劃：

## 1. 當有已經在執行的生成任務時，又再次按下生成影片按鈕，直接中斷先前的生成任務並送出當前生成任務，而不是排隊。
### 詳細規劃：
- **ComfyUI API 層 (`comfy_client.py`)**：
  - 新增 `interrupt_execution(prompt_id=None, server_url=None)` 函式。
  - 呼叫 ComfyUI `POST /interrupt` 中斷當前執行。
  - 若指定 `prompt_id`，同時呼叫 ComfyUI `POST /queue` (`{"delete": [prompt_id]}`) 及 `POST /api/jobs/{prompt_id}/cancel`，若在佇列中排隊則直接剔除。
- **任務管理器層 (`task_manager.py`)**：
  - 在 `Task` 物件新增 `cancel_event = threading.Event()`，狀態支援 `"interrupted"`。
  - 在 `TaskManager` 新增 `interrupt_device_tasks(device_id)` 與 `interrupt_task(task_id)`。
  - 若同一裝置（或當前連線）有處於 `queued` 或 `running` 狀態的任務，立即觸發 `cancel_event`，更新狀態為 `interrupted`，訊息改為 `⚠️ 任務已被新任務中斷`。
  - 背景工作執行緒 `_monitor_worker` 於每次輪詢檢查 `task.cancel_event.is_set()`，若被中斷則立刻釋放資源、中斷 ComfyUI 並提早返回。
- **Gradio 前端層 (`app.py`)**：
  - 在 `handle_i2v_generate`、`handle_t2v_generate`、`handle_r2v_generate` 開頭，發起新任務前先調用 `task_manager.interrupt_device_tasks(device_id)` 與 `comfy_client.interrupt_execution()`，確保 GPU 立即釋放並啟動新任務。

## 2. 如果中途有斷開連線(透過ID重新找回)，在影片生成完成之後似乎不會自動刷新狀態，需要手動重新整理，這要改成能夠自動刷新。
### 詳細規劃：
- **現狀問題分析**：
  - 過去使用者點擊生成時是透過 Gradio generator 生成器函式即時接收串流。
  - 若手機休眠、斷線、刷新頁面或由其他分頁透過 ID 找回時，產生器連線已斷開，`restore_device_state` 僅讀取當前瞬間快照，隨後前端便陷入靜態，無法感知背景任務何時完成。
- **改進方案 (`app.py`)**：
  - 利用 Gradio 的定時器（例如每 1~2 秒運行的 status timer，或結合現有 `auto_timer`）監聽當前裝置的進行中任務。
  - 新增前端自動輪詢回調函式 `poll_active_task_progress(device_id, session_task_id)`：
    - 取得當前裝置的進行中或最新任務。
    - 若任務在背景中狀態有變更（如從 `running` 變更為 `completed` 或 `failed`）：
      - 自動更新對應分頁的狀態 HTML (`i2v_status` / `t2v_status` / `r2v_status`)。
      - 若任務完成且有 `video_path`，自動載入影片至 `output_video`。
      - 更新歷史紀錄下拉選單。
    - 若當前無任務或任務已為終態且前端已展示，則維持無多餘操作（透過 `gr.skip()` 或原樣返回），節省網路頻寬與資源。

## 3. 移除自訂寬度、自訂高度的欄位，寬高都唯一以畫質(MP)計算，以免誤算。
### 詳細規劃：
- **UI 調整 (`app.py`)**：
  - 移除 I2V、T2V、R2V 三個分頁中「⚙️ 進階參數」裡的 `custom_w` 與 `custom_h` 滑桿。
  - 保留「長寬比 (Aspect Ratio)」與「畫質等級 (Quality Level 1~10)」下拉選單，並在界面上保留解析度計算提示（如 `1344 x 768 (~1.03 MP)`）。
  - 將解析度計算邏輯封裝在後端，調用 `calculate_dimensions(aspect_ratio, quality_level)` 自動推導符合 MiniMax 規範（Snap to 32）的寬與高。
- **事件與函式簽章清理**：
  - 清理 `handle_i2v_generate`、`handle_t2v_generate`、`handle_r2v_generate` 的參數列表，不再傳入 `custom_w` / `custom_h`。
  - 清理 `restore_device_state` 與 `all_restored_outputs`，移除寬高元件的輸出綁定。
  - 調整 `on_resolution_change` 與 `on_first_frame_change` 的輸出，僅更新長寬比與解析度 Markdown 提示文字。

## 4. 移除進階參數中的所有模型欄位、使用者無法自己選擇模型，這是伺服器端部署決定的
### 詳細規劃：
- **UI 調整 (`app.py`)**：
  - 移除 I2V、T2V、R2V 三個分頁「⚙️ 進階參數」中的 4 個模型設定文字框：
    - `Diffusion Model (UNET)`
    - `Text Encoder (CLIP)`
    - `Video VAE`
    - `Audio VAE`
- **後端與工作流邏輯**：
  - 移除生成函式中多餘的模型參數傳遞。
  - 生成時直接使用 `config.py` 中的伺服器端固定配置：`DEFAULT_UNET`、`DEFAULT_CLIP`、`DEFAULT_VIDEO_VAE`、`DEFAULT_AUDIO_VAE`。
  - 清理 `restore_device_state` 與 `all_restored_outputs` 中對應的綁定。

## 5. 將readme寫得更加完善，使其他開發者可以快速明白專案架構與測試流程
### 詳細規劃：
- **更新 `README.md`**：
  - **架構全景圖**：說明前端 (Gradio)、任務管理 (TaskManager / threading)、後端通訊 (ComfyClient)、工作流構建 (WorkflowBuilder) 的架構與職責。
  - **核心機制解析**：
    - 任務搶占中斷機制（避免隊列堆積）。
    - 斷線自動重連與狀態同步機制。
    - 寬高解析度對齊機制（長寬比 + 畫質等級 -> 32 的倍數）。
    - 幀數對齊 MiniMax-H3 `17k + 5` 規則。
  - **詳細使用手冊**：涵蓋 I2V / T2V / R2V 的各項參數意涵與提示詞規範。
  - **開發與測試指南**：說明各檔案用途、如何執行單元測試 (`run_tests.bat` / pytest)、如何執行 E2E 測試。

## 6. 合法輸出影片解析度定義與輸入圖片長寬比自動完美對齊機制 (Adaptive Aspect Ratio Alignment)
### 6.1 合法輸出影片解析度的判定標準
1. **空間倍數對齊約束 (Spatial Multiple Constraint)**：
   - MiniMax-H3 的 Spatial VAE compression ratio 為 16x (`latent_h = height // 16`, `latent_w = width // 16`)。
   - 其 DiT 結構採用 2x2 patch，且在官方節點源碼 (`nodes_minimax_h3.py`) 中明確定義 `CANVAS_MULTIPLE = 32`，節點 input schema 指定 `step=32, min=32`。
   - 影片編碼器（如 H.264/H.265/libx264 之 YUV420p 色度次採樣與 16x16 宏塊）強烈要求寬高能被 16 或 32 整除。
   - **結論**：$W \ge 32, H \ge 32$，且 $W \pmod{32} = 0, H \pmod{32} = 0$。
2. **總像素面積與模型有效能力區間 (Total Pixel Area / Megapixels)**：
   - MiniMax-H3 官方基準解析度為 $1344 \times 768 \approx 1.03$ MP (`MAX_PIXELS = 768 * 1344 = 1,032,192`)。
   - 畫質檔次分布於 0.2 MP (極速預覽 592x336 等) 至 1.5~2.0 MP (超高畫質)，且短邊建議 $\ge 256$、長邊 $\le 2048$。
   - 總像素面積必須緊密貼合所選的畫質檔次：$\text{Target Area} = \text{MP} \times 1,000,000$。
3. **首幀無畸變幾何一致性 (Zero Geometric Distortion)**：
   - ComfyUI `MiniMaxH3ImageToVideo` 節點內部處理首幀的方式為：`_resize(first_frame[:1], width, height, "disabled")`，也就是 **直接強制拉伸 (plain stretch without cropping or padding)**。
   - 若生成的畫布長寬比 $\frac{W}{H}$ 與輸入原圖長寬比 $\frac{W_{orig}}{H_{orig}}$ 不一致，原圖將直接在模型潛空間中被拉伸或壓扁（導致人臉、物體失真）。
   - **結論**：合法且優質的輸出解析度其長寬比必須以最小誤差（$< 0.3\%$ 甚至 $0.0\%$）嚴格對齊輸入圖片的真實長寬比。

### 6.2 新的自適應長寬比計算方法規劃 (`config.py`)
- **鄰域網格搜尋演算法 (Adaptive AR Grid-Search)**：
  1. 讀取輸入圖片原始寬高 $(W_{orig}, H_{orig})$，求真實長寬比 $r = \frac{W_{orig}}{H_{orig}}$。
  2. 由所選品質等級取得目標面積 $\text{Target Area} = \text{MP} \times 1,000,000$。
  3. 初算浮點尺寸：$H_{raw} = \sqrt{\frac{\text{Target Area}}{r}}, \quad W_{raw} = H_{raw} \times r$。
  4. 取基準倍數 $m_w = \text{round}(W_{raw} / 32), m_h = \text{round}(H_{raw} / 32)$。
  5. 在 $\Delta_w, \Delta_h \in [-3, 3]$ 範圍內搜尋滿足 $|\text{Area} - \text{Target Area}| / \text{Target Area} \le 15\%$ 的候選整數維度，最小化綜合評分：
     $$\text{Score} = 100 \times \frac{|\frac{W}{H} - r|}{r} + \frac{|\text{Area} - \text{Target Area}|}{\text{Target Area}}$$
  6. 輸出之 $(W, H)$ 既嚴格為 32 的倍數，又將長寬比誤差控制在極小範圍（例如 1500x1000 輸出 1248x832，誤差 0.00%）。
- **新增輔助函式**：
  - `calculate_dimensions_from_image(img_input, quality_level, multiple=DEFAULT_MULTIPLE) -> Tuple[int, int]`
  - `calculate_dimensions_adaptive_ratio(orig_w, orig_h, target_mp, multiple=DEFAULT_MULTIPLE) -> Tuple[int, int]`
  - 擴充 `calculate_dimensions` 支援直接處理 `"原圖比例 (自動對齊)"` 及自訂輸入比例。

### 6.3 對應 UI 改動內容規劃 (`app.py`)
1. **長寬比選項定義分流**：
   - **I2V (圖生影片)** 與 **R2V (參照生影片)**：
     - 下拉選單加入 `"原圖比例 (自動對齊)"` 作為第一選項，並**設為預設值**。
     - 選單結構：`["原圖比例 (自動對齊)", "16:9 (橫向風景)", "9:16 (直向手機)", "1:1 (正方形)", "4:3 (標準比例)", "3:4 (直向比例)", "21:9 (超寬電影)"]`。
   - **T2V (純文生影片)**：
     - 因無任何輸入圖片，維持固定標準比例選單，預設為 `"16:9 (橫向風景)"`。
2. **即時互動解析度預覽徽章 (`on_first_frame_change` / `on_resolution_change`)**：
   - 當使用者上傳首幀（或更換圖片）時：
     - 若為「原圖比例 (自動對齊)」，即時讀取圖片尺寸，計算出最優解析度並展示：
       `📐 **輸出解析度**：1248 x 832 (~1.04 MP)`
       `💡 *偵測到原圖尺寸：1500 x 1000 (比例 1.50)，已自動對齊無畸變輸出尺寸，拉伸誤差：0.00%*`。
     - 若使用者手動切換至其他標準長寬比，即時切換為該比例尺寸。
   - 當使用者變更品質等級時，若目前為「原圖比例 (自動對齊)」且有已上傳的圖片，動態重算最新畫質下的自適應尺寸。
3. **生成事件防呆處理 (`handle_i2v_generate` / `handle_r2v_generate`)**：
   - 生成觸發時，若 `aspect_ratio` 為 `"原圖比例 (自動對齊)"`：
     - 若有上傳圖片，調用 `calculate_dimensions_from_image` 算出精確尺寸。
     - 若未上傳圖片（如直接提交），安全降級為 16:9 預設值，保證系統不崩潰。
4. **工作階段恢復相容性 (`restore_device_state`)**：
   - 確保已儲存「原圖比例 (自動對齊)」或舊版比例的會話皆能順暢恢復與正常展示。

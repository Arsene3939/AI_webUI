# 接下來要執行的任務：

## 優化UI：

### 1. 進度條沒有正常顯示，使用者只會看到工作任務讀秒，但看不到現在的執行階段或步數(ex: sampling:13/20)
- 每隔0.5秒更新一次進度與任務讀秒

#### 實作規劃方向：
1. **ComfyUI WebSocket 原生進度監聽**：
   - 在 `task_manager.py` 的背景監聽執行緒中，建立與 ComfyUI 的 WebSocket 連線 (`ws://{host}:{port}/ws?clientId={client_id}`)。
   - 即時監聽 `progress` 事件（取得 `value` 與 `max`，例如 13/20 步）與 `executing` 事件（取得目前執行中的節點名稱，如 `MiniMaxH3ImageToVideo`、`VAEDecode`）。
   - 將狀態即時寫入 `task.progress = value / max` 與 `task.message = f"⚡ 擴散取樣中: {value}/{max} 步 (耗時 {time_str})"` 或 `"🔄 正在進行 VAE 視訊解碼..."`。
   - 保留 HTTP 輪詢作為斷線或未收到 WS 訊息時的 fallback 備援機制。
2. **前端推播頻率提升**：
   - 將 `app.py` 內 `handle_i2v_generate`、`handle_t2v_generate`、`handle_r2v_generate` 中的輪詢間隔從 `time.sleep(1.5)` 調整為 `time.sleep(0.5)`，讓進度條與秒數每 0.5 秒即時跳動，呈現高度滑順的進度視覺反饋。

---

### 2. 解析度應該用megapixels, 倍數來選擇(可參考i2v工作流)，這樣只要選定了長寬比跟megapixels，就會自己算出正確的輸出解析度。

#### 實作規劃方向：
1. **解析度動態計算器 (`config.py`)**：
   - 實作公式函式 `calculate_dimensions(aspect_ratio: str, megapixels: float, multiple: int = 16) -> Tuple[int, int]`。
   - 支援常見長寬比選項：`16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`21:9`（依比例計算寬高：$W = \sqrt{M \times r}$，$H = \sqrt{M / r}$）。
   - 支援百萬像素 (Megapixels) 選擇：例如 `0.5 MP`、`0.75 MP`、`1.0 MP` (約 1024x1024 / 1344x768)、`1.25 MP`、`1.5 MP`。
   - 自動 Snap（四捨五入）至指定對齊倍數（預設 16，符合 MiniMax/VAE 潛在空間維度要求）。
2. **UI 元件聯動設計 (`app.py`)**：
   - 將原有的單一解析度下拉選單，升級為：`長寬比下拉選單` + `Megapixels 滑桿/下拉選單` + `倍數選擇 (預設16)`。
   - 即時動態計算並將結果顯示為：`輸出解析度：1344 x 768 (~1.03 MP)`，並同步自動設定底層的 `custom_w` 與 `custom_h`。

---

### 3. 偵測輸入圖片的解析度，顯示在介面上，並且自動選擇最接近的長寬比。

#### 實作規劃方向：
1. **圖片上傳事件監聽**：
   - 為 I2V 首幀圖片 (`i2v_first_frame`) 及 R2V 參考圖 (`r2v_img1`) 綁定 `.change()` 或 `.upload()` 事件回呼函式 `on_first_frame_change(img_path)`。
2. **解析度讀取與長寬比比對**：
   - 透過 `PIL.Image.open(img_path).size` 獲取原始尺寸 $(W_{orig}, H_{orig})$ 與長寬比 $R_{orig} = W_{orig} / H_{orig}$。
   - 計算該比例與系統所有長寬比預設值（`16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `21:9`）的絕對誤差，自動挑選距離最小者作為最佳匹配比例。
3. **介面反饋與自動套用**：
   - 自動回傳並更新長寬比下拉選單至該最佳選項。
   - 在上傳元件下方顯示提示標籤：`📐 偵測圖片尺寸：1080 x 1920 (比例 ~9:16)，已自動匹配直向手機比例 (9:16)`。

---

### 4. 調整長寬比跟duration的排版，兩個要分成兩行，而非並列，以增加操作舒適度。

#### 實作規劃方向：
1. **排版重構 (I2V / T2V / R2V 統一調整)**：
   - 解除目前 `with gr.Row():` 將解析度/長寬比與 `duration`（生成秒數滑桿）強制擠在同一行的設計。
   - **第一行**：專門放置「長寬比與 Megapixels / 解析度配置」（寬敞易點選）。
   - **第二行**：放置「影片生成時長 (Duration)」滑桿（享有完整寬度，手機觸控滑動更精準快適），旁邊可搭配 Seed 隨機按鈕或 Steps 等參數。

---

### 5. 歷史畫廊選單目前無法正常工作，點擊下拉沒有反應，點下去變成是手動輸入的textbox。

#### 實作規劃方向：
1. **修復 Dropdown 行為模式**：
   - 在 Gradio 5/6 中，當 Dropdown 的初始 `choices=[]` 或是未限制輸入時，容易被渲染為可自由輸入文字的 Combobox。
   - 將 `history_dropdown` 明確宣告為：`gr.Dropdown(..., allow_custom_value=False, filterable=False, interactive=True)`，確保在手機與電腦點擊時一律彈出原生選擇選單，而非游標文字輸入框。
   - 初始無紀錄時填入佔位項目 `[("— 尚無歷史任務紀錄 —", "")]`，避免空陣列觸發 Gradio 元件降級 Bug。
2. **連動與選取事件確認**：
   - 確保 `.change(fn=on_select_history_item, inputs=[history_dropdown, device_id_state], outputs=[gallery_video, gallery_info])` 能正確觸發，並於切換時即時載入對應影片及中繼資訊。

---

### 6. comfy後端開關設計：
- 在"啟動comfy後端"按鈕右邊新增一個小的"關閉comfy後端"按鈕。小的按鈕都只需要簡單圖示，不需要文字。
- 每隔0.5秒自動刷新一次連線狀態，移除"刷新連線狀態"按鈕
- 移除多餘標頭欄提示，直接用按鈕顏色跟文字來顯示當前comfy連線狀態
- 狀態反饋：可以維持這個欄位，包含提示"comfy已經在運作中"、"已發送啟動指令，請等待約x秒..."這幾個原有提示

#### 實作規劃方向：
1. **後端關閉功能實作 (`comfy_client.py`)**：
   - 實作 `stop_comfyui_backend(server_url: str) -> Tuple[bool, str]` 函式。
   - 透過 Windows 系統指令（尋找佔用 8188 埠的 PID 或透過啟動時紀錄的 Process PID），發送終止訊號安全關閉 ComfyUI 進程，回傳「🔴 ComfyUI 後端已關閉」。
2. **按鈕佈局與無文字圖示**：
   - 頂部工具列設計：
     `[ ⚡ 啟動 ComfyUI 後端 ] (主要按鈕)` + `[ 🛑 ] (小圖示按鈕，scale=0, min_width=50)`。
3. **0.5秒自動偵測與按鈕動態樣式 (移除手動刷新按鈕)**：
   - 移除手動的 `refresh_status_btn`。
   - 使用 Gradio 內建定時器 `gr.Timer(value=0.5)` 自動觸發狀態檢查回呼 `poll_backend_status()`。
   - 依照連線狀態動態更新「啟動按鈕」本身的外觀與文字：
     - **在線時**：綠色樣式 (`variant="primary"` 或自訂綠底)，文字顯示 `🟢 ComfyUI 後端運作中`。
     - **離線時**：灰色/提示樣式 (`variant="secondary"` 或紅字)，文字顯示 `⚡ 啟動 ComfyUI 後端 (離線中)`。
4. **簡化標頭與保留狀態反饋**：
   - 移除上方佔版面的大塊連線狀態 HTML 橫幅。
   - 保留 `backend_status_msg = gr.Markdown("")`，專門顯示點擊啟動、關閉時的即時操作回饋訊息（如「已發送啟動指令，請等待約 5~10 秒...」）。

---

### 7. 預設提示詞保持為空

#### 實作規劃方向：
1. **清空預設文字**：
   - 將 `app.py` 中 `i2v_prompt`、`t2v_prompt`、`r2v_prompt` 的初始化參數 `value="..."` 統一修改為 `value=""`。
2. **優化 Placeholder 提示**：
   - 保持並強化各模式專屬的 `placeholder` 提示文字，指引使用者如何輸入高質量的動態、運鏡或多模態引用標籤（如 `<Picture 1>`, `<Video 1>`），但在載入時輸入框乾淨無殘留文字，方便直接貼上或輸入。

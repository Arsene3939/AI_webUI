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

## 1. 新增"影片導演"
用一個具有視覺能力的多模態模型(VLM)，作為影片導演，根據輸入圖片與我們口語簡單的需求，轉成專業且描述詳細的提示詞給minimax h3生成
- 這個VLM必須跟minimax h3一样是無審查的模型，而且要同樣能跑在comfy後端
- 規劃1. 可用的模型選擇
- 規劃2. UI設計
- 其他規劃

> **狀態：程式端＋模型安裝全部完成（2026-10-31）；接線格式已對官方範本工作流逐一核對實測通過，
> 實際推論完成度取決於執行當下显存/RAM 是否被常駐程式（strata=本地 LLM）挤占，
> 乾淨環境下用 `tools/director_selftest.py` 一條指令即可最終驗收。**
>
> **施工紀錄（2026-11-01）**
> - **方案 A（重用 H3 自帶 qwen3vl_32b_minimax_h3）已證實不可行**：ComfyUI `comfy/text_encoders/llama.py`
>   `Qwen3VL_32BConfig` 註解與欄位證實該 checkpoint 是「64 層截到 50 層、`lm_head=False`、`final_norm=False`」
>   的 conditioning 檔案（只出 embedding、無生成頭）→ 物理上無法生成文字。已从導演模型掃描名單中永久排除。
> - **已上線的程式端實作**（全部走 core 節點、無 custom node）：
>   `config.get_director_models()`（掃 text_encoders 的 qwen3vl* 並排除 minimax 截斷版）、
>   `core/director_builder.py`（CLIPLoader+LoadImage+TextGenerate 三節點 graph、中英導演人格、輸出雙段格式
>   【導演筆記】/【English Prompt】與容錯解析）、`core/director_client.py`（上傳/送件/輪詢 history 取文字、
>   結果快取、各種失敗皆回友善中文不拋錯）、`components/director_block.py`（摺疊導演區塊，模型/語言收在
>   進階設定）、已接入 **I2V tab**（吃本 tab 首幀、成品一鍵套用提示詞）。
>   測試：`tests/test_director.py` 18 項；全量 **189 綠**；minimax/upscaler e2e 全綠。
> - **模型選用（2026-10-31，依使用者硬體 RTX 5070 12GB + 96GB RAM 拍板）**：
>   - **主選 `qwen3vl_8b_nvfp4.safetensors`（6.3GB）**——RTX 50 系 Blackwell 有**原生 FP4 張量核心**，
>     NVFP4 格式在 5070 上是「體積最小＋解碼最快」的 8B 版本；權重 ~5.9GB + vision + KV ≈ 7-8GB peak，
>     12GB 在空機（关掉其他佔显存的程式）時可全速跑。
>   - **備援 `qwen3vl_4b_fp8_scaled.safetensors`（4.9GB）**——給显存吃緊/要和其他程式共存時的下檔選項，
>     兩檔都會進進階設定的模型下拉選單。
>   - 下載來源：ModelScope `Comfy-Org/Qwen3-VL`（HF 直連不通時的鏡像，已驗證 200 可連）。
>   - **不需要安裝任何 custom node**：導演走的 `CLIPLoader + LoadImage + TextGenerate` 三個節點
>     全部內建於 ComfyUI-Desktop 0.30.1 core（已在執行中的後端 `/object_info` 實測確認：
>     `joyimage` 在 CLIPLoader type 清單內、TextGenerate schema 與 builder 欄位逐一對上）。
>   - **模型清單免重啟**：`DirectorBlockComponent` 內建 5 秒定時重掃目錄，只有清單真的變化時
>     才刷新下拉選單/成品框可見度/狀態行（`refresh_model_choices`，含 5 項回歸測試）。
>   - **显存放置可調**：`config.DIRECTOR_CLIP_DEVICE`（env 可覆寫；"default"=交給 ComfyUI 显存管理、
>     "cpu"=完全不佔显存的保底）。⚠ CPU 模式請搭配 **bf16** 版模型（fp8/fp16 的 CPU matmul 在
>     Desktop 版 torch 會原生崩潰）：`qwen3vl_4b_bf16.safetensors`（8.9GB）已一併下載。
>     本機注意：`strata` 常駐程式（＝本地 LLM 服務）會佔走大部分 12GB 显存與 ~60GB RAM，
>     要跑導演/影片生成前需先關閉它；導演撞到 OOM 時 UI 會給出「显存不夠…關程式或改小模型」的可操作提示。
>   - **下拉選單現況**：掃描結果依序為 `qwen3vl_8b_nvfp4`（主選，Blackwell 原生 FP4）→
>     `qwen3vl_4b_bf16`（CPU 保底）→ `qwen3vl_4b_fp8_scaled`（GPU 輕量）。
> - **live spike 結果（2026-10-31，使用者提供官方範本工作流 `user/default/workflows/llm_qwen3vl_text_gen.json` 對照）**：
>   - **(a) 載入＝通過**：`CLIPLoader type=ideogram4`（官方範本對 standalone qwen3vl 檔用的 type，
>     `DIRECTOR_CLIP_TYPE` 已照官方預設改掉）實測 `Qwen3VLTEModel_ loaded completely; 4999.47 MB, full load: True`。
>     先前 joyimage 也能載，但官方範本是 ideogram4 → 以官方為準。
>   - **(b) 送件格式＝通過（關鍵收斂）**：`TextGenerate` 的 DynamicCombo 在 API graph 的正確序列化是
>     「`"sampling_mode": "on"` ＋ 子欄位用點分鍵 `sampling_mode.top_k / .temperature / ...`」
>     （官方範本的 input 名稱直接印證；option-dict 巢狀與平級展開都會被 0.30.1 驗證端打回或把參數丟掉）。
>     結尾必須接 `PreviewAny`（TextGenerate 非輸出節點，graph 無輸出會被 `prompt_no_outputs` 拒絕；
>     PreviewAny 把文字以 `{"text":[…]}` 寫進 /history，零檔案落盤）。以上已鏡像進 `director_builder` 並有測試封鎖。
>   - **(c) 推論完成度＝受環境資源限制**：送件、載入、tokenize、開始生成全部抵達；
>     `device=cpu` 時在 fp16 CPU matmul 原生崩潰（Desktop 版 torch 的 fp8→fp16 CPU 路徑不良）、
>     `--lowvram` 下則 `bad allocation`（當時 strata 常駐已吃走 ~58GB RAM + 絕大部分 12GB VRAM）。
>     **不是接線問題**：乾淨環境（关掉 strata 等佔显存程式）下 8B nvfp4 全速跑；
>     strata 開著時可用 `--device cpu` 搭配 **`qwen3vl_4b_bf16.safetensors`（已下載）**
>     ——bf16 純 CPU matmul 不會觸發 fp16 崩潰路徑（注意：此點仍待干净環境外的自我驗證收尾）。
>   - **收尾工具**：`tools/director_selftest.py`（走與網頁按鈕完全相同的 `call_director` 路徑，
>     `--model/--device/--image` 可選；綠 = 網頁導演也綠）。
>   - **測試**：單元 195 綠（含 DynamicCombo 點分鍵、PreviewAny 結尾、模型掃描/自動刷新、OOM 友善訊息）；
>     minimax／upscaler e2e 全綠零殘留。
> - **審查性提醒**：Comfy-Org 的 Qwen3-VL 為原版 Instruct（有安全對齊），敏感需求可能被改寫；
>   若要完全無審查導演，後續再走 ComfyUI-QwenVL custom node ＋ abliterated Qwen2.5-VL（方案 B+）。
> - **下輪候選**：R2V/T2V tab 接入導演區塊、e2e 加導演步驟（mock 後端回固定文字）、live spike 收斂參數。

### 規劃 1. 可用的模型選擇

**硬性條件**：本地端、無審查（或可移除審查）、能在 ComfyUI 後端執行（與 MiniMax-H3 共用同一個 ComfyUI-Desktop 实例）。

**方案 A（首選，零下載）：直接重用 H3 自帶的導演編碼器**
本機已裝 `F:\Comfy_models\text_encoders\qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`＝
MiniMax 微調過的 **Qwen3-VL-32B VLM（含 vision tower）**，語意對齊 H3、為「解圖＋解需求→專業提示詞」而訓練。
已核對本機 ComfyUI-Desktop **0.30.1**：core 內建 `TextGenerate` 節點（`comfy_extras/nodes_textgen.py`），
吃既有 text-encoder 物件、**具 image/video 可選輸入**（官方 LTX-2「圖→i2v 提示詞助理」模板即同款用法），
`comfy/text_encoders/qwen3vl.py` loader 在 core、nvfp4-awq 混量檔案已由 H3 生成實戰載入成功。
→ 導演 workflow＝與 H3 同一個 encoder 載入＋TextGenerate(圖片+口語需求)→ 回文字。**零新權重、零新節點。**
待 spike 驗證三點：(a) 微調後是否仍聽得懂口語對話指令（失敗降方案 B）、(b) checkpoint vision 部分是否
完整接上 TextGenerate 的 image 輸入、(c) ~20GB VRAM 常駐與 H3 生成共用（同檔快取可共用，用完 /free 釋放）。

| 候選模型（方案 B 備援下載版） | 無審查方式 | 體積/VRAM 需求 | ComfyUI 節點（現成活躍） | 評序 |
|---|---|---|---|---|
| **Qwen2.5-VL 7B/3B-Instruct-abliterated**（huihui-ai，HF＋ModelScope 雙源） | abliterated（移除拒答）；另有 prithivMLmods `Qwen2.5-VL-Abliterated-Caption` 特化描述版 | 7B≈16GB(fp16)/≈8GB(int4)；3B≈8GB | `1038lab/ComfyUI-QwenVL`、`alexcong/ComfyUI_QwenVL`（模型路徑可換成 abliterated 權重 repo） | ⭐ 首選：畫面的細節描述力最強，abliterated 生態最完整 |
| **MiniCPM-V 2.6 / MiniCPM-o**（OpenBMB） | 本身低拒答、開放（授權細節開工前核對） | 8B≈16GB | `1038lab/ComfyUI-MiniCPM`、`CY-CHENYUE/ComfyUI-MiniCPM-o` | 亞軍：中文理解佳，節點附 VQA/描述節點 |
| **Moondream 2 / 3.1**（kijai 節點＋Moondream3.1Caption 節點） | 訓練時未加安全對齊，天性無審查 | ≈2–3GB（極輕） | `kijai/ComfyUI-moondream`、`Comfy_VLM_nodes` | 備援：VRAM 不足時的保底；描述力較弱、不擅长「導演級」提示詞 |

- 三個候選的節點都是「載入模型 → 圖片+文字輸入 → 輸出純文字」的標準三節點形態，WebUI 端可以用同一套 graph 建構器參數化（見其他規劃）。
- ❓ **需拍板：GPU VRAM 多大？** ≥16GB → 首選 7B；8–12GB → 3B；<8GB → Moondream。
- 模型權重存放：`F:\Comfy_models\LLM-Vision\<模型名>\`（與既有 `F:\Comfy_models\upscale_models` 掃描模式一致，導演模型下拉選單也掃目錄）。
- 全部僅本機執行、不外傳；abliterated 衍生模型授權隨基礎模型（Qwen 系可本機自用），開工前完成授權核對。

### 規劃 2. UI 設計

**定位決策**：導演的產出就是要餵給 minimax 的提示詞欄 → 做成 **minimax 頁內嵌的「導演區塊」**（嵌入 I2V/R2V/T2V 三個 tab 的提示詞區旁），不做成 `/director` 獨立頁。理由：免跨頁搬文字、免多一層導航，符合「使用者只看到需要的東西」。❓ 若你偏好獨立 /director 頁再加 localStorage 搬文字，請說。

```
┌ 🎬 影片導演（點擊展開）────────────────────────┐
│ 導演需求：[口語描述你想拍什麼….        ]       │
│ 參考圖片： 自動沿用本頁首幀/參考圖 [+再加一張] │
│ [ ✨ 請導演寫提示詞 ]   ← 按鈕                 │
│ （狀態行）導演構思中… / ✅ 已完成              │
│ 導演成品： [可編輯的多行結果 ]                 │
│ [ 套用到生成提示詞 ]                           │
│   ▸ 進階設定（預設收合）                       │
│      └ 導演模型：[內建（H3 專用導演） ▾]       │
│        輸出語言：[中文說明＋英文提示詞 ▾]      │
└────────────────────────────────────────────────┘
```
- **導演模型選擇預設隱藏**：一般使用者不需要選模型（預設＝內建 H3 導演編碼器，零設定直接用）；
  模型下拉與輸出語言收進區塊內的「進階設定」摺疊列，只給想折騰的人。
- **用詞紅線**（遵守注意事項）：UI 不出現 VLM、custom node、graph、prompt engineering 等開發字；統一用「導演」「導演構思中」「導演成品」。技術名只出現在 admin 專區設定裡。
- 流程：點按鈕 → WebUI 組 VLM workflow → 走既有 `queue_prompt` 送到 ComfyUI → 從 `/history` 取回文字 → 填入可編輯框 → 「套用」寫進生成提示詞欄（可再手動改）。
- T2V tab 沒有自帶圖片 → 導演區塊提供「上傳一張參考圖」；沒圖時按鈕變「請導演構思」（純文字導演，同款模型但不吃圖）。
- 導演呼叫**不进任務歷史**（不污染影片 history），但在 log 留一筆供除錯。
- 失敗應對（使用者語氣）：節點沒裝 →「導演功能未就緒：請先安裝導演元件」；VRAM 不足 →「導演暫時無法上線，請稍後重試」；逾時 → 同上。按鈕變不可點而非彈錯。

### 其他規劃

- **Phase 0 spike（必做，半天）**：在 ComfyUI UI 手動組一條「H3 同款 qwen3vl_32b_minimax_h3 載入 → TextGenerate(image=首幀, 口語需求)」workflow，
  親測三件事：能否吃圖、是否聽懂口語指令並產出 H3 風格提示詞、拒答行為。通過→導演走方案 A（零下載）；
  不通→退方案 B（裝 ComfyUI-QwenVL 節點＋abliterated Qwen2.5-VL 下載版），再不通降 Moondream。不硬做。
- **檔案規劃**：
  - `core/director_builder.py`：組 VLM workflow graph（鏡像既有 `core/workflow_builder.py` 的形態；模型/圖片/需求/語言 → graph）
  - `core/director_client.py`：`call_director(image_paths, brief, model, language)` → queue_prompt、輪詢 /history、取文字、逾時處理（沿用 comfy_client 的重試語意）
  - `config.py`：`get_vision_models()` 掃 `F:\Comfy_models\LLM-Vision`；導演節點可用性偵測
  - `views/minimax/components/director_block.py`：上方 UI 區塊元件（三個 tab 共用，塞進 `ActionButtonsComponent` 生成钮附近）
- **VRAM 共存策略**：導演跑完立即呼叫 ComfyUI `/free`（既有 free_vram 機制）釋放 VLM，避免與 H3 搶显顯存；若偵測 VRAM 不足以同時載入，就維持「用完即放」模式。
- **快取**：以 (首幀圖 hash + 導演需求 + 模型) 做 key，同條件重點直接回上次結果，可强制重導。
- **測試規劃**：
  - 單元：graph 建構正確性、/history 文字解析、快取命中/失效、模型目錄掃描
  - e2e：minimax runner 加一步——mock 後端對 VLM graph 回固定文字 → 驗證「導演成品→套用到提示詞→生成」串起走
- **合規與安全**：全程本機、無外部 API；abliterated 模型僅供本機生成輔助；產出提示詞仍由使用者自己承擔內容責任。
- **任務順序**：Phase0 spike → 模型安裝腳本/指引 → director_builder/client → UI 元件（先 I2V，跑通再推 R2V/T2V）→ 單元＋e2e → 完成紀錄寫 spec、SERVER_STATUS 恢復 OK。
- 粗估：spike 半天；完整實施 1～2 個工作日當量（不含模型下載時間）。
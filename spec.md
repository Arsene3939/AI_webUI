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

## 1. 裝置列表欄位新增連線裝置的IP

## 2. 加上顯示在網頁的icon以及Title

## 3. 管理員頁面的系統提示詞儲存之後重新整理會變回原樣，但檔案內容是有改到的

## 4. 畫質放大智慧助理頁面沒有device ID跟更改ID的介面 (在minimax頁面連線網址的下方有，這幾個feature應該三個view共用)

## 5. minimax-h3只支援24幀的影片生成，把影格率拉桿整個從UI移除，並且輸入參數釘死24fps。

## 6. upscaler的其他參數設定
- 研究官方workflow 或是其他公開資料，"F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\utility-gan_upscaler.json" ，看看upscaler有沒有更詳細的參數可以設定

## 7. 在系統維護時，只有管理員可以存取頁面，其他裝置使用者無論開啟甚麼頁面，只會看到開頭的伺服器維護/更新中，以下全部空白

---

# 本輪（2026-10-31 第二批）施工規畫

## 任務 1：裝置列表欄位新增連線裝置的IP
- **現況根因**：`task_manager.get_connected_devices_summary()` 只彙整任務歷史，全專案沒有任何地方記錄裝置 IP（只有測試裡出現過 `request.client.host`）。
- **作法**：
  - `task_manager` 新增記憶體層裝置→IP 登記表：`record_device_ip(device_id, ip)`（由頁面 load／切換裝置等帶 `gr.Request` 的事件寫入），`get_connected_devices_summary()` 併入 `"ip"` 欄位（沒記錄過顯示 `—`）。IP 屬連線狀態資訊，不入任務歷史檔（重開後由重新載入頁面自然重建）。
  - `core/admin_manager.build_admin_devices_html()` 表格新增「IP 位址」欄。
  - 三個頁面 load 時都會記錄（minimax 走 `restore_device_state`，upscaler/strata 走任務 4 新加的通用 load）。

## 任務 2：網頁 icon 與 Title
- **現況根因**：`mount_gradio_app` 只帶 theme/css/head，全專案沒有任何 favicon；`Blocks(title=...)` 各頁有值但標題風格不一致、根頁跳轉頁也無 icon。
- **作法**：
  - 內嵌 SVG favicon（暗底 + 場記板意象），以 `<link rel="icon" href="data:image/svg+xml,...">` 注入三個 mount 的 head（`components/styles.py` 新增 `FAVICON_HTML`）＋ `ROOT_HTML` 跳轉頁。SVG data URI 免掃瞄、免額外靜態掛載。
  - 三頁 `Blocks(title=...)` 與頁內 header 主標統一：`/minimax`「🎬 MiniMax-H3 影片生成」、`/upscaler`「🔍 畫質放大 (Video Upscaler)」、`/strata`「💬 Strata 智慧助理」；根頁「AI 影片工作平台」。
  - `components/header.py` 的頁面主標原本是硬編碼 MiniMax，改為可帶 `title` 參數，由各 scaffold 執行時傳入（預設維持 MiniMax，不影響既有測試）。

## 任務 3：管理員系統提示詞編輯器重新整理後回到舊值（bug）
- **現況根因**：`MiniMaxAdminTab.render_comfy_content` 在 **Blocks 建置期**就抓了 `value=load_director_system_prompt()`；PAGE 是模組層單例只建一次，之後改檔＋重新整理頁面，編輯器仍是建置當下的快照（檔案其實已儲存成功）。
- **作法**：在 `pages_minimax.py` 補一條 `blocks.load`，每次開頁把編輯器內容從檔案重抓（`gr.update(value=load_director_system_prompt())`）。單次 load 也同時修好「多瀏覽器分頁」不同步問題。

## 任務 4：upscaler / strata 缺 device ID 顯示與切換介面
- **現況根因**：三個頁面都掛了同一套 header＋hidden 編輯列（`WebPageScaffold`），但只有 minimax 在 `blocks.load` 時用 `restore_device_state` 把 header 重繪成「帶裝置徽章」的版本；upscaler/strata 的 header 永远是無徽章的建置期快照，`triggerEditId()` 觸發的編輯列根本出不來。
- **作法**：`WebPageScaffold.wire_generic_device_switch()` 追加通用 load：`BrowserState` 沒有裝置 ID 就生成一個（與 minimax 語意一致），記錄裝置 IP（任務 1），並重繪 header 徽章；由 `pages_upscaler` / `pages_strata` 既有的 `wire_generic_device_switch()` 呼叫自動生效，minimax 不受影響（它走自己的還原路徑，只需補 IP 記錄）。

## 任務 5：移除影格率拉桿、生成參數釘死 24fps
- MiniMax-H3 只支援 24fps。`config.py` 新增 `MINIMAX_FIXED_FPS = 24`。
- `components/video_params.py`：刪除 fps Slider 與 `default_fps`；`i2v/t2v/r2v` 三個 tab 的 handler 簽名、click inputs、`saved_params`、`get_components_for_restore` 全移除 fps；呼叫 `build_*_workflow` 時固定傳 `fps=float(MINIMAX_FIXED_FPS)`（builder 簽名不動，向後相容）。
- 還原鏈連動收斂：`MiniMaxView.restore_state` 的更新計數 14/12/19 → 13/11/18；`all_restored_outputs` 55 → 52；`tests/test_app_state.py` 的索引註解與 55 斷言同步更新；兩個 e2e 的 `submit(..., 24, ...)` 定位參數移除。
- 舊任務歷史裡已存的 `params["fps"]` 不再讀取（僅供舊紀錄展示，不生新值）。

## 任務 6：upscaler 更詳細參數（研究＋實作）
- **研究結論**（官方範本 `utility-gan_upscaler.json` ＋ ComfyUI 0.30 `comfy_extras/nodes_video.py` 原始碼）：
  - 我們的拓撲與官方範本完全相同（UpscaleModelLoader→ImageUpscaleWithModel→CreateVideo→SaveVideo）。
  - 官方範本內可調而我們尚未暴露的：`CreateVideo.bit_depth`（8/10，10-bit 漸層較不易色帶）、`SaveVideo.format`（auto|mp4）、`SaveVideo.codec`（auto|h264，h264 可再選 re-encode+CRF——這是巢狀 DynamicCombo，序列化風險高，本輪不暴露）、`SaveWEBM` 節點（experimental，本輪不採用）。
  - 官方 MarkdownNote 建議：GAN 模型倍率固定（本機三個模型全是 4x：RealESRGAN_x4plus / 4x-UltraSharp / 4x-AnimeSharp），「先放大、再用縮放節點降到目標解析度」。
- **實作**：builder 新增 `output_format="auto"`、`bit_depth=8`、`post_scale=None` 三個參數（預設值產生與現在完全相同的圖，零回歸）；`post_scale` 有值時插入核心 `ImageScaleBy`（area 縮放）節點。UI 加「🎛️ 進階輸出設定」摺疊區：輸出格式（auto/mp4）、位元深度（8/10）、輸出縮放（不縮放＝模型原生 4x / 再縮 1/2＝淨 2x / 再縮 1/4＝淨 1x 純畫質重建）。`tests/test_upscaler.py` 補新節點斷言、e2e submit 補對應定位參數。

## 任務 7：維護期間僅管理員可看到頁面內容
- **語意**：`SERVER_STATUS=UPDATING` 時，非管理員（`AdminManager.is_super_user(request)` 為 False，同一套 admin IP 白名單機制）開任何頁面，只看到 header（既有 `build_header_html` 已會渲染「🔧 伺服器維護/更新中」橫幅），其下全部隱藏。
- **作法**：`WebPageScaffold` 新增 `wire_maintenance_gate()`：
  - 註冊 `blocks.load` ＋`backend_poll_timer.tick`（0.5s）雙觸發的閘門 handler（吃 `gr.Request`）：維護中且非管理員 → 對「模組主容器、後端工具列、側欄」回 `gr.update(visible=False)`，否則回 visible=True（維護結束自動恢复）。
  - 同一 handler 順帶重繪 header（讓「維護中／維護結束」橫幅即時出現/消失，不必重新整理）。
  - `ComfyToolbarComponent.render()` 把工具列 Row 存成 `self.row` 供閘門.hide；三頁 `_build_page` 各呼叫一次 `wire_maintenance_gate([...])`。
  - 生成提交端點本就有維護擋箭牌，此層是 UI 層的可見性控管；e2e/單元測試從本機（loopback=super user）執行，不會被閘門擋掉。

## 驗收程序
1. 全程 `SERVER_STATUS=SERVER_STATUS_UPDATING`（本輪開始已立旗）。
2. 全部實作完成 → 旗標改回 `OK`。
3. `pytest tests/` 全綠 → 依序跑 `e2e_tests/minimax_test_e2e.py`、`e2e_tests/upscaler_test_e2e.py`（mock 後端、零殘留）。
4. 回填「施工完成紀錄」至本檔。

---

# 本輪（2026-10-31 第二批）施工完成紀錄

## 任務 1 ✅ 連線裝置 IP
- `task_manager/manager.py`：新增記憶體登記表 `_device_ips`（刻意不入歷史檔，避免訪客 IP 長期落地）＋ `record_device_ip()`（自動剝除 `::ffff:` 前綴）＋ `get_device_ip()`；`get_connected_devices_summary()` 合併登記表 — **只開過頁面、還沒生成任務的裝置也會出現在總覽**（task_count=0）。
- 記錄點：minimax `restore_device_state`／`switch_manual_device_id`（補了 `gr.Request` 參數）、`shell.wire_maintenance_gate`（load＋切換裝置）、upscaler/strata 的通用 load。
- `core/admin_manager.build_admin_devices_html()`：表格新增「連線 IP」欄（無記錄顯示 `—`）；管理頁每 5s 自動刷新沿用既有 super-user timer。

## 任務 2 ✅ 網站 icon 與 Title
- 採用使用者自製的 `assets/app_icon.png`（影格＋播放鍵）：`webapp/server.py` 掛 `/assets` 靜態目錄＋`/favicon.ico` 兜底路由；`components/styles.py` 的 `FAVICON_HTML`（`<link rel="icon">`）注入三個 mount 的 `head=` 與 `/` 跳轉頁。
- 分頁標題：`/minimax`「🎬 MiniMax-H3 影片生成｜AI 影片工作平台」、`/upscaler`「🔍 畫質放大 (Video Upscaler)｜…」、`/strata`「💬 Strata 智慧助理｜…」、根頁「AI 影片工作平台」。
- 順帶修復：頁內 header 大標過去三頁都硬編碼 MiniMax — `build_header_html` 開放 `title` 參數，由各頁 `header_title` 帶入（upscaler「🔍 影片畫質放大系統」、strata「💬 Strata 智慧助理系統」）。

## 任務 3 ✅ 管理員提示詞編輯器重新整理變回舊值（bug 修復）
- 根因如規畫：`PAGE` 單例在 Blocks 建置期快照了檔案內容。修在 `webapp/pages_minimax.py`：每頁 `blocks.load` 重抓 `load_director_system_prompt()` 灌回編輯器。存檔→重新整理→看到的就是檔案最新內容（回歸測試 `test_admin_prompt_editor_reflects_file_on_every_load` 直接改檔比對兩版）。

## 任務 4 ✅ 三頁共用的裝置 ID 顯示／切換介面
- `webapp/shell.py` `wire_maintenance_gate(..., own_header=True)`（upscaler/strata）：單一個 load handler 同時「補發裝置 ID → 記錄 IP → 重繪 header 徽章（帶該頁標題）」；徽章出現後 `triggerEditId()` 的「✏️ 切換裝置 ID」編輯列在两頁都可用（編輯列元件本來就在 scaffold 上，之前只是永遠觸發不到）。
- minimax 走 `own_header=False`：ID／header／IP 仍歸 `restore_device_state` 單一寫入，避免雙寫競態。

## 任務 5 ✅ 影格率 UI 全移除、生成釘死 24fps
- `config.MINIMAX_FIXED_FPS = 24`；`VideoParamsComponent` 的 fps Slider 與 `default_fps` 刪除；I2V/T2V/R2V 的 handler 參數、inputs、`saved_params`（存固定值 24 供歷史展示）、還原清單全數收斂；`build_*_workflow` 一律傳 `fps=24.0`（builder 簽名不動）。
- 計數同步：I2V 14→13、T2V 12→11、R2V 19→18；`all_restored_outputs` **55→52**；`test_app_state.py` 索引/斷言與兩個 e2e 的定位參數同步更新。

## 任務 6 ✅ upscaler 進階輸出參數
- 研究（官方 `utility-gan_upscaler.json` ＋ ComfyUI 0.30 `nodes_video.py`／`nodes.py` 原始碼）：我們的拓撲＝官方範本；本機三個模型全是 4x；`SaveVideo.format` 只有 auto|mp4（webm 走另一節點 SaveWEBM，experimental，不採用）；`SaveVideo.codec` 的 h264 re-encode+CRF 是巢狀 DynamicCombo，序列化風險高 → **本輪不暴露**；`CreateVideo.bit_depth` 8|10；官方註記建議「先放大、再用 resize 節點降回目標解析度」。
- 實作：builder 新增 `output_format`／`bit_depth`／`post_scale`（後者插入核心 `ImageScaleBy`（注意：參數名是 `scale_by` 不是 scale_factor）以 area 縮放）；UI「🎛️ 進階輸出設定」：輸出縮放（原生／1/2／1/4）、輸出格式（auto/MP4）、位元深度（8/10）。非法值退回安全預設。
- 零回歸證據：預設參數產出的圖與舊版逐位元組相同（`test_default_params_reproduce_legacy_graph`）。

## 任務 7 ✅ 維護期間僅管理員可見頁面
- `WebPageScaffold.wire_maintenance_gate()`：三頁的「模組主容器＋後端工具列＋側欄」在 `SERVER_STATUS=UPDATING` 且非 super user 時全部 `visible=False`，只留 header 的「🔧 伺服器維護/更新中」橫幅；`backend_poll_timer`（0.5s）偵測維護開始/結束即時切換（狀態未變不寫輸出）；admin 白名單沿用 `AdminManager.is_super_user`。
- 回歸測試 `test_maintenance_gate_hides_pages_from_non_admins`：LAN IP 請求 → 三處 hidden＋header 含橫幅；loopback → 全部 visible。

## 驗收結果
- `pytest tests/`：**209 passed**（198→209：本輪新增 11 個測試 — IP 4、favicon/title 2、維護閘門 1、提示詞重抓 1、upscaler 參數 3；另同步更新既有的索引/計數/參數斷言）。
- `e2e_tests/minimax_test_e2e.py`：ALL PASSED（10.58s，任務全數清理、零殘留）。
- `e2e_tests/upscaler_test_e2e.py`：ALL PASSED（11.52s，含跨模組串行排隊）。
- `SERVER_STATUS` 已恢復 `OK`。
- 待辦提醒：`tools/director_selftest.py` 的實機導演推論驗證（上一輪遺留，需在 strata 關閉的環境執行）仍待執行；本輪改動與導演功能無交集，不影響該待辦。
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

> **✅ 2026-10-31 實作完成紀錄**：本輪任務 1～4 已按下列規劃全部實作完成。
> - **任務 1**：`ComfyToolbarComponent.on_stop_backend(request)` 管理員強制關閉路徑：super user 按 🛑 時先
>   `interrupt_device_tasks(device_id=None, module=None)` 標記全部 queued/running 為 interrupted，再照常關閉後端，
>   訊息回報「已中斷 N 個進行中的工作」；一般使用者 safeguard 不變。
> - **任務 2**（僵死任務 bug）：
>   - `_monitor_worker` 後端存活看門狗：history+queue 輪詢連續 10 次全失敗 ⇒ 任務標記 interrupted
>     （⚠️ 後端模型已離線，任務已中止）並寫入歷史。
>   - 新增 `reconcile_orphaned_tasks()`（於 `launch_webui()` 呼叫）：重啟後對每個 queued/running 任務向 ComfyUI
>     一次性核對 `/history` + `/queue`，已消失的降格 interrupted。實測已把 log 中卡死的
>     `task_1793365559_cae706`（7/13 步、後端被殺）降格為 interrupted。
>   - `sync_task_with_server` 加入 prompt 失蹤回收（history/queue 雙重不存在 ⇒ interrupted）。
>   - 歷史畫廊納入近 15 筆 ⚠️/❌ 失敗與中斷紀錄，選取時顯示狀態與中止原因。
>   - `delete_task` 順手清除 `outputs/inputs/` 上傳媒體歸檔（磁碟洩漏修復）。
> - **任務 3**（電腦版太窄）：確認根因是 Gradio 6 手機優先設計（`fill_width=False` 時 `.fillable` 被限制
>   max-width 640px）+ 本專案 `.container` 1000px 上限。`app.py` 改用 `gr.Blocks(fill_width=True)`；
>   `styles.py` 新增 `@media (min-width: 1024px)` 桌面區塊（1280px 置中、加大留白），手機版樣式完全不動。
> - **任務 4**（e2e 殘留）：盤點如上述表格。兩個 e2e runner 的 `_cleanup()`（成功/失敗路徑皆覆蓋）改為
>   自動刪除本次建立的所有任務（含影片與 inputs 歸檔）、掃除 `outputs/`、`outputs/frames/` 內含 `_e2e_`
>   的檔案、rmtree 暫存目錄；新增一次性工具 `e2e_tests/clean_e2e_leftovers.py` 已清除舊殘留
>   （50 筆 e2e 歷史紀錄、145+178 個殘留檔案；使用者真實紀錄全數保留）。
> - 驗證結果：unit tests **147 項全數通過**（新增 14 項：管理員強制關閉×3、僵死任務回收/畫廊可見性/
>   inputs 歸檔清理×8、桌面排版防回歸×3）；minimax E2E 8 階段與 upscaler E2E 9 階段皆綠燈，且跑完後
>   `outputs/` 與 `task_history.json` **零殘留**（0 個 e2e 檔案、0 筆 e2e 紀錄）。
> - `SERVER_STATUS` 已於施工前切 UPDATING、完工後恢復 OK。

> **✅ 2026-10-31 (第二輪) 實作完成紀錄**：本輪任務 1～3（歷史紀錄含未完成任務、UI 滿版修復、自動刷新）
> 已按規劃全部實作完成。
> - **任務 1**：確認設計——輸入在 `create_task()` 當下即存檔（params＋上傳媒體歸檔至 `outputs/inputs/`），
>   「恢復上次輸入」讀任務紀錄而非畫廊， queued/running/failed/interrupted 皆可恢復，不會失效；
>   缺的只是可見性（上一輪已修）。新增防回歸測試：只有 interrupted 紀錄的裝置不再顯示「暫無歷史紀錄」、
>   未完成任務的歸檔輸入檔在任務存在期間保持可恢復。
> - **任務 2**：元兇查明——CUSTOM_CSS 的 `div[class*="sidebar"] { width:260px !important }` 命中 gradio 6
>   包住整個 App 的 `.sidebar-parent`，整頁（手機＋電腦）都被壓成 260px 寬；此為 `gr.Sidebar` 遷移時
>   引入的回歸，與 fill_width 改動無關。修法：移除該選擇器，側欄寬度/定位改由
>   `.sidebar:not(.right)` 一組規則統一管理（260px、`left:-260px`、展開 `translateX(260px)`），
>   手機/桌面同一套。白色主題黑字：launch 改用深色化 gradio 主題（light+dark token 全釘死深色）＋
>   深色底區塊直接指定文字色（header、狀態框、進度列訊息）。新增防回歸測試封鎖寬側欄選擇器。
>   （截圖右側圖示欄為系統浮窗，非網頁內容。）
> - **任務 3**：管理員專區新增 5 秒 `gr.Timer`：硬體儀表板、ComfyUI 佇列狀態、連線裝置總覽自動刷新
>   （`is_super_user(request)` 把關，非管理員 session 不做任何查詢）；任務清單下拉選單與 IP 名單
>   刻意維持手動（理由見評估表）。負擔：每 5 秒 psutil 微秒級＋1 次 localhost GET，對 GPU 生成零干擾。
> - 驗證結果：unit tests **152 項全數通過**（本輪新增 5 項）；minimax E2E 8 階段與 upscaler E2E 9 階段
>   皆綠燈（含新主題/計時器下完整啟動與 /config 探測），跑完 `outputs/` 與歷史紀錄**零殘留**。
> - `SERVER_STATUS` 已於施工前切 UPDATING、完工後恢復 OK。

> **✅ 2026-10-31 (熱重載修復) 實作完成紀錄**：
> - **問題**：UI 改動要重啟伺服器才生效。根因：run.bat 的 `python -m gradio app.py` 熱重載會重跑
>   app.py 並把重建的 demo 換進執行中的伺服器（swap_blocks），但**不會重綁 port、也不會走完整啟動**；
>   而 theme/css/head 是在 `Blocks.launch()` 最前面幾行才被套用進 Blocks 的，我們舊的
>   `launch_webui()` 守衛在重載執行緒直接 early-return，導致重建的 demo 完全沒有自訂樣式
>   （不只是沒更新，是整套 CUSTOM_CSS/APP_THEME/head JS 遺失）。
> - **修法**：`launch_webui()` 的 reload 執行緒分支改為仍呼叫
>   `demo.launch(theme=APP_THEME, css=CUSTOM_CSS, head=CUSTOM_HEAD_JS)`——gradio 的 launch()
>   會先套用樣式，再於綁 port 前因 `_is_running_in_reload_thread` 自動 return，不會重複啟動。
>   （注意：把 css/theme 挪進 `gr.Blocks()` 建構子**沒有用**，那些只是存成 `_deprecated_*`，
>   實際套用仍只發生在 launch()。）
> - **驗證**：實測 `python -m gradio app.py`（7899 埠）下修改 `components/styles.py` ⇒
>   log 出現 `Changes detected`，數秒後網頁原始碼即含新 CSS 標記、還原後標記消失，
>   自訂 CSS 全程存在、零 reload 錯誤。新增回歸測試 `tests/test_reload_style_guard.py`
>   （模擬 reloader 執行緒旗標，驗證樣式重新套用且不會重綁 port）。unit tests **153 項全數通過**。
> - `SERVER_STATUS` 已於施工前切 UPDATING、完工後恢復 OK。

## 0. 重複提醒：注意事項
- 應避免UI介面出現過多開發相關字詞，讓使用者只看到他需要看到的東西
- 很多東西其實使用者根本不在乎，例如：支援電腦與手機... 
- 開始施工前要改SERVER_STATUS旗標

## 1. 讓歷史紀錄也包含未完成任務
- 考量到恢復上次輸入與成果是讀取歷史紀錄來恢復，如果未完成任務不寫進歷史紀錄，恢復上次"輸入結果"這個說法就會失效。
- 本來的設計在使用者是怎麼保存使用者的輸入的？依現在的設計，在任務完成前，"恢復上次輸入結果"這個說法確實會失效嗎?
### 現況分析（設計說明）
- **輸入的保存時機**：`create_task()` 在任務建立当下就把所有輸入存進任務紀錄
  （`params`：提示詞、全部參數、上傳媒體的**歸檔路徑**），`_archive_file()` 會把上傳的首幀/參考影片等
  复制到 `outputs/inputs/<task_id>_<欄位>.<ext>` 永久保存，與暫存檔脫鉤。任務一經建立即寫入
  `task_history.json`（保留最新 100 筆）。
- **恢復路徑讀的是任務紀錄，不是歷史畫廊**：「🔄 恢復上次輸入與成果」按鈕走
  `restore_device_state → get_task(stored_task_id) / get_latest_task_for_device → restore_state(task)`，
  與任務狀態無關 ⇒ 對 queued/running/failed/interrupted 任務，**輸入恢復本來就不會失效**。
- **真正的缺口在「可見性」**：歷史畫廊下拉選單舊版只列 completed＋影片存在的紀錄，失敗/中斷的任務對使用者
  不可見（上一輪已修：畫廊納入近 15 筆 ⚠️/❌ 紀錄）；另外重啟降格（reconcile）只改狀態、不刪紀錄，
  params 仍完整 ⇒ 降格後的任務一樣可恢復輸入。
### 解法（補強＋防回歸）
- 新增防回歸測試：只有 interrupted 紀錄的裝置，畫廊不再顯示「暫無歷史紀錄」；選取該紀錄會顯示
  提示詞/參數/中止原因；其 inputs 歸檔在被手動刪除任務前必須保持存在（恢復輸入的來源）。

## 2. UI依舊沒有正常滿版顯示，而且我發現可能更久之前，手機版網頁就也沒有正常顯示了
- 這個問題或許修改某個UI擺法後手機跟網頁版的版面問題都能解決?
- 你可以參考重構之前的UI設計(commit #76b9be5)，我記得那時候的UI是正常的，但是要維持现在的軟體架構，不要改回全部擠在一個app.py的寫法
- 閱讀"E:\Screenshots\螢幕擷取畫面 2026-10-31 021528.png"，"E:\Screenshots\螢幕擷取畫面 2026-10-31 021332.png"，這是現在的UI長相
- 另外在白色主題的系統下，有些字會變成黑色(如手機版網頁截圖)，因為我們的UI都有背景打底，所以你可能要直接指定字體顏色
### 根因（已從 gradio 6.30 內建 CSS 查證）
- **一個選擇器壓垮全部版面**：`CUSTOM_CSS` 裡的 `div[class*="sidebar"] { width: 260px !important }`
  不只命中侧栏本体，也命中 gradio 6 的 **`.sidebar-parent`**（包住整個 App 的 flex 主容器）與
  `.sidebar-content`，於是**整個網頁被壓成 260px 寬**——電腦版與手機版截圖中的直幅窄欄都是它。
  這是 `gr.Sidebar`（gradio 6 原生元件）取代舊 Accordion 擺法時引入的回歸，與本輪 fill_width 改動無關，
  也解释了「手機版更久之前就已經不正常」。兩張截圖右側的圖示欄是系統浮窗（RivaTuner/手機工具箱），
  非網頁內容。
### 解法（單一擺法同時修好手機與電腦版）
- 移除 `div[class*="sidebar"]` 選擇器；寬度/定位覆蓋只作用在真正的 `.sidebar` 元素：
  `.sidebar, .sidebar.svelte-1uruprb { width:260px !important; left:-260px !important }`，
  展開統一用 `.open → transform: translateX(260px)`（一套規則通用于手機與桌面，不再依賴 gradio
  手機斷點的 100vw 原生行為）。
- `.sidebar-parent` 只保留 padding 歸零（覆蓋式側欄），寬度交回 gradio 原生 flex ⇒ 內容恢復滿版。
- 白色主題下黑字問題：對深色底區塊直接指定文字色（`body` 深色背景、`.header-card h2`、
  `.backend-status-box`/`.res-display-box` 文字、進度列訊息 HTML 全部明文化），不再依賴
  gradio 主題繼承色。
- `test_styles_css.py` 同步防回歸：禁止 `div[class*="sidebar"]` 再出現在寬度規則中。

## 3. 自動刷新資訊
- 列出一些你認為應該自動刷新，但現在卻不會自動刷新的內容(例如:管理員頁面的硬體狀態)
- 評估這些自動刷新對硬體的負擔、設定合理的刷新速度
### 盤點與評估
| 項目 | 現況 | 決定 | 硬體負擔評估 |
|---|---|---|---|
| 管理員・硬體資源儀表板 (RAM/GPU/VRAM/磁碟) | ❌ 僅手動按鈕 | ✅ 每 5 秒 | psutil 讀取，微秒級、無副作用 |
| 管理員・ComfyUI 佇列狀態 | ❌ 僅手動按鈕 | ✅ 每 5 秒 | 1 次 localhost `/queue` GET（與既有 0.5s check_server 相比可忽略） |
| 管理員・連線裝置總覽 | ❌ 僅手動按鈕 | ✅ 每 5 秒 | 純記憶體掃描（≤100 筆任務） |
| 管理員・任務清單下拉選單 | 手動 | ❌ 維持手動 | 自動刷新會把使用者正在操作的選取值洗掉，得不償失 |
| 後端啟動狀態列 | 已 0.5s | 維持 | 已有 0.5s check_server 輪詢 |
| 生成進度 / 歷史畫廊 / upscaler 進度 | 已 1s 輪詢 | 維持 | 已有 |
| 管理員 IP 名單、IP 白名單 HTML | 手動 | ❌ 維持手動 | 變動頻率低，自動刷只是浪費 |
### 實作
- `BaseAdminTab.render` 建立 `gr.Timer(value=5.0)`，tick 以 `is_super_user(request)` 把關
  （非管理員 session 回 `gr.update()` 不做事），刷新硬體儀表板＋裝置總覽；
  `ComfyUIAdminTab` 把同一個 timer 再綁到佇列狀態 HTML。每 5 秒的 psutil+1 次 GET 對 GPU/生成工作零干擾。

## 4. 評估taskmanager是否應該模組化
## 5. 評估以網頁路徑(/)分開管理頁面的可行性
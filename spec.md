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

# 接下來要執行的任務與詳細規劃：

## 更新UI排版（已完成）
### 跑版問題
- **問題診斷**：原本 `長寬比`、`畫質等級`、`輸出解析度` 三個元件被硬擠在同一個 `gr.Row()` 內，當螢幕或欄位寬度稍窄時，右側輸出解析度 Markdown 文字（如「輸出解析度：\n352 x 576 (~0.2 MP)」）會折行破版，且兩側元件垂直高低不一。
- **規劃方案**：
  1. 將「長寬比」與「畫質等級」維持在同一 Row（各自 scale=1），維持整齊對齊。
  2. 將「輸出解析度」獨立自成一完整列，設計成專屬狀態卡片，不再與下拉選單搶橫向空間。
  3. 設定響應式 CSS 樣式，確保在桌面版左右分欄與手機版單欄自適應時均能正常伸展無跑版。

### 參數位置擺放調整
- **修改內容**：
  - **移入「⚙️ 進階參數」折疊區塊**：
    - `隨機種子` (Seed) 與 `🎲 隨機` (Random Button)。
    - 與原本的 `去噪強度` (Denoise)、`取樣器` (Sampler)、`調度器` (Scheduler) 置於進階區塊。
  - **移出至基本參數區**：
    - `取樣步數` (Steps) 與 `影格率 (FPS)`：與 `影片時長 (秒)` (Duration) 一同放在外層基本參數區（成排佈局：時長、步數、FPS）。
  - **套用範圍**：一致性套用於 `圖生影片 (I2V)`、`文生影片 (T2V)`、`參考生影片 (R2V)` 三大生成頁籤。

### 狀態欄的位置調整
- **修改內容**：確保三大文字狀態欄各自獨自享有完整的兩行空間高度，文字垂直置中、版面不隨字數變動而抖動跳躍：
  1. **啟動模型相關的狀態欄 (`backend_status_msg`)**：
     - 位於後端啟動/停止按鈕列下方，使用獨立專屬樣式容器，設定固定最小兩行高度 (`min-height: 48px; line-height: 1.5; display: flex; align-items: center; padding: 6px 12px; border-radius: 8px;`)，確保訊息文字穩定維持兩行高度不壓迫鄰近元件。
  2. **輸出解析度狀態欄 (`i2v_res_info`, `t2v_res_info`, `r2v_res_info`)**：
     - 獨立自成一完整列，設計專屬 2-line 高度卡片樣式容器 (`min-height: 44px; display: flex; align-items: center; padding: 6px 12px; border-radius: 8px; background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.08);`)，確保解析度數字與 MP 標籤有充分的完整兩行空間且文字絕對不會被擠壓折損。
  3. **生成與進度回饋狀態欄 (`i2v_status`, `t2v_status`, `r2v_status`)**：
     - 在 `build_progress_html` 中調整文字狀態欄高度至標準兩行高度 (`min-height: 2.7em; -webkit-line-clamp: 2; line-height: 1.35;`)，無論是一行提示還是兩行階段訊息（包含耗時與百分比），高度恆定鎖定兩行空間，進度條不上下位移。

## 管理員模式：管理員名單 (IP 管理員名單設定)
### 需求規格
1. 命名規範：一律使用「管理員名單」（非白名單），避免開發術語。
2. 功能範圍：
   - 管理員可輸入特定 IP 加入「管理員名單」。
   - 可檢視已登記在「管理員名單」中的 IP，並可將特定 IP 移除。
   - 只要連線的用戶 IP 存在於「管理員名單」或原本的本地端/本機 IP，即可在開啟 WebUI 時存取並看到「管理員操作」頁籤，且具備完整的管理員權限。
3. 資料持久化：
   - 儲存於 `outputs/admin_ips.json`，伺服器重啟或 auto-reload 後不遺失。
   - 本地本機 IP（127.0.0.1, ::1, localhost, 本機實體 IP）為預設永遠具備權限，不可被誤刪。
4. UI 設計：
   - 在「管理員操作」頁籤新增「🛡️ 管理員名單設定」區塊。
   - 包含：目前管理員名單顯示（HTML 卡片/表格或標籤）、新增 IP 輸入框與「新增管理員 IP」按鈕、移除特定 IP 按鈕/下拉清單、操作即時提示訊息。

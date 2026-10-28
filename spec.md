# 接下來要執行的任務：

## 1. 連接埠佔用友善診斷與管理員排查指引（Port Conflict Diagnosis & Admin Guidance）
- **維持固定 7860 連接埠**：
  - 考量使用者與行動端預設僅記憶與書籤 `http://localhost:7860`（或手機內網 IP:7860），伺服器啟動時不再自動隨機跳號轉移至 7861、7862 等陌生連接埠。
- **佔用預檢與詳細排查指引**：
  - 伺服器啟動前進行預檢（Pre-flight check）。若 7860（或指定之 `WEBUI_PORT`）已被佔用，立即顯示格式清晰且醒目的錯誤警示框，避免出現不友善的 Python 錯誤堆疊（Traceback）。
  - 自動呼叫系統指令（`netstat -ano` 與 `tasklist`）解析佔用該通訊埠之進程 PID 及執行檔名稱（例如 `python.exe`）。
  - 提供明確的排查與解決步驟，包括一鍵結束衝突進程的指令範例（如 `taskkill /PID <PID> /F`），引導伺服器管理員快速排除佔用後重新啟動。

## 2. 新增log系統，在運行前端伺服器的terminal輸出一些你認為應該log出來的訊息，方便debug。
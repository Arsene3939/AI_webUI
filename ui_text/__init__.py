"""
WebUI 文案集中包（Spec 2026-11-03 任務 5）。

使用者在 WebUI 上看得到的所有文字（按鈕、標籤、占位文字、狀態訊息、警示、
Markdown 說明）一律住在這裡；要改文案只動這個資料夾。
分組檔案：common / backend / minimax / upscaler / strata / admin / chrome，
各檔常數以檔名前綴區隔（COMMON_ / BACKEND_ / MINIMAX_ / DIRECTOR_ /
UPSCALER_ / TASK_ / STRATA_ / ADMIN_ / CHROME_），全站統一
`from ui_text import XXX` 取用。

邊界：技術值（模型檔名、解析度與取樣器技術名稱、目錄路徑、CSS/JS、
api_name、logger 記錄文字）不搬，仍留在 config／各模組。
含數字／變數的訊息以 {} 模板常數存放，呼叫端 .format(...) 組回。
"""
from .common import *
from .backend import *
from .minimax import *
from .upscaler import *
from .strata import *
from .admin import *
from .chrome import *

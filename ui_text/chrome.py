"""chrome 區塊的 UI 文案（三個模組頁共用的頁面骨架：header 橫幅、側邊導覽、
瀏覽器分頁標題、維護橫幅）。HTML 標記留在常數內，含 IP／裝置碼／標題等
變動部分以 {}／{0} 槽存放，呼叫端 .format(...) 組回。

技術值不搬：localStorage 鍵、TAB_SEGMENTS 網址段、CSS/JS、模組鍵
（MODULE_MINIMAX 等英文識別鍵，畫面從不顯示）。
"""
from .common import COMMON_MAINT_BTN  # 「🔧 伺服器維護/更新中」逐字相同，共用不重複

# ── 頁內 header 主標（components/header.py；預值＝minimax 頁）───────────
CHROME_HEADER_TITLE_MINIMAX = "🎬 MiniMax-H3 影片生成系統"
CHROME_HEADER_TITLE_UPSCALER = "🔍 影片畫質放大系統"
CHROME_HEADER_TITLE_STRATA = "💬 Strata LLM"

# ── 瀏覽器分頁標題（gr.Blocks(title=…)；webapp/pages_*.py 與 shell 預值）─
CHROME_SCAFFOLD_TITLE_DEFAULT = "MiniMax-H3 AI Video WebUI"
CHROME_PAGE_TITLE_MINIMAX = "🎬 MiniMax-H3 影片生成｜AI 影片工作平台"
CHROME_PAGE_TITLE_UPSCALER = "🔍 畫質放大 (Video Upscaler)｜AI 影片工作平台"
CHROME_PAGE_TITLE_STRATA = "💬 Strata LLM｜AI 影片工作平台"

# ── header 橫幅（build_header_html）：外框、維護橫幅、裝置 ID 徽章 ──────
# 外框 {} 依序：主標、內網 IP、埠號、裝置徽章字串、維護橫幅
CHROME_HEADER_PAGE_HTML = """
    <div class="header-card">
        <h2 style="margin: 0 0 8px 0; font-size: 1.5rem;">{0}</h2>
        <div style="font-size: 0.95rem; opacity: 0.9; line-height: 1.6;">
            🌐 <b>連線網址：</b> <span class="ip-badge">http://{1}:{2}</span>
            {3}
        </div>
        {4}
    </div>
    """
CHROME_HEADER_MAINT_BANNER_HTML = (
    '<div style="margin-top: 8px; padding: 6px 14px; background: #fff1f2; '
    'border: 1.5px solid #fda4af; border-radius: 6px; color: #e11d48; '
    'font-weight: 700; font-size: 0.95rem; text-align: center;">'
    + COMMON_MAINT_BTN +
    '</div>'
)
# 裝置 ID 徽章：{0}＝裝置代碼短碼（onclick JS 與標題皆圍繞短碼）
CHROME_HEADER_DEVICE_BADGE_HTML = (
    ' | <span style="display: inline-flex; align-items: center; gap: 4px; vertical-align: middle;">'
    '<button type="button" class="id-badge-btn" onclick="copyDeviceId(this, \'{0}\')" title="點擊複製裝置代碼 ({0})">📋 ID:{0}</button>'
    '<button type="button" class="id-edit-btn" onclick="triggerEditId()" title="手動指定裝置代碼">✏️</button>'
    '</span>'
)

# ── header 的「手動切換裝置 ID」列（HeaderComponent.render）─────────────
CHROME_ID_EDIT_BTN = "✏️"
CHROME_ID_INPUT_LABEL = "切換裝置 ID"
CHROME_ID_INPUT_PLACEHOLDER = "請輸入 6 位數代碼 (例如 71c8f5)..."
CHROME_ID_SAVE_BTN = "確認切換"
CHROME_ID_CANCEL_BTN = "取消"

# ── 側邊導覽列（components/dashboard_sidebar.py）────────────────────────
CHROME_SIDEBAR_LABEL = "控制儀表板"
CHROME_SIDEBAR_TITLE_MD = "### 📊 功能切換"
CHROME_NAV_MINIMAX = "🎬 影片生成"
CHROME_NAV_UPSCALER = "🔍 畫質放大"
CHROME_NAV_STRATA = "💬 文字生成"

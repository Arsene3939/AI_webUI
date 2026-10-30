"""
CSS and JavaScript definitions for MiniMax-H3 and multi-module AI WebUI.
"""

CUSTOM_CSS = """
/* Responsive adjustments for mobile screens */
.container {
    max-width: 1000px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding: 10px !important;
}

/* Finger-friendly buttons */
button.primary-btn {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    height: 52px !important;
    border-radius: 10px !important;
    margin-top: 10px !important;
    box-shadow: 0 4px 12px rgba(0, 100, 255, 0.25) !important;
}

button.recover-btn {
    font-weight: 600 !important;
    border-radius: 8px !important;
    background-color: #0369a1 !important;
    color: white !important;
}

/* Header Banner */
.header-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    padding: 16px 20px;
    border-radius: 12px;
    margin-bottom: 12px;
    color: #f8fafc;
}

.ip-badge {
    background-color: #0284c7;
    color: white;
    padding: 4px 10px;
    border-radius: 6px;
    font-family: monospace;
    font-weight: bold;
}

.id-badge {
    background-color: #334155;
    color: #38bdf8;
    padding: 3px 8px;
    border-radius: 6px;
    font-family: monospace;
    font-weight: 600;
}

/* Header ID Badge Copy Button */
.id-badge-btn {
    background-color: #334155;
    color: #38bdf8;
    border: 1px solid #475569;
    padding: 3px 10px;
    border-radius: 6px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    line-height: 1.4;
    transition: all 0.15s ease-in-out;
    user-select: none;
    -webkit-user-select: none;
    vertical-align: middle;
}

.id-badge-btn:hover {
    background-color: #475569;
    color: #7dd3fc;
    border-color: #38bdf8;
    box-shadow: 0 0 8px rgba(56, 189, 248, 0.25);
}

.id-badge-btn:active {
    transform: scale(0.96);
    background-color: #1e293b;
}

/* Header ID Edit Icon Button */
.id-edit-btn {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.85rem;
    line-height: 1.4;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease-in-out;
    user-select: none;
    -webkit-user-select: none;
    vertical-align: middle;
}

.id-edit-btn:hover {
    background-color: #475569;
    border-color: #38bdf8;
    box-shadow: 0 0 8px rgba(56, 189, 248, 0.25);
    transform: scale(1.05);
}

.id-edit-btn:active {
    transform: scale(0.95);
}

/* Hidden Trigger Button for clean layout */
.hidden-trigger-btn {
    position: fixed !important;
    left: -9999px !important;
    top: -9999px !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    opacity: 0 !important;
    pointer-events: none !important;
    overflow: hidden !important;
}

/* Mobile video player fix */
video {
    width: 100% !important;
    border-radius: 8px !important;
    background-color: #000;
}

/* Prevent virtual keyboard on dropdowns for mobile */
.gr-dropdown input {
    cursor: pointer !important;
    -webkit-user-select: none !important;
    user-select: none !important;
}

.header-row {
    align-items: center;
    margin-bottom: 4px;
}

/* Two-line status box styling */
.backend-status-box {
    min-height: 48px !important;
    line-height: 1.5 !important;
    display: flex !important;
    align-items: center !important;
    padding: 6px 12px !important;
    margin-top: 4px !important;
    margin-bottom: 8px !important;
    border-radius: 8px !important;
    background: rgba(30, 41, 59, 0.35) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-sizing: border-box !important;
}

.backend-status-box p {
    margin: 0 !important;
    padding: 0 !important;
}

.res-display-box {
    min-height: 44px !important;
    line-height: 1.5 !important;
    display: flex !important;
    align-items: center !important;
    padding: 8px 14px !important;
    margin-top: 4px !important;
    margin-bottom: 6px !important;
    border-radius: 8px !important;
    background: rgba(30, 41, 59, 0.45) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-sizing: border-box !important;
}

.res-display-box p {
    margin: 0 !important;
    padding: 0 !important;
}

/* Sidebar Overlay & Layout Preservation (展開時覆蓋而非擠壓原有UI) */
.sidebar-parent,
.sidebar-parent:has(.sidebar.open),
.sidebar-parent:has(.sidebar.open:not(.right)),
.sidebar-parent:has(.sidebar.open.right),
div:has(> .sidebar.open) {
    padding-left: 0 !important;
    padding-right: 0 !important;
    transition: none !important;
}

.sidebar,
.sidebar.svelte-1uruprb,
div[class*="sidebar"] {
    background: #0f172a !important;
    border-right: 1px solid #334155 !important;
    z-index: 1005 !important;
    width: 260px !important;
}

.sidebar.open,
.sidebar.open.svelte-1uruprb,
div[class*="sidebar"].open {
    box-shadow: 6px 0 24px rgba(0, 0, 0, 0.6) !important;
    z-index: 1005 !important;
}

/* Sidebar 收合拉頁籤（gradio 原生 chevron 預設深色背景下幾乎看不見，這裡改成高對比可辨識樣式）
   展開時位於儀表板右上角、收起時位於螢幕左緣，點一下就收合/展開 */
.sidebar .toggle-button {
    top: 12px !important;
    width: 30px !important;
    height: 40px !important;
    background: #1e293b !important;
    border: 1px solid #38bdf8 !important;
    z-index: 1006 !important;
}

.sidebar .chevron-left {
    width: 10px !important;
    height: 10px !important;
    border-top: 2px solid #7dd3fc !important;
    border-right: 2px solid #7dd3fc !important;
}

.sidebar .toggle-button:hover {
    background: #334155 !important;
    border-color: #7dd3fc !important;
}

/* Mobile Sidebar Width Override (防止手機端展開佔滿全螢幕 100vw) */
@media (max-width: 768px) {
    .sidebar,
    .sidebar.svelte-1uruprb,
    div[class*="sidebar"] {
        width: 260px !important;
        max-width: 80vw !important;
        left: -260px !important;
    }
    .sidebar.open,
    .sidebar.open.svelte-1uruprb,
    div[class*="sidebar"].open {
        transform: translateX(260px) !important;
        width: 260px !important;
        max-width: 80vw !important;
        box-shadow: 8px 0 28px rgba(0, 0, 0, 0.75) !important;
    }
    .sidebar-parent,
    .sidebar-parent:has(.sidebar.open) {
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
}

/* 3 Simple Clean Options for Dashboard (無冗贅按鈕與說明) */
.dashboard-title {
    margin: 4px 0 12px 0 !important;
    color: #e2e8f0 !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
}

.dashboard-simple-radio {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

.dashboard-simple-radio .wrap {
    display: flex !important;
    flex-direction: column !important;
    gap: 8px !important;
}

.dashboard-simple-radio label {
    display: flex !important;
    align-items: center !important;
    padding: 12px 14px !important;
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    cursor: pointer !important;
    transition: all 0.15s ease-in-out !important;
    margin: 0 !important;
}

.dashboard-simple-radio label:hover {
    border-color: #38bdf8 !important;
    background: #253349 !important;
    color: #38bdf8 !important;
}

.dashboard-simple-radio label.selected,
.dashboard-simple-radio label:has(input:checked) {
    border-color: #38bdf8 !important;
    background: #0284c7 !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(2, 132, 199, 0.35) !important;
}

.dashboard-simple-radio input[type="radio"] {
    display: none !important;
}
"""

CUSTOM_HEAD_JS = """
<script>
window.copyDeviceId = function(btn, text) {
    function showSuccess() {
        var orig = btn.innerHTML;
        btn.innerHTML = '✅ 已複製!';
        btn.style.borderColor = '#22c55e';
        btn.style.color = '#86efac';
        setTimeout(function() {
            btn.innerHTML = orig;
            btn.style.borderColor = '';
            btn.style.color = '';
        }, 1500);
    }
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(showSuccess, function() {
            window.fallbackCopy(text, showSuccess);
        });
    } else {
        window.fallbackCopy(text, showSuccess);
    }
};

window.fallbackCopy = function(text, cb) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '-9999px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
        var successful = document.execCommand('copy');
        if (successful) {
            cb();
        } else {
            prompt('請手動選取並複製代碼：', text);
        }
    } catch (err) {
        prompt('請手動選取並複製代碼：', text);
    }
    document.body.removeChild(ta);
};

window.triggerEditId = function() {
    var triggerBtn = document.getElementById('edit-id-trigger-btn');
    if (triggerBtn) {
        var btn = triggerBtn.tagName === 'BUTTON' ? triggerBtn : triggerBtn.querySelector('button');
        if (btn) {
            btn.click();
        } else {
            triggerBtn.click();
        }
    }
};
</script>
"""

"""
ui_text 文案集中包守門測試（Spec 2026-11-03 任務 5）。

目的：確保「使用者看得到的文字只存在 ui_text」不被慢慢破窗——
1) 已遷移的 UI 來源檔不得再內嵌 ui_text 裡長度 ≥12 的文案值（防文案散回各檔案）；
2) ui_text 本身不得反向 import core/views/components/webapp（保持純文案、零循環）；
3) 任務篩選下拉＝比對值的協定：task_manager 與管理頁必須共用同一份常數。
"""
import ast
import pathlib

import ui_text

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 已遷移的 UI 來源檔（新增檔案時請加進來，守門才会覆蓋到）
MIGRATED_FILES = [
    "views/minimax/view.py", "views/minimax/tabs/i2v_tab.py", "views/minimax/tabs/r2v_tab.py",
    "views/minimax/tabs/t2v_tab.py", "views/minimax/admin_tab.py", "components/video_params.py",
    "components/director_block.py", "core/director_client.py", "utils/frame_extractor.py",
    "views/upscaler/view.py", "views/upscaler/admin_tab.py", "components/history_gallery.py",
    "components/media_player.py", "task_manager/manager.py", "task_manager/comfy_progress.py",
    "views/strata/view.py", "views/strata/admin_tab.py", "components/strata_toolbar.py",
    "core/strata_client.py", "components/comfy_toolbar.py", "core/comfy_client.py",
    "core/base_admin_tab.py", "core/admin_manager.py", "core/comfy_admin_tab.py",
    "components/header.py", "components/dashboard_sidebar.py", "webapp/shell.py",
    "webapp/pages_minimax.py", "webapp/pages_upscaler.py", "webapp/pages_strata.py",
]

# 刻意保留的技術值／內部標記（不是文案；見 ui_text/admin.py 檔案說明）
WHITELIST = {
    "16:9 (橫向風景)",   # 解析度選項的資料值（config 清單同值）
    "無可移除",          # 管理員清單佔選的內部偵測標記
    "【使用者提示詞草稿】\n",  # 導演給模型的提示詞框架，非 UI 文案
}


def _string_literals(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
        elif isinstance(node, ast.JoinedStr):
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    out.add(v.value)
    return out


def _ui_text_values(min_len: int = 12):
    vals = set()
    for name in dir(ui_text):
        if name.startswith("_"):
            continue
        v = getattr(ui_text, name)
        if isinstance(v, str) and len(v) >= min_len:
            vals.add(v)
    return vals


class TestUiTextHygiene:
    def test_all_public_constants_are_text(self):
        for name in dir(ui_text):
            if name.startswith("_") or not name.isupper():
                continue  # 小寫名稱是子模組（admin/backend/...），跳過
            v = getattr(ui_text, name)
            assert isinstance(v, (str, dict, tuple, list)), f"ui_text 只放文字/文字容器: {name}"
            if isinstance(v, dict):
                for k, kv in v.items():
                    assert isinstance(k, str) and isinstance(kv, str), name

    def test_no_reverse_imports(self):
        """ui_text 只准 import config（單向依賴，杜絕循環 import）。"""
        for p in (ROOT / "ui_text").glob("*.py"):
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue  # 包內相對 import（from .common import ...）允許
                    mods = [node.module] if node.module else []
                for m in mods:
                    top = m.split(".")[0]
                    assert top == "config", \
                        f"ui_text/{p.name} 不得 import {m}（文案包只准依賴 config）"

    def test_migrated_files_do_not_inline_ui_text_copy(self):
        vals = _ui_text_values()
        offenders = []
        for rel in MIGRATED_FILES:
            path = ROOT / rel
            for lit in _string_literals(path):
                # 破窗條件：來源檔裡又出現一段「完整等於」ui_text 長文案的內嵌字串
                if len(lit) >= 12 and lit in vals and lit not in WHITELIST:
                    offenders.append((rel, lit))
        assert not offenders, f"文案散回來源檔: {offenders}"

    def test_task_filter_protocol_shared(self):
        """篩選下拉文案＝task_manager 比對值：兩邊都必須引用同一份 ui_text 常數。"""
        import core.admin_manager as am
        import task_manager.manager as mgr

        # 同一份常數物件（改字不會一邊改一邊對不上）
        assert am.ADMIN_FILTER_ALL_DEVICES is mgr.ADMIN_FILTER_ALL_DEVICES
        assert am.ADMIN_FILTER_ALL_STATUS is mgr.ADMIN_FILTER_ALL_STATUS
        # manager 的篩選分支必須引用同一份常數（不是重新硬寫字面值）
        import inspect
        src = inspect.getsource(mgr.TaskManager.get_all_tasks)
        for const in ("ADMIN_FILTER_ALL_DEVICES", "ADMIN_FILTER_ALL_STATUS",
                      "ADMIN_FILTER_DONE", "ADMIN_FILTER_ACTIVE", "ADMIN_FILTER_FAILED"):
            assert const in src, f"get_all_tasks 未引用 ui_text.{const}"
        assert am.AdminManager.get_admin_tasks_dropdown_choices.__defaults__ == (
            ui_text.ADMIN_FILTER_ALL_DEVICES, ui_text.ADMIN_FILTER_ALL_STATUS,
        )
        assert ui_text.ADMIN_FILTER_ALL_DEVICES in am.AdminManager.get_admin_device_filter_choices()

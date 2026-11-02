"""
Base administrator tab class providing shared maintenance, hardware monitoring, and IP whitelisting.
Follows Template Method and OOP inheritance pattern.
"""
from typing import Optional, Any
import gradio as gr
from core.admin_manager import AdminManager


class BaseAdminTab:
    """
    Abstract base admin tab for all functional views.
    Encapsulates universally shared administrator features:
    - Server status toggle (Normal / Maintenance)
    - Hardware resource dashboard (RAM, GPU util, VRAM, Disk)
    - Connected devices overview
    - Admin IP whitelist management (Add / Remove)
    """

    def __init__(self, tab_title: str = "⚙️ 管理員專區"):
        self.tab_title = tab_title
        self.tab: Optional[gr.Tab] = None
        self.status_badge: Optional[gr.HTML] = None
        self.toggle_status_btn: Optional[gr.Button] = None
        self.op_msg: Optional[gr.Markdown] = None

        self.hw_dashboard_html: Optional[gr.HTML] = None
        self.refresh_hw_btn: Optional[gr.Button] = None

        self.devices_html: Optional[gr.HTML] = None
        self.refresh_devices_btn: Optional[gr.Button] = None

        # Auto-refresh heartbeat for volatile admin panels (Spec 2026-10-31 round 2 task 3):
        # hardware dashboard + devices overview every 5s; super-user-guarded so regular
        # sessions pay only a cheap IP check per tick.
        self.auto_refresh_timer: Optional[gr.Timer] = None

        self.ip_list_html: Optional[gr.HTML] = None
        self.new_ip_input: Optional[gr.Textbox] = None
        self.add_ip_btn: Optional[gr.Button] = None
        self.remove_ip_dropdown: Optional[gr.Dropdown] = None
        self.remove_ip_btn: Optional[gr.Button] = None

        # Startup resource thresholds (Spec 2026-11-01 round 3 task 2)
        self.threshold_min_ram: Optional[gr.Slider] = None
        self.threshold_max_gpu: Optional[gr.Slider] = None
        self.threshold_min_vram: Optional[gr.Slider] = None
        self.thresholds_save_btn: Optional[gr.Button] = None
        self.thresholds_status: Optional[gr.Markdown] = None

        # PC power controls (Spec 2026-11-02 第 2 輪任務 1)
        self.shutdown_pc_btn: Optional[gr.Button] = None
        self.cancel_shutdown_btn: Optional[gr.Button] = None
        self.pc_power_status: Optional[gr.Markdown] = None

    def render(self, session_ctx: Any) -> gr.Tab:
        """Renders the common admin interface and calls subclass custom render hooks."""
        with gr.Tab(self.tab_title, visible=False) as self.tab:
            gr.Markdown(f"## 🛠️ {self.tab_title}")
            gr.Markdown("此分頁僅對本機操作者 (127.0.0.1) 或已授權之管理員 IP 開放。")

            # 1. Server Service Status Toggle
            gr.Markdown("### 🚦 伺服器服務狀態切換")
            with gr.Row():
                self.status_badge = gr.HTML(AdminManager.build_admin_status_badge(), scale=4)
                self.toggle_status_btn = gr.Button("切換為維護模式", variant="stop", scale=2)
            self.op_msg = gr.Markdown("", elem_classes=["backend-status-box"])

            self.auto_refresh_timer = gr.Timer(value=5.0)

            # 2. Hardware Resource Dashboard
            gr.Markdown("### 🖥️ 硬體資源即時狀態 (Hardware Dashboard)")
            self.hw_dashboard_html = gr.HTML(AdminManager.build_admin_hw_dashboard_html())
            self.refresh_hw_btn = gr.Button("🔄 刷新硬體狀態", variant="secondary")

            # 3. Subclass Custom Content Hook (Inserted before device and IP sections)
            self.render_custom_content(session_ctx)

            # 4. Connected Devices Overview
            gr.Markdown("### 📱 連線裝置總覽")
            self.devices_html = gr.HTML(AdminManager.build_admin_devices_html())
            self.refresh_devices_btn = gr.Button("🔄 刷新裝置列表", variant="secondary")

            # 5. Backend Startup Resource Thresholds
            from config import get_system_thresholds
            _t = get_system_thresholds()
            gr.Markdown("### 📏 後端啟動資源門檻")
            gr.Markdown("ComfyUI 啟動前的資源檢查標準；調整後按下儲存，下次啟動檢查立即採用新值。")
            with gr.Row():
                self.threshold_min_ram = gr.Slider(
                    minimum=0, maximum=128, step=1, value=_t["min_ram_gb"],
                    label="最低可用記憶體 (RAM, GB)", scale=3,
                )
                self.threshold_max_gpu = gr.Slider(
                    minimum=0, maximum=100, step=5, value=_t["max_gpu_util"],
                    label="GPU 使用率上限 (%)", scale=3,
                )
                self.threshold_min_vram = gr.Slider(
                    minimum=0, maximum=24, step=0.5, value=_t["min_vram_gb"],
                    label="最低可用顯存 (VRAM, GB)", scale=3,
                )
            with gr.Row():
                self.thresholds_save_btn = gr.Button("💾 儲存門檻設定", variant="primary", scale=2)
                self.thresholds_status = gr.Markdown("")

            # 6. Admin IP Whitelist Settings
            gr.Markdown("### 🛡️ 管理員名單設定")
            gr.Markdown("在下方輸入指定裝置的 IP 位址，加入後該裝置連線時即可直接操作管理員專屬功能。")
            self.ip_list_html = gr.HTML(AdminManager.build_admin_ip_list_html())
            with gr.Row():
                self.new_ip_input = gr.Textbox(
                    label="新增管理員 IP",
                    placeholder="請輸入欲授權的 IP 位址，例如 192.168.0.11...",
                    scale=7,
                )
                self.add_ip_btn = gr.Button("➕ 加入名單", variant="primary", scale=2)
            with gr.Row():
                self.remove_ip_dropdown = gr.Dropdown(
                    choices=AdminManager.get_admin_ip_remove_choices(),
                    value=AdminManager.get_admin_ip_remove_choices()[0] if AdminManager.get_admin_ip_remove_choices() else "",
                    label="選取欲移除的管理員 IP",
                    filterable=False,
                    scale=7,
                )
                self.remove_ip_btn = gr.Button("🗑️ 移除此 IP", variant="stop", scale=2)

            # 7. PC Power (Spec 2026-11-02 第 2 輪任務 1)
            gr.Markdown("### 💻 電腦電源")
            gr.Markdown("⚠️ 「電腦關機」會關閉這台執行 WebUI 與後端的實體電腦；"
                        "按下後有短暫倒數緩衝，期間可點「取消關機」中止。")
            with gr.Row():
                self.shutdown_pc_btn = gr.Button("🛑 電腦關機", variant="stop", scale=2)
                self.cancel_shutdown_btn = gr.Button("✋ 取消關機", variant="secondary", scale=2)
            self.pc_power_status = gr.Markdown("")

        return self.tab

    def render_custom_content(self, session_ctx: Any) -> None:
        """Hook for subclasses to inject module-specific admin UI controls."""
        pass

    def register_events(self, session_ctx: Any) -> None:
        """Registers events for universally shared controls and calls subclass hook."""
        self.toggle_status_btn.click(
            AdminManager.on_toggle_server_status,
            outputs=[self.status_badge, self.toggle_status_btn, self.op_msg],
        )
        self.refresh_hw_btn.click(
            AdminManager.build_admin_hw_dashboard_html,
            outputs=[self.hw_dashboard_html],
        )
        self.refresh_devices_btn.click(
            AdminManager.build_admin_devices_html,
            outputs=[self.devices_html],
        )

        # Auto-refresh: hardware dashboard + connected devices every 5 seconds
        # (psutil reads + in-memory scan: microseconds, zero impact on the GPU job).
        if self.auto_refresh_timer is not None:
            def auto_admin_refresh(req: gr.Request = None):
                if not AdminManager.is_super_user(req):
                    return gr.update(), gr.update()
                return (
                    AdminManager.build_admin_hw_dashboard_html(),
                    AdminManager.build_admin_devices_html(),
                )

            self.auto_refresh_timer.tick(
                auto_admin_refresh,
                outputs=[self.hw_dashboard_html, self.devices_html],
            )

        def add_ip_and_clear(new_ip, req: gr.Request):
            html, rem_upd, msg = AdminManager.on_add_admin_ip(new_ip, req)
            return html, rem_upd, msg, ""

        self.add_ip_btn.click(
            add_ip_and_clear,
            inputs=[self.new_ip_input],
            outputs=[self.ip_list_html, self.remove_ip_dropdown, self.op_msg, self.new_ip_input],
        )
        self.new_ip_input.submit(
            add_ip_and_clear,
            inputs=[self.new_ip_input],
            outputs=[self.ip_list_html, self.remove_ip_dropdown, self.op_msg, self.new_ip_input],
        )
        self.remove_ip_btn.click(
            AdminManager.on_remove_admin_ip,
            inputs=[self.remove_ip_dropdown],
            outputs=[self.ip_list_html, self.remove_ip_dropdown, self.op_msg],
        )

        # Resource threshold save (Spec 2026-11-01 round 3 task 2)
        self.thresholds_save_btn.click(
            AdminManager.on_save_system_thresholds,
            inputs=[self.threshold_min_ram, self.threshold_max_gpu, self.threshold_min_vram],
            outputs=[self.thresholds_status],
        )

        # PC power controls (Spec 2026-11-02 第 2 輪任務 1)：super-user 門護在 AdminManager 內
        self.shutdown_pc_btn.click(
            AdminManager.on_shutdown_pc,
            outputs=[self.pc_power_status],
        )
        self.cancel_shutdown_btn.click(
            AdminManager.on_cancel_shutdown,
            outputs=[self.pc_power_status],
        )

        # Subclass custom events hook
        self.register_custom_events(session_ctx)

    def wire_page_load(self, blocks: gr.Blocks) -> None:
        """每次開頁從檔案重抓門檻現值（規避 PAGE 單例建置期快照，同 admin prompt 編輯器教訓）。"""
        blocks.load(
            AdminManager.reload_system_thresholds,
            outputs=[self.threshold_min_ram, self.threshold_max_gpu, self.threshold_min_vram],
            api_name=False,
        )

    def register_custom_events(self, session_ctx: Any) -> None:
        """Hook for subclasses to register their own event listeners."""
        pass

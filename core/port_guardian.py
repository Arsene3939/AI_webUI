"""
Network port availability check and conflict diagnostics for WebUI server.
"""
import socket
import subprocess
from typing import List


class PortGuardian:
    """Detects port occupation and prints diagnostic instructions."""

    @staticmethod
    def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
        """Checks whether a local TCP port is already bound."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((host, port)) == 0

    @staticmethod
    def find_pids_on_port(port: int) -> List[str]:
        """Finds PIDs listening on the specified port on Windows."""
        try:
            output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True)
            pids = []
            for line in output.strip().splitlines():
                line_str = line.strip()
                if f":{port}" in line_str and "LISTENING" in line_str:
                    parts = line_str.split()
                    if len(parts) >= 5 and parts[-1] not in pids:
                        pids.append(parts[-1])
            return pids
        except Exception:
            return []

    @staticmethod
    def get_process_name_by_pid(pid: str) -> str:
        """Gets the executable process name for a PID on Windows."""
        try:
            out = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /FO CSV /NH', shell=True, text=True)
            if out and "," in out:
                return out.split(",")[0].strip('"\r\n ')
        except Exception:
            pass
        return "Unknown"

    @classmethod
    def print_port_conflict_help(cls, port: int):
        """Displays clear troubleshooting guide for administrators when target port is occupied."""
        pids = cls.find_pids_on_port(port)
        pid_details = []
        kill_cmds = []
        for pid in pids:
            proc_name = cls.get_process_name_by_pid(pid)
            pid_details.append(f"PID: {pid} ({proc_name})")
            kill_cmds.append(f"taskkill /PID {pid} /F")

        pid_str = ", ".join(pid_details) if pid_details else "無法直接取得（可能為其他使用者或系統服務）"

        print("\n" + "=" * 70)
        print(f"❌ [錯誤] 前端伺服器啟動失敗：連接埠 {port} 已被佔用！")
        print("=" * 70)
        print("【排查診斷資訊】：")
        print(f" • 目標連接埠：{port}")
        print(f" • 佔用進程資訊：{pid_str}")
        print()
        print("【伺服器管理員排查與解決步驟】：")
        print(f" 1. 使用者預設透過 http://127.0.0.1:{port} 訪問，系統維持固定通訊埠而不隨意跳號。")
        print(" 2. 請檢查是否已有先前開啟但未完全關閉的 WebUI 終端機或背景 Python 進程。")
        if kill_cmds:
            print(" 3. 若欲強制結束佔用此連接埠的進程，可開啟命令提示字元（CMD）或 PowerShell 執行：")
            for k_cmd in kill_cmds:
                print(f"    👉 {k_cmd}")
            print(f"    （亦可手動執行 netstat -ano | findstr :{port} 再次確認通訊狀態）")
        else:
            print(f" 3. 可於終端機執行下列指令查詢佔用此連接埠的 PID：")
            print(f"    👉 netstat -ano | findstr :{port}")
            print(f"    再執行 👉 taskkill /PID <查詢到的PID> /F 強制釋放。")
        print(f" 4. 釋放連接埠後，請重新執行 run.bat 啟動伺服器。")
        print("=" * 70 + "\n")

@echo off
title MiniMax-H3 Server Tray Supervisor (Auto-Reload)
cd /d "%~dp0"

set "PYTHON_EXE=F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found at:
    echo %PYTHON_EXE%
    pause
    exit /b 1
)

echo ==========================================================
echo Starting MiniMax-H3 Server in Windows System Tray Mode...
echo - Background Tray Supervisor (Single icon with WebUI/ComfyUI menus)
echo - Auto-Reload Enabled (Changes to .py automatically reload)
echo ==========================================================
echo.

"%PYTHON_EXE%" tray_supervisor.py

if errorlevel 1 (
    echo.
    echo [ERROR] Tray Supervisor exited with error.
    pause
)

@echo off
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

set "WEBUI_DEV_RELOAD=1"

echo ==========================================================
echo Starting MiniMax-H3 AI WebUI in Auto-Reload Mode...
echo (Changes to .py files will automatically reload the server)
echo Pages: http://127.0.0.1:7860/minimax  /upscaler  /strata
echo ==========================================================
echo.

"%PYTHON_EXE%" app.py

if errorlevel 1 (
    echo.
    echo [ERROR] App exited with error.
    pause
)

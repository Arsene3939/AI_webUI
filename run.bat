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

echo ==========================================================
echo Starting MiniMax-H3 Gradio WebUI in Auto-Reload Mode...
echo (Changes to .py files will automatically reload the webpage)
echo ==========================================================
echo.

"%PYTHON_EXE%" -m gradio app.py

if errorlevel 1 (
    echo.
    echo [ERROR] App exited with error.
    pause
)

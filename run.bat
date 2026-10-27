@echo off
cd /d "%~dp0"

set "PYTHON_EXE=F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found at:
    echo %PYTHON_EXE%
    echo Please verify the Comfy-Desktop path.
    pause
    exit /b 1
)

echo ==========================================================
echo Starting MiniMax-H3 Gradio WebUI...
echo Path: %~dp0
echo Python: %PYTHON_EXE%
echo ==========================================================
echo.

"%PYTHON_EXE%" app.py

if errorlevel 1 (
    echo.
    echo [ERROR] App exited with error.
    pause
)

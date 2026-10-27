@echo off
title ComfyUI Backend Server
cd /d "F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"

set "PYTHON_EXE=F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found: %PYTHON_EXE%
    pause
    exit /b 1
)

echo ==========================================================
echo Starting ComfyUI Backend Server (PyTorch CUDA 13.0)...
echo Python: %PYTHON_EXE%
echo Model Path: F:\Comfy_models
echo Listen Address: 0.0.0.0:8188
echo ==========================================================
echo.

"%PYTHON_EXE%" main.py --listen 0.0.0.0 --port 8188 --output-directory "F:\program_file\Comfy-Desktop\ComfyUI-Shared\output" --input-directory "F:\program_file\Comfy-Desktop\ComfyUI-Shared\input"

if errorlevel 1 (
    echo.
    echo [ERROR] ComfyUI backend stopped with error.
    pause
)

@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

set "VENV_PYTHON=F:\program_file\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"

echo ============================================================
echo [1/2] Running Unit Tests (pytest)...
echo ============================================================
"%VENV_PYTHON%" -m pytest tests/ -v
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Unit tests failed! Aborting E2E run.
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo [2/2] Running End-to-End (E2E) Generation Test Suite...
echo ============================================================
"%VENV_PYTHON%" test_e2e.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] End-to-End test failed!
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo [SUCCESS] All Unit Tests and E2E Tests Passed (100% Green)!
echo ============================================================

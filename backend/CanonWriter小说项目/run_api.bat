@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   CanonWriter API Gateway
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    pause
    exit /b 1
)

echo Starting with virtual environment...
echo ========================================
echo   API:   http://localhost:8000
echo   Docs:  http://localhost:8000/docs
echo   Stop:  Ctrl+C
echo ========================================
echo.

".venv\Scripts\python.exe" -m uvicorn api_server:app --reload --host 0.0.0.0 --port 8000

pause

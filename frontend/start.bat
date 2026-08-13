@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   CanonWriter Startup
echo ========================================
echo.
echo   Frontend:  http://localhost:3000
echo   API:       http://localhost:8000
echo   Stop:      Ctrl+C
echo.
echo ========================================
echo.

rem Start backend API if port 8000 is not already listening
set "API_DIR="

rem 查找后端目录：backend\CanonWriter小说项目
if exist "%~dp0..\backend\CanonWriter小说项目\run_api.bat" (
    set "API_DIR=%~dp0..\backend\CanonWriter小说项目"
)

rem 如果上面找不到，尝试其他可能的位置
if not defined API_DIR (
    for /d %%D in ("%~dp0..\backend\*") do (
        if exist "%%~fD\run_api.bat" set "API_DIR=%%~fD"
    )
)

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if errorlevel 1 (
    if defined API_DIR (
        echo [1/3] Starting backend API from: %API_DIR%
        start "CanonWriter API" cmd /k call "%API_DIR%\run_api.bat"
        echo [1/3] Waiting for backend to start...
        timeout /t 5 /nobreak >nul
    ) else (
        echo [ERROR] Backend folder not found!
        echo Please run run_api.bat manually in the backend project folder.
    )
) else (
    echo [1/3] Backend API already running on port 8000.
)

echo [2/3] Starting frontend web server on port 3000...
start http://localhost:3000

echo [3/3] Checking for cpolar (内网穿透)...
where cpolar >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [3/3] cpolar found! Starting tunnel for port 3000...
    echo.
    echo ========================================
    echo   🌐  外网访问链接会显示在 cpolar 窗口中
    echo   复制 https://... 的链接，放到简历上即可！
    echo ========================================
    echo.
    start "CanonWriter Tunnel" cmd /k cpolar http 3000
    echo [3/3] cpolar tunnel started.
) else (
    echo [3/3] cpolar not found. If you want public access, install from https://www.cpolar.com
)

echo.
echo ========================================
echo   ✅ 所有服务已启动！
echo   本地访问: http://localhost:3000
echo ========================================
echo.

python -m http.server 3000

pause

@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"
set "BACKEND_URL=http://127.0.0.1:8000"
set "FRONTEND_URL=http://127.0.0.1:5173"

title HR Assist Launcher
echo.
echo ========================================
echo          Starting HR Assist
echo ========================================
echo.

if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
    echo [ERROR] Backend virtual environment was not found.
    echo Run the one-time setup described in docs\local-development.md.
    goto :failed
)

if not exist "%FRONTEND_DIR%\node_modules" (
    echo [ERROR] Frontend dependencies were not found.
    echo Run the one-time setup described in docs\local-development.md.
    goto :failed
)

where node.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not available in PATH.
    goto :failed
)

powershell.exe -NoProfile -Command "if ((Test-NetConnection 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue).TcpTestSucceeded) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo [ERROR] PostgreSQL is not listening on 127.0.0.1:5432.
    echo Start PostgreSQL, then run this file again.
    goto :failed
)

call :port_in_use 8000
if errorlevel 1 (
    echo [INFO] Port 8000 is already in use; backend launch skipped.
) else (
    echo [INFO] Starting backend at %BACKEND_URL% ...
    start "HR Assist - Backend" /D "%BACKEND_DIR%" cmd.exe /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)

call :port_in_use 5173
if errorlevel 1 (
    echo [INFO] Port 5173 is already in use; frontend launch skipped.
) else (
    echo [INFO] Starting frontend at %FRONTEND_URL% ...
    start "HR Assist - Frontend" /D "%FRONTEND_DIR%" cmd.exe /k "npm run dev -- --host 127.0.0.1"
)

echo [INFO] Waiting for the application ...
powershell.exe -NoProfile -Command "$deadline=(Get-Date).AddSeconds(30); do { try { $r=Invoke-WebRequest '%FRONTEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo [WARN] The frontend did not become ready within 30 seconds.
    echo Check the Backend and Frontend windows for errors.
    goto :failed
)

echo [OK] HR Assist is ready: %FRONTEND_URL%
if /I not "%~1"=="--no-browser" start "" "%FRONTEND_URL%"
exit /b 0

:port_in_use
powershell.exe -NoProfile -Command "if ((Test-NetConnection 127.0.0.1 -Port %1 -WarningAction SilentlyContinue).TcpTestSucceeded) { exit 1 } else { exit 0 }"
exit /b %errorlevel%

:failed
echo.
echo Press any key to close this window.
pause >nul
exit /b 1

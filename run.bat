@echo off
:: Asset Owner Export Tool — browser launcher
:: Double-click this file to start the app.

setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%backend"
set "VENV_DIR=%BACKEND_DIR%\.venv"
set "PORT=8000"
set "URL=http://127.0.0.1:%PORT%"

:: ── 1. Create virtual environment if it doesn't exist ────────────────────────
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Setting up environment (first run only -- this takes about a minute^)...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Could not create virtual environment.
        echo Make sure Python 3.11 or later is installed and on your PATH.
        pause
        exit /b 1
    )
)

set "PYTHON=%VENV_DIR%\Scripts\python.exe"

:: ── 2. Install / upgrade dependencies silently ───────────────────────────────
:: Use "python -m pip" rather than calling pip.exe directly — pip's Windows
:: launcher stub can't safely overwrite its own running executable, which
:: throws "Fatal error in launcher: Unable to create process" during self-upgrade.
"%PYTHON%" -m pip install --quiet --upgrade pip
"%PYTHON%" -m pip install --quiet "%BACKEND_DIR%"

:: ── 3. Start server in background ────────────────────────────────────────────
cd /d "%BACKEND_DIR%"
start /B "" "%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

:: ── 4. Wait until server is accepting connections, then open browser ──────────
set "READY=0"
for /L %%i in (1,1,30) do (
    if "!READY!"=="0" (
        curl -sf "%URL%/api/health" >nul 2>&1
        if not errorlevel 1 set "READY=1"
        if "!READY!"=="0" timeout /t 1 /nobreak >nul
    )
)

start "" "%URL%"

echo App running at %URL%
echo Close this window to stop the server.
echo.

:: Keep window open so the server process stays alive
pause >nul

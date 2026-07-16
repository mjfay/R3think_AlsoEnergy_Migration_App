@echo off
setlocal

:: -----------------------------------------------------------------------
:: AlsoEnergy Asset Owner Export Tool — Windows launcher
:: Double-click this file (or run from Command Prompt) to start the export.
:: On first run it creates a .venv folder and installs dependencies.
:: No admin rights required.
:: -----------------------------------------------------------------------

cd /d "%~dp0"

:: Check for Python
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on this computer.
    echo Please install Python 3.10 or later from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Verify Python version is 3.10+
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.10 or later is required.
    python --version
    echo Please install a newer version from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create virtual environment on first run
if not exist ".venv\Scripts\activate.bat" (
    echo Setting up environment for the first time. This takes about 30 seconds...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
    echo Setup complete.
    echo.
) else (
    call .venv\Scripts\activate.bat
)

:: Run the export
python export.py %*

if errorlevel 1 (
    echo.
    echo The export encountered an error. See the message above for details.
    pause
    exit /b 1
)

pause

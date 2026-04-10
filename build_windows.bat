@echo off
REM Build script for Windows executables
REM Note: Only the basic version works on Windows (evdev is Linux-only)

echo Building Windows executable...

REM Create virtual environment for build if needed
set VENV_DIR=.build_venv
if not exist "%VENV_DIR%" (
    echo Creating build virtual environment...
    python -m venv "%VENV_DIR%"
)

REM Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

REM Install project dependencies and build tools
pip install -r requirements.txt pyinstaller==6.13.0

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

REM Build basic version (the only version that works on Windows)
echo Building autoclicker...
pyinstaller --onefile --windowed --name Autoclicker --hidden-import autoclicker_core --icon=icon.ico --add-data "icon.ico;." --add-data "icon.png;." --add-data "takodachi.png;." autoclicker.py

echo.
echo Build complete! Executable is in the dist\ directory:
echo   - Autoclicker.exe (mouse clicking with dual clickers)
echo.
echo Note: The keyboard presser feature requires Linux (evdev).
echo       On Windows, you may need to run as Administrator for proper functionality.
pause

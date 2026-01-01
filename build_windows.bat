@echo off
REM Build script for Windows executables
REM Note: Only the basic version works on Windows (evdev is Linux-only)

echo Building Windows executable...

REM Check if PyInstaller is installed
where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

REM Build basic version (the only version that works on Windows)
echo Building autoclicker...
pyinstaller --onefile --windowed --name autoclicker autoclicker.py

echo.
echo Build complete! Executable is in the dist\ directory:
echo   - autoclicker.exe (mouse clicking with dual clickers)
echo.
echo Note: The keyboard presser feature requires Linux (evdev).
echo       On Windows, you may need to run as Administrator for proper functionality.
pause

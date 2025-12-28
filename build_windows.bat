@echo off
REM Build script for Windows executables

echo Building Windows executables...

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

REM Build evdev version (recommended - includes keyboard presser)
echo Building autoclicker-evdev (recommended version)...
pyinstaller --onefile --windowed --name autoclicker-evdev autoclicker_evdev.py

REM Build basic version
echo Building autoclicker-basic...
pyinstaller --onefile --windowed --name autoclicker-basic autoclicker.py

echo.
echo Build complete! Executables are in the dist\ directory:
echo   - autoclicker-evdev.exe (recommended - includes keyboard presser)
echo   - autoclicker-basic.exe (mouse only)
echo.
echo Note: On Windows, you may need to run as Administrator for proper functionality
pause

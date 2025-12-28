#!/bin/bash
# Build script for Linux executables

echo "Building Linux executables..."

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller --break-system-packages
fi

# Clean previous builds
rm -rf build dist *.spec

# Build evdev version (recommended - includes keyboard presser)
echo "Building autoclicker-evdev (recommended version)..."
pyinstaller --onefile --name autoclicker-evdev autoclicker_evdev.py

# Build basic version
echo "Building autoclicker-basic..."
pyinstaller --onefile --name autoclicker-basic autoclicker.py

echo ""
echo "Build complete! Executables are in the dist/ directory:"
echo "  - autoclicker-evdev (recommended - includes keyboard presser)"
echo "  - autoclicker-basic (mouse only)"
echo ""
echo "Note: The evdev version requires sudo privileges to run:"
echo "  sudo ./dist/autoclicker-evdev"

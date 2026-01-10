#!/bin/bash
# Build script for Linux executables

echo "Building Linux executables..."

# Create virtual environment for build if needed
VENV_DIR=".build_venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating build virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Install PyInstaller in virtual environment
if ! command -v pyinstaller &> /dev/null; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller
fi

# Install project dependencies
pip install -r requirements-linux.txt 2>/dev/null || true

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

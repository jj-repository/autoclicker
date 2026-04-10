#!/bin/bash
set -euo pipefail
# Build script for Linux executables

echo "Building Linux executables..."

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 1; }

# Create virtual environment for build if needed
VENV_DIR=".build_venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating build virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Install project dependencies and build tools
pip install -r requirements-linux.txt pyinstaller==6.13.0

# Clean previous builds
rm -rf build dist *.spec

# Build evdev version (recommended - includes keyboard presser)
echo "Building autoclicker-evdev (recommended version)..."
pyinstaller --onefile --name Autoclicker-Linux --hidden-import autoclicker_core --add-data "icon.png:." --add-data "takodachi.png:." autoclicker_evdev.py

# Build basic version
echo "Building autoclicker-basic..."
pyinstaller --onefile --name Autoclicker-Basic --hidden-import autoclicker_core --add-data "icon.png:." --add-data "takodachi.png:." autoclicker.py

echo ""
echo "Build complete! Executables are in the dist/ directory:"
echo "  - Autoclicker-Linux (recommended - includes keyboard presser)"
echo "  - Autoclicker-Basic (mouse only)"
echo ""
echo "Note: The evdev version requires sudo privileges to run:"
echo "  sudo ./dist/Autoclicker-Linux"

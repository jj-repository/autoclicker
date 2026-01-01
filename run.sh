#!/bin/bash

# AutoClicker run script

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "Installing dependencies..."
    ./venv/bin/pip install -r requirements.txt
    ./venv/bin/pip install evdev
fi

# Check if running as root (required for evdev version)
if [ "$EUID" -eq 0 ]; then
    echo "Running full version with keyboard presser support..."
    ./venv/bin/python autoclicker_evdev.py
else
    echo "Running basic version (mouse clicking only)..."
    echo "For full features (keyboard presser), run with: sudo ./run.sh"
    ./venv/bin/python autoclicker.py
fi

#!/bin/bash
set -euo pipefail
echo "Installing pynput for root user in dedicated venv..."
sudo python3 -m venv /opt/autoclicker-venv
sudo /opt/autoclicker-venv/bin/pip install pynput
echo "Done! Run with: sudo /opt/autoclicker-venv/bin/python autoclicker.py"

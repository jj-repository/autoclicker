# Overview

v1.20 — Dual auto-clicker with keyboard key presser, configurable hotkeys, hold-button mode, and emergency stop.

## Files
- `autoclicker.py` — main app (pynput, cross-platform)
- `autoclicker.py.sha256` — checksum (regenerate after every edit!)
- `autoclicker_evdev.py` — Linux Wayland/games version (requires sudo for uinput)
- `test_autoclicker.py` — 138 unit tests

## Backend Selection
- **pynput:** Windows, macOS, Linux X11
- **evdev:** Wayland or games that don't detect pynput events (requires root)

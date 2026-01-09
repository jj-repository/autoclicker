# Dual AutoClicker + Keyboard Key Presser

[![Build](https://github.com/jj-repository/autoclicker/actions/workflows/build-release.yml/badge.svg)](https://github.com/jj-repository/autoclicker/actions/workflows/build-release.yml)
[![Latest Release](https://img.shields.io/github/v/release/jj-repository/autoclicker)](https://github.com/jj-repository/autoclicker/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/jj-repository/autoclicker/total)](https://github.com/jj-repository/autoclicker/releases)

A robust, production-ready autoclicker application with dual mouse autoclickers, keyboard key auto-presser, and emergency stop functionality. Features thread-safe operation, error handling, customizable hotkeys, and configurable intervals for all automation modes.

## Features

### Mouse Autoclickers
- **Two independent mouse autoclickers** with side-by-side layout
- **Configurable hotkeys** for each autoclicker (just click and press a key)
- **Adjustable click intervals** (in seconds) for each autoclicker
- **Automatic mutual exclusion**: Starting one mouse autoclicker stops the other
- **Left mouse button** auto-clicking

### Keyboard Key Presser
- **Auto-press any keyboard key** you configure
- **Select target key** from letters, numbers, F-keys, space, arrows, and more
- **Independent operation** - runs alongside mouse clickers
- **Adjustable press intervals**
- **Configurable toggle hotkey**

### Emergency Stop
- **Panic button hotkey** (default: F9) to stop ALL autoclickers instantly
- **Highest priority** - stops everything with one keypress
- **Customizable hotkey**

### General
- **Simple and intuitive GUI** with improved layout
- **Configuration persistence** - all settings saved automatically with validation
- **Toggle on/off** with the same hotkey for each feature
- **Status indicators** for each autoclicker with error states
- **Thread-safe operation** - no race conditions or crashes
- **Robust error handling** - gracefully handles failures
- **Rate limiting** - prevents accidental rapid toggling (200ms cooldown)
- **Input validation** - enforces min (0.01s) and max (60s) intervals to prevent system overload

### Auto-Updates
- **Automatic update checking** on startup (configurable via Help menu)
- **One-click updates** with SHA256 checksum verification for security
- **Backup creation** before applying updates (`.py.backup`)
- **Manual update check** available in Help menu
- **GitHub Releases integration** - opens releases page as alternative

## Installation

### Quick Start (Recommended)
The run script automatically handles everything:

```bash
./run.sh           # Basic version (mouse clicking only)
sudo ./run.sh      # Full version with keyboard presser
```

The script will:
- Create a virtual environment if needed
- Install all dependencies
- Run the appropriate version based on privileges

### Manual Installation

#### Basic Version (autoclicker.py)
Uses pynput for mouse clicking. Works on Linux and Windows without root privileges.

```bash
pip install pynput
python3 autoclicker.py
```

#### Full Version with Keyboard Presser (autoclicker_evdev.py) - Linux Only
Uses evdev for low-level input simulation. Supports both mouse and keyboard automation.

**Requires root/sudo privileges!**

```bash
pip install pynput evdev
sudo python3 autoclicker_evdev.py
```

### Dependencies
- `pynput` - Keyboard hotkey listening
- `evdev` - Low-level input device simulation (Linux evdev version only)
- `tkinter` - GUI (usually pre-installed with Python)

**Requirements files:**
- `requirements.txt` - Cross-platform (Windows/Linux basic version)
- `requirements-linux.txt` - Linux full version with evdev

## Usage

### Initial Setup

1. Run the application (use sudo for evdev version)

2. **Configure Mouse Clickers** (Clicker 1 and Clicker 2):
   - **Interval**: Enter click speed in seconds
     - `0.1` = 10 clicks per second
     - `0.5` = 2 clicks per second
     - `1.0` = 1 click per second
   - Click "Apply Interval" to save
   - **Hotkey**: Click the "Current: [key]" button and press any key
   - Press the hotkey to start/stop that clicker

3. **Configure Keyboard Key Presser**:
   - **Key to Press**: Click the button and press the key you want to auto-press
   - **Interval**: Set how fast the key should be pressed
   - Click "Apply Interval" to save
   - **Toggle Hotkey**: Set the hotkey to start/stop key pressing
   - Press the hotkey to start/stop the key presser

4. **Emergency Stop**:
   - Configure the emergency stop hotkey (default: F9)
   - Press it anytime to stop ALL autoclickers and key presser instantly

### During Use

- **Mouse clickers**: Starting one stops the other (mutual exclusion)
- **Keyboard presser**: Runs independently, can work alongside mouse clickers
- **Emergency stop**: Stops everything at once
- All settings are saved automatically to `~/.config/autoclicker/config.json`
- **Update settings**: Toggle "Check for Updates on Startup" in Help menu

## Default Settings

**Clicker 1 (Mouse):**
- Hotkey: `F6`
- Interval: `0.1` seconds (10 clicks per second)

**Clicker 2 (Mouse):**
- Hotkey: `F7`
- Interval: `0.5` seconds (2 clicks per second)

**Keyboard Key Presser:**
- Hotkey: `F8`
- Target Key: `Space`
- Interval: `0.1` seconds (10 presses per second)

**Emergency Stop:**
- Hotkey: `F9`

## Supported Keys for Keyboard Presser

- **Letters**: A-Z
- **Numbers**: 0-9
- **Function Keys**: F1-F12
- **Special Keys**: Space, Enter, Tab, Escape, Backspace, Delete
- **Arrow Keys**: Up, Down, Left, Right
- **Navigation**: Home, End, Page Up, Page Down, Insert
- **Modifiers**: Shift, Ctrl, Alt

## Notes

- The application must be running for hotkeys to work
- **Mouse clicking** happens at the current mouse position
- Only **left mouse button** clicks are supported for mouse autoclickers
- **Keyboard presser** simulates actual keypresses (works in games, applications, etc.)
- Mouse clickers have **mutual exclusion** - only one can run at a time
- Keyboard presser is **independent** and can run alongside mouse clickers
- **Emergency stop** has the highest priority and stops everything
- The evdev version requires **root/sudo** privileges to create virtual input devices
- All settings persist between sessions

## Technical Improvements

This application includes enterprise-grade stability and safety features:

- **Thread Safety**: All state-changing operations use mutex locks to prevent race conditions
- **Error Recovery**: Click/press loops include exception handling with visual error indicators
- **Rate Limiting**: 200ms cooldown on hotkey presses prevents accidental double-toggles
- **Input Validation**:
  - Minimum interval: 0.01s (prevents system DoS)
  - Maximum interval: 60s (prevents unreasonable values)
  - Config file validation with safe fallbacks
- **Graceful Degradation**: Invalid config values don't crash the app
- **Thread-Safe Interval Updates**: Intervals are read atomically to prevent mid-update inconsistencies

## Troubleshooting

### "Permission denied" errors (evdev version)
Run with sudo:
```bash
sudo python3 autoclicker_evdev.py
```

### Hotkeys not working
- Make sure the application window is running (doesn't need focus)
- Check that you're not in "hotkey capture" mode (button shows "Press a key...")
- Try reconfiguring the hotkey
- Wait 200ms between hotkey presses (rate limiting)

### Keys not pressing / clicks not working
- **evdev version**: Make sure you're running with sudo
- Check that the status shows "Clicking..." or "Pressing..."
- If status shows "Error" (orange), check console output for details
- Verify the interval is set correctly (min 0.01s, max 60s)

### Error status (orange indicator)
- Check the terminal/console for detailed error messages
- Virtual device initialization may have failed
- Try restarting the application with proper permissions

### Update issues
- **"Checksum verification failed"**: The downloaded file may be corrupted, try again
- **"Could not find checksum file"**: Update not available for this version, visit GitHub releases
- **Cannot check for updates**: Check your internet connection
- **Backup file created**: If update fails, restore from `.py.backup` file

## Building Executables

### Linux
```bash
pip install pyinstaller
# Full version (requires sudo to run):
pyinstaller --onefile autoclicker_evdev.py
# Basic version (no sudo required):
pyinstaller --onefile autoclicker.py
```

### Windows
```bash
pip install pyinstaller
pyinstaller --onefile --windowed autoclicker.py
# Output: dist\autoclicker.exe
```

Note: Windows only supports the basic version (autoclicker.py) as evdev is Linux-only.

## License

MIT License - Feel free to use and modify as needed.

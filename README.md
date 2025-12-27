# Dual AutoClicker + Keyboard Key Presser

A lightweight autoclicker application with dual mouse autoclickers, keyboard key auto-presser, and emergency stop functionality. Features customizable hotkeys and intervals for all automation modes.

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
- **Configuration persistence** - all settings saved automatically
- **Toggle on/off** with the same hotkey for each feature
- **Status indicators** for each autoclicker

## Installation

### Option 1: Standard Version (autoclicker.py)
Uses pynput for mouse clicking. Works on most systems but may have permission issues.

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Install dependencies:
```bash
./venv/bin/pip install -r requirements.txt
```

3. Run:
```bash
./run.sh
```

### Option 2: Advanced Version with Keyboard Presser (autoclicker_evdev.py) - Recommended
Uses evdev for low-level input simulation. Supports both mouse and keyboard automation.

**Requires root/sudo privileges!**

1. Install dependencies:
```bash
pip install pynput evdev --break-system-packages
```

Or use the provided script:
```bash
./install_pynput_root.sh
```

2. Run with sudo:
```bash
sudo python3 autoclicker_evdev.py
```

### Dependencies
- `pynput` - Keyboard hotkey listening
- `evdev` - Low-level input device simulation (evdev version only)
- `tkinter` - GUI (usually pre-installed with Python)

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

### Keys not pressing / clicks not working
- **evdev version**: Make sure you're running with sudo
- Check that the status shows "Clicking..." or "Pressing..."
- Verify the interval is set correctly

## License

MIT License - Feel free to use and modify as needed.

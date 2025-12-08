# Dual AutoClicker

A lightweight dual autoclicker application with customizable hotkeys and click intervals for two independent autoclickers.

## Features

- **Two independent autoclickers** side by side
- **Configurable hotkeys** for each autoclicker (just click and press a key)
- **Adjustable click intervals** (in seconds) for each autoclicker
- **Automatic mutual exclusion**: Starting one autoclicker stops the other
- **Simple and intuitive GUI**
- **Toggle on/off** with the same hotkey

## Installation

1. Create a virtual environment (required for Arch Linux and other externally-managed Python environments):
```bash
python -m venv venv
```

2. Install the required dependencies:
```bash
./venv/bin/pip install -r requirements.txt
```

Alternatively, just run the provided script (it handles everything):
```bash
./run.sh
```

## Usage

Run the application using the run script:
```bash
./run.sh
```

Or manually activate the virtual environment:
```bash
source venv/bin/activate
python autoclicker.py
```

2. Configure each autoclicker:

   **For each autoclicker (Clicker 1 and Clicker 2):**

   - **Click Interval**: Enter how fast clicks should occur (in seconds). For example:
     - `0.1` = 10 clicks per second
     - `0.5` = 2 clicks per second
     - `1.0` = 1 click per second
   - Click "Apply Interval" to save the interval

   - **Toggle Hotkey**: Click the "Current: [key]" button and press any key to set it
     - Function keys: `F1`, `F2`, ... `F12`
     - Letters: `a`, `b`, `c`, etc.
     - Special keys: `space`, `esc`, `enter`, `tab`, etc.
   - The hotkey is applied immediately after pressing it

3. Press a hotkey to start its autoclicker

4. Press the same hotkey again to stop it

5. Starting one autoclicker will automatically stop the other

## Default Settings

**Clicker 1:**
- Hotkey: `F6`
- Interval: `0.1` seconds (10 clicks per second)

**Clicker 2:**
- Hotkey: `F7`
- Interval: `0.5` seconds (2 clicks per second)

## Notes

- The application must be running for hotkeys to work
- Clicking happens at the current mouse position
- Only left mouse button clicks are supported
- **Only one autoclicker can be active at a time** - starting one will automatically stop the other
- This allows you to quickly switch between two different click speeds without reconfiguring

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Dual AutoClicker** is a Python desktop application that provides automated mouse clicking functionality with dual clicker support. It features a tkinter GUI and supports both pynput (cross-platform) and evdev (Linux-specific) backends.

**Version:** 1.2.1

## Files Structure

```
autoclicker/
├── autoclicker.py          # Main application (pynput backend - cross-platform)
├── autoclicker_evdev.py    # Linux/Wayland version using evdev + uinput
├── test_autoclicker.py     # Unit tests (31 tests)
└── CLAUDE.md               # This file
```

## Running the Application

```bash
# Cross-platform version (Windows, macOS, Linux X11)
python autoclicker.py

# Linux with Wayland or games requiring low-level input
sudo python autoclicker_evdev.py  # Requires root for uinput access

# Run tests
python -m pytest test_autoclicker.py -v
```

## Architecture Overview

### Backend Selection

- **autoclicker.py (pynput)**: Uses pynput library for mouse control and keyboard hotkey detection. Works on Windows, macOS, and Linux with X11.
- **autoclicker_evdev.py (evdev)**: Uses evdev for keyboard input and uinput for mouse output. Required for Wayland or games that don't detect pynput events.

### Core Components

1. **DualAutoClicker class**: Main application class containing all UI and logic
2. **Thread-safe state**: Uses `threading.Lock()` for clicker state access
3. **Hotkey system**: Global keyboard listener for start/stop hotkeys
4. **Config persistence**: JSON config in `~/.config/autoclicker/config.json`

### Key Patterns

**Thread Safety:**
```python
with self.clicker1_lock:
    self.clicker1_clicking = True
```

**UI Updates from Threads:**
```python
self.window.after(0, lambda: self._show_update_dialog(...))
```

**Hotkey Rate Limiting:**
- 200ms cooldown between hotkey presses to prevent rapid toggling

## Configuration

**Config Path:** `~/.config/autoclicker/config.json`

**Stored Settings:**
- Clicker intervals (float, in seconds)
- Hotkey assignments (serialized Key/KeyCode objects)
- Hotkey display names

**Interval Constraints:**
- Minimum: 0.01s (10ms, 100 clicks/sec max)
- Maximum: 60.0s

## Update System

**Status:** Fully implemented with SHA256 verification

**Components:**
- `_check_for_updates()`: Fetches latest release from GitHub API
- `_version_newer()`: Semantic version comparison
- `_show_update_dialog()`: Modal dialog with Update Now / Open Releases / Later
- `_apply_update()`: Downloads, verifies SHA256 checksum, backs up old file, applies update

**GitHub Integration:**
- Repository: `jj-repository/autoclicker`
- API: `https://api.github.com/repos/jj-repository/autoclicker/releases/latest`
- Checksum file: `autoclicker.py.sha256`

**Security:**
- SHA256 checksum verification required
- Creates `.py.backup` before replacing
- Aborts if checksum missing or mismatched

## Dependencies

### autoclicker.py (pynput version)
- `tkinter` (standard library)
- `pynput` - Mouse control and keyboard listening
- `json` (standard library)
- `threading` (standard library)

### autoclicker_evdev.py
- `tkinter` (standard library)
- `evdev` - Linux input device access
- `pynput.keyboard` - Key constants only

## Testing

**Test File:** `test_autoclicker.py`

**Test Categories:**
- `TestValidateInterval` (9 tests): Interval validation edge cases
- `TestKeyMapping` (7 tests): Tkinter to evdev key conversion
- `TestKeySerialization` (7 tests): Key save/load for config
- `TestKeyDisplayName` (4 tests): Human-readable key names
- `TestConfigPersistence` (2 tests): Config file handling
- `TestConstants` (2 tests): Module constants

**Running Tests:**
```bash
python -m pytest test_autoclicker.py -v
python -m pytest test_autoclicker.py --tb=short  # Shorter output
```

## Known Issues / Technical Debt

1. **No auto_check_updates toggle**: Currently always checks on startup, users cannot disable
2. **evdev version requires root**: Needs uinput access, could use udev rules instead
3. **No per-clicker mouse button selection**: Both clickers use left-click

## Common Development Tasks

### Adding a new setting
1. Add default value in `__init__`
2. Add to `save_config()` serialization
3. Add to `load_config()` deserialization with fallback
4. Add UI control in `setup_ui()`

### Modifying hotkey behavior
- Key conversion: `_tk_key_to_evdev()` (evdev version)
- Key serialization: `_serialize_key()` / `_deserialize_key()`
- Display names: `_get_key_display_name()`

### Testing changes
- Mock evdev/pynput modules for platform-independent testing
- Use `unittest.mock.patch` for file operations
- Tests use `tempfile` for config file testing

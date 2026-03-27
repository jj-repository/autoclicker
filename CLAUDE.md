# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AutoClicker** is a Python desktop application that provides automated mouse clicking and keyboard key pressing functionality with dual clicker support. It features a PyQt6 GUI (using the GUI-Template pattern) and supports both pynput (cross-platform) and evdev (Linux-specific) backends.

**Version:** 2.0.0

## Versioning

Version bumps default to **+0.0.1** (patch) unless explicitly told otherwise.

## IMPORTANT: Checksum Rule

**Every time `autoclicker.py` is modified, regenerate `autoclicker.py.sha256` before committing:**

```bash
sha256sum autoclicker.py > autoclicker.py.sha256
```

The in-app update system fetches this file from the tagged commit on GitHub to verify the download. If it's missing or stale, users will see "No checksum file found" and the update will be blocked. The CI workflow validates the checksum matches on every build.

## Files Structure

```
autoclicker/
├── autoclicker.py          # Main application (pynput backend - cross-platform, PyQt6 GUI)
├── autoclicker_evdev.py    # Linux/Wayland version using evdev + uinput (tkinter GUI)
├── test_autoclicker.py     # Unit tests (37 tests)
└── CLAUDE.md               # This file
```

## Running the Application

```bash
# Cross-platform version (Windows, macOS, Linux X11)
pip install -r requirements.txt
python autoclicker.py

# Linux with Wayland or games requiring low-level input
sudo python autoclicker_evdev.py  # Requires root for uinput access

# Run tests
python -m pytest test_autoclicker.py -v
```

## Architecture Overview

### Backend Selection

- **autoclicker.py (pynput)**: Uses pynput library for mouse control, keyboard key pressing, and hotkey detection. PyQt6 GUI using the GUI-Template pattern. Works on Windows, macOS, and Linux with X11.
- **autoclicker_evdev.py (evdev)**: Uses evdev for keyboard input and uinput for mouse/keyboard output. Required for Wayland or games that don't detect pynput events. Uses tkinter GUI (not migrated).

### GUI Structure (autoclicker.py)

Follows the GUI-Template pattern (`AppWindow(QMainWindow)`):

- **Tabs:** Clicker 1, Clicker 2, Key Presser, [spacer], Settings, Help
- **`_build_groups()`** — creates `_clicker1_group`, `_clicker2_group`, `_keypresser_group`
- **`_build_tabs()`** — arranges groups into tabs via `_add_tab()`
- **`_build_settings_tab()`** — Emergency Stop group + dark mode toggle + auto-update + mascot
- **`_build_help_tab()`** — help sections + Readme/Report Bug buttons
- **`self.widgets`** — registry for all named widgets

### Key Patterns

**Thread Safety:**
```python
with self.clicker1_lock:
    self.clicker1_clicking = True
```

**UI Updates from Threads (cross-thread safe):**
```python
QTimer.singleShot(0, lambda: self._show_update_dialog(...))
```

**Hotkey Rate Limiting:**
- 200ms cooldown between hotkey presses to prevent rapid toggling

**Config Load Guard:**
```python
self._loading = True
# ... populate widgets ...
self._loading = False
```
Prevents `valueChanged` signals from triggering `_save_config()` during load.

## Configuration

**Config Path:** `~/.config/autoclicker/config.json`

**Stored Settings (backward compatible with v1.x):**
- `clicker1_interval`, `clicker2_interval` (float, in seconds)
- `keypresser_target_key_pynput`, `keypresser_target_key_display`
- `clicker1_hotkey_pynput`, `clicker1_hotkey_display`
- `clicker2_hotkey_pynput`, `clicker2_hotkey_display`
- `keypresser_hotkey_pynput`, `keypresser_hotkey_display`
- `emergency_stop_hotkey_pynput`, `emergency_stop_hotkey_display`

**Interval Constraints:**
- Minimum: 0.01s (10ms, 100 clicks/sec max)
- Maximum: 60.0s

## Update System

**Status:** Fully implemented with SHA256 verification

**Components:**
- `_check_for_updates()`: Fetches latest release from GitHub API
- `_version_newer()`: Semantic version comparison
- `_show_update_dialog()`: QMessageBox with Update Now / Open Releases / Later
- `_apply_update()`: Downloads, verifies SHA256 checksum, backs up old file, applies update, quits app

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
- `PyQt6>=6.5` - GUI framework
- `pynput` - Mouse control and keyboard listening
- `json`, `threading`, `pathlib` (standard library)

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
- `TestVersionComparison` (6 tests): Semantic version comparison with pre-release support

**Running Tests:**
```bash
python -m pytest test_autoclicker.py -v
python -m pytest test_autoclicker.py --tb=short  # Shorter output
```

## Security Features

- **Download size validation**: MAX_DOWNLOAD_SIZE (5MB) limit for update downloads
- **SHA256 checksum verification**: Required for all updates
- **Backup before update**: Creates `.py.backup` before applying updates
- **Hotkey capture lock**: Thread-safe hotkey capture state
- **Thread-safe UI updates**: Uses `QTimer.singleShot()` for cross-thread UI scheduling
- **Thread-safe hotkey timing**: Hotkey rate limiting protected by lock

## Common Development Tasks

### Adding a new setting
1. Add default value in `_init_state()`
2. Add to `_save_config()` serialization
3. Add to `_load_config()` deserialization with fallback
4. Add UI control in `_build_groups()`

### Modifying hotkey behavior
- Key serialization: `_serialize_key()` / `_deserialize_key()`
- Display names: `_get_key_display_name()`
- Capture: `_capture_hotkey(setter_fn, btn)`

### Testing changes
- Mock evdev/pynput modules for platform-independent testing
- Use `unittest.mock.patch` for file operations
- Tests use `tempfile` for config file testing

---

## Review Status

> **Last Full Review:** 2026-03-27
> **Status:** Production Ready

### Security Review ✅
- [x] Path traversal protection (config paths validated)
- [x] Input validation (interval bounds, key serialization)
- [x] No hardcoded secrets
- [x] Safe subprocess usage (N/A - no subprocess)
- [x] Download size validation (5MB limit)
- [x] SHA256 checksum verification for updates
- [x] Backup before update

### Thread Safety Review ✅
- [x] Clicker state protected by locks
- [x] Hotkey timing dictionary protected by lock
- [x] UI updates via `QTimer.singleShot()` (cross-thread safe)
- [x] Hotkey capture state protected

### Code Quality ✅
- [x] All tests passing (37 tests)
- [x] No unused imports/variables
- [x] Consistent error handling
- [x] PyQt6 GUI-Template pattern

## Intentional Design Decisions

| Decision | Rationale |
|----------|-----------|
| PyQt6 GUI (v2.0) | Matches GUI-Template pattern used across other apps; better theming |
| evdev version keeps tkinter | evdev version is Linux-only sudo tool; PyQt6 migration not needed |
| Two separate files (pynput/evdev) | Different backends for different platforms, keeps code simpler than runtime switching |
| Root required for evdev | uinput requires elevated privileges; udev rules would add setup complexity |
| Left-click only | Simplicity; right-click selection would add UI complexity for minimal benefit |
| 200ms hotkey cooldown | Prevents accidental double-toggles; tested value that feels responsive |
| Config in ~/.config/ | Standard XDG location for Linux; works cross-platform |
| Backward-compatible config keys | Same JSON keys as v1.x so existing user configs are preserved |

## Won't Fix (Accepted Limitations)

| Issue | Reason |
|-------|--------|
| evdev requires sudo | By design - uinput needs privileges. Users can set up udev rules if desired |
| No per-clicker button selection | Low demand; adds UI complexity |
| No click patterns (double-click, etc.) | Feature creep; simple tool should stay simple |
| pynput version doesn't work in some games | Use evdev version for games; documented in README |

## Completed Optimizations

- ✅ Thread-safe state management
- ✅ Hotkey rate limiting
- ✅ Safe UI updates from threads (QTimer.singleShot)
- ✅ Config persistence with validation
- ✅ Update system with verification
- ✅ PyQt6 GUI migration (v2.0.0)
- ✅ Dark/light theme toggle
- ✅ Window geometry persistence

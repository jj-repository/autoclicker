# Architecture

`DualAutoClicker` class — all UI and logic.
- Thread-safe state via `threading.Lock()`
- Global keyboard listener for hotkeys
- 200ms hotkey cooldown (prevents rapid toggling)

## Thread Patterns
```python
# Thread safety
with self.clicker1_lock:
    self.clicker1_clicking = True

# UI updates from threads (pynput)
self.window.after(0, lambda: self._show_update_dialog(...))

# UI updates from threads (evdev — crash-safe)
self._safe_after(0, lambda: self._show_update_dialog(...))
```

## Adding a New Setting
1. Default value in `__init__`
2. Add to `save_config()` serialization
3. Add to `load_config()` with fallback
4. Add UI in `setup_ui()`

## Hotkey System
- Key conversion: `_tk_key_to_evdev()` (evdev)
- Serialization: `_serialize_key()` / `_deserialize_key()`
- Display: `_get_key_display_name()`

## Clicker Modes
- **Click mode** (default): `action_loop` thread fires `perform_click()` at the configured interval.
- **Hold mode**: `_start_clickerN_locked` calls `_press_mouse_button()` once, stores the held button in `clickerN_held_button`, and skips the thread. `_stop_clickerN_locked` calls `_release_mouse_button()` and clears the field. Triggered by the per-clicker `Hold button` checkbox in the UI; persisted as `clickerN_hold_mode` in config. Emergency stop and `closeEvent` go through the standard stop path so a held button is always released on shutdown.

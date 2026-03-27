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

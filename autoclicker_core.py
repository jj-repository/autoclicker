"""Shared logic for both autoclicker backends (PyQt6 and evdev/tkinter)."""

from __future__ import annotations

import re
import time

from pynput.keyboard import Key, KeyCode

# Allowed key names for deserialize_key (defense-in-depth)
_VALID_KEY_NAME = re.compile(r"^[a-z0-9_]+$")

# ── Interval Constants ────────────────────────────────────────────────
MIN_INTERVAL = 0.01
MAX_INTERVAL = 60.0
DEFAULT_CLICKER1_INTERVAL = 0.1
DEFAULT_CLICKER2_INTERVAL = 0.5
DEFAULT_KEYPRESSER_INTERVAL = 0.1


def validate_interval(interval, default):
    """Validate interval is within acceptable bounds."""
    try:
        v = float(interval)
        if MIN_INTERVAL <= v <= MAX_INTERVAL:
            return v
    except (ValueError, TypeError):
        pass
    return default


def serialize_key(key):
    """Convert a pynput key to a JSON-serializable format."""
    if hasattr(key, "name"):
        return {"type": "special", "name": key.name}
    elif hasattr(key, "char"):
        return {"type": "char", "char": key.char}
    return {"type": "special", "name": "f6"}


def deserialize_key(key_data):
    """Convert JSON data back to a pynput key."""
    if not isinstance(key_data, dict):
        return Key.f6
    key_type = key_data.get("type", "special")
    if not isinstance(key_type, str):
        return Key.f6
    if key_type == "special":
        name = key_data.get("name", "f6")
        if not isinstance(name, str) or not _VALID_KEY_NAME.match(name):
            return Key.f6
        return getattr(Key, name, Key.f6)
    elif key_type == "char":
        char = key_data.get("char")
        if char and isinstance(char, str) and len(char) == 1:
            try:
                return KeyCode.from_char(char)
            except (ValueError, TypeError):
                return Key.f6
    return Key.f6


def action_loop(stop_event, get_interval, action_fn, on_error):
    """Shared timing loop for clickers and key presser.

    Uses monotonic clock for drift compensation and Event.wait for
    sleep so that stop signals take effect immediately.
    """
    next_time = time.monotonic()
    while not stop_event.is_set():
        interval = get_interval()
        try:
            action_fn()
        except Exception as e:
            on_error(e)
            break
        next_time += interval
        sleep_dur = next_time - time.monotonic()
        if sleep_dur > 0:
            if stop_event.wait(timeout=sleep_dur):
                break
        else:
            next_time = time.monotonic()


def dispatch_hotkey(key, hotkey_actions, timing_lock, last_hotkey_time, cooldown):
    """Shared hotkey dispatch with rate limiting.

    hotkey_actions: list of (hotkey, action_callable) pairs.
    Emergency stop should be first for priority.
    """
    current_time = time.time()
    key_str = str(key)
    with timing_lock:
        if key_str in last_hotkey_time:
            if current_time - last_hotkey_time[key_str] < cooldown:
                return
        last_hotkey_time[key_str] = current_time
        # Prune stale entries to prevent unbounded growth
        if len(last_hotkey_time) > 20:
            cutoff = current_time - cooldown * 2
            stale = [k for k, v in last_hotkey_time.items() if v < cutoff]
            for k in stale:
                del last_hotkey_time[k]

    try:
        for hotkey, action in hotkey_actions:
            if key == hotkey:
                action()
                return
    except AttributeError:
        pass  # Key comparison failed with some special key objects


def get_key_display_name(key):
    """Get a human-readable display name for a pynput key."""
    if hasattr(key, "name"):
        name = key.name
        if name.startswith("f") and name[1:].isdigit():
            return name.upper()
        return name.capitalize()
    elif hasattr(key, "char") and key.char:
        return key.char.upper()
    return str(key)

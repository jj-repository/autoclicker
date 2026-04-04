"""Shared logic for both autoclicker backends (PyQt6 and evdev/tkinter)."""

from __future__ import annotations

from pynput.keyboard import Key, KeyCode

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
        if not isinstance(name, str):
            return Key.f6
        return getattr(Key, name, Key.f6)
    elif key_type == "char":
        char = key_data.get("char")
        if char and isinstance(char, str) and len(char) == 1:
            try:
                return KeyCode.from_char(char)
            except Exception:
                return Key.f6
    return Key.f6


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

#!/usr/bin/env python3
"""Unit tests for autoclicker.py (PyQt6) and autoclicker_evdev.py (tkinter/evdev).

Tests call actual production methods — no re-implementations.
"""

import hashlib
import json
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# ── Mock evdev (Linux-only) ──────────────────────────────────────────
sys.modules["evdev"] = MagicMock()
sys.modules["evdev"].UInput = MagicMock()
sys.modules["evdev"].ecodes = MagicMock()
sys.modules["evdev"].ecodes.KEY_SPACE = 57
sys.modules["evdev"].ecodes.KEY_ENTER = 28
sys.modules["evdev"].ecodes.KEY_TAB = 15
sys.modules["evdev"].ecodes.KEY_ESC = 1
sys.modules["evdev"].ecodes.KEY_BACKSPACE = 14
sys.modules["evdev"].ecodes.KEY_DELETE = 111
sys.modules["evdev"].ecodes.KEY_UP = 103
sys.modules["evdev"].ecodes.KEY_DOWN = 108
sys.modules["evdev"].ecodes.KEY_LEFT = 105
sys.modules["evdev"].ecodes.KEY_RIGHT = 106
sys.modules["evdev"].ecodes.KEY_HOME = 102
sys.modules["evdev"].ecodes.KEY_END = 107
sys.modules["evdev"].ecodes.KEY_PAGEUP = 104
sys.modules["evdev"].ecodes.KEY_PAGEDOWN = 109
sys.modules["evdev"].ecodes.KEY_INSERT = 110
sys.modules["evdev"].ecodes.KEY_LEFTSHIFT = 42
sys.modules["evdev"].ecodes.KEY_RIGHTSHIFT = 54
sys.modules["evdev"].ecodes.KEY_LEFTCTRL = 29
sys.modules["evdev"].ecodes.KEY_RIGHTCTRL = 97
sys.modules["evdev"].ecodes.KEY_LEFTALT = 56
sys.modules["evdev"].ecodes.KEY_RIGHTALT = 100
sys.modules["evdev"].ecodes.KEY_F1 = 59
sys.modules["evdev"].ecodes.KEY_F2 = 60
sys.modules["evdev"].ecodes.KEY_F3 = 61
sys.modules["evdev"].ecodes.KEY_F4 = 62
sys.modules["evdev"].ecodes.KEY_F5 = 63
sys.modules["evdev"].ecodes.KEY_F6 = 64
sys.modules["evdev"].ecodes.KEY_F7 = 65
sys.modules["evdev"].ecodes.KEY_F8 = 66
sys.modules["evdev"].ecodes.KEY_F9 = 67
sys.modules["evdev"].ecodes.KEY_F10 = 68
sys.modules["evdev"].ecodes.KEY_F11 = 87
sys.modules["evdev"].ecodes.KEY_F12 = 88
sys.modules["evdev"].ecodes.KEY_A = 30
sys.modules["evdev"].ecodes.KEY_B = 48
sys.modules["evdev"].ecodes.KEY_Z = 44
sys.modules["evdev"].ecodes.KEY_0 = 11
sys.modules["evdev"].ecodes.KEY_1 = 2
sys.modules["evdev"].ecodes.KEY_9 = 10
sys.modules["evdev"].ecodes.BTN_LEFT = 272
sys.modules["evdev"].ecodes.BTN_RIGHT = 273
sys.modules["evdev"].ecodes.BTN_MIDDLE = 274
sys.modules["evdev"].ecodes.EV_KEY = 1
sys.modules["evdev"].ecodes.KEY_KPDOT = 83

# ── Mock pynput with SimpleNamespace-based key objects ───────────────
# SimpleNamespace avoids the MagicMock `.name` property issue.

_mock_key_f6 = types.SimpleNamespace(name="f6")
_mock_key_f7 = types.SimpleNamespace(name="f7")
_mock_key_f8 = types.SimpleNamespace(name="f8")
_mock_key_f9 = types.SimpleNamespace(name="f9")

mock_key = types.SimpleNamespace(
    # F-keys used in tests and by KeyCaptureDialog class-level code
    **{f"f{i}": types.SimpleNamespace(name=f"f{i}") for i in range(1, 13)},
    # Special keys referenced at class level in autoclicker.py KeyCaptureDialog
    space=types.SimpleNamespace(name="space"),
    enter=types.SimpleNamespace(name="enter"),
    tab=types.SimpleNamespace(name="tab"),
    esc=types.SimpleNamespace(name="esc"),
    backspace=types.SimpleNamespace(name="backspace"),
    delete=types.SimpleNamespace(name="delete"),
    up=types.SimpleNamespace(name="up"),
    down=types.SimpleNamespace(name="down"),
    left=types.SimpleNamespace(name="left"),
    right=types.SimpleNamespace(name="right"),
    home=types.SimpleNamespace(name="home"),
    end=types.SimpleNamespace(name="end"),
    page_up=types.SimpleNamespace(name="page_up"),
    page_down=types.SimpleNamespace(name="page_down"),
    insert=types.SimpleNamespace(name="insert"),
    shift_l=types.SimpleNamespace(name="shift_l"),
    ctrl_l=types.SimpleNamespace(name="ctrl_l"),
    alt_l=types.SimpleNamespace(name="alt_l"),
)
# Keep handy references for test assertions
_mock_key_f6 = mock_key.f6
_mock_key_f7 = mock_key.f7
_mock_key_f8 = mock_key.f8
_mock_key_f9 = mock_key.f9

mock_keycode = MagicMock()
mock_keycode.from_char = lambda c: types.SimpleNamespace(char=c)

mock_keyboard_module = MagicMock()
mock_keyboard_module.Key = mock_key
mock_keyboard_module.KeyCode = mock_keycode
mock_keyboard_module.Listener = MagicMock()

sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = mock_keyboard_module

# ── Mock PyQt6 for autoclicker.py import ─────────────────────────────
# QMainWindow/QDialog/QObject must be real classes (not MagicMock) so that
# AppWindow and KeyCaptureDialog are defined as proper classes whose
# @staticmethod / instance methods are accessible from tests.
_qt_widgets = MagicMock()
_qt_widgets.QMainWindow = type("QMainWindow", (), {})
_qt_widgets.QDialog = type("QDialog", (), {"DialogCode": MagicMock()})

_qt_core = MagicMock()
_qt_core.QObject = type("QObject", (), {})
_qt_core.pyqtSignal = lambda *a, **kw: MagicMock()
_qt_core.Qt.Key = MagicMock()
for _i in range(1, 13):
    setattr(_qt_core.Qt.Key, f"Key_F{_i}", 0x01000030 + _i - 1)

for mod, mock_obj in [
    ("PyQt6", MagicMock()),
    ("PyQt6.QtCore", _qt_core),
    ("PyQt6.QtGui", MagicMock()),
    ("PyQt6.QtWidgets", _qt_widgets),
]:
    sys.modules[mod] = mock_obj

# ── Import production modules (must follow mocks) ───────────────────
from autoclicker_evdev import (  # noqa: E402
    DualAutoClicker,
    MIN_INTERVAL,
    MAX_INTERVAL,
    DEFAULT_CLICKER1_INTERVAL,
    DEFAULT_CLICKER2_INTERVAL,
    DEFAULT_KEYPRESSER_INTERVAL,
)
from autoclicker import AppWindow  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────


def _make_evdev_obj() -> DualAutoClicker:
    """Create a DualAutoClicker without running __init__."""
    return object.__new__(DualAutoClicker)


def _make_special_key(name: str):
    """Create a SimpleNamespace mimicking pynput Key with .name."""
    return types.SimpleNamespace(name=name)


def _make_char_key(char: str):
    """Create a SimpleNamespace mimicking pynput KeyCode with .char."""
    return types.SimpleNamespace(char=char)


# ═════════════════════════════════════════════════════════════════════
#  Tests
# ═════════════════════════════════════════════════════════════════════


class TestValidateInterval(unittest.TestCase):
    """Call _validate_interval on both backends."""

    def setUp(self):
        self.evdev_obj = _make_evdev_obj()
        self.DEFAULT = DEFAULT_CLICKER1_INTERVAL

    # -- valid --

    def test_valid_interval(self):
        for val in (0.1, 1.0, 30.0):
            self.assertEqual(AppWindow._validate_interval(val, self.DEFAULT), val)
            self.assertEqual(self.evdev_obj._validate_interval(val, self.DEFAULT), val)

    def test_string_interval(self):
        self.assertEqual(AppWindow._validate_interval("0.5", self.DEFAULT), 0.5)
        self.assertEqual(self.evdev_obj._validate_interval("1", self.DEFAULT), 1.0)

    # -- boundary --

    def test_boundary_minimum(self):
        self.assertEqual(
            AppWindow._validate_interval(MIN_INTERVAL, self.DEFAULT), MIN_INTERVAL
        )
        self.assertEqual(
            self.evdev_obj._validate_interval(MIN_INTERVAL, self.DEFAULT), MIN_INTERVAL
        )

    def test_boundary_maximum(self):
        self.assertEqual(
            AppWindow._validate_interval(MAX_INTERVAL, self.DEFAULT), MAX_INTERVAL
        )
        self.assertEqual(
            self.evdev_obj._validate_interval(MAX_INTERVAL, self.DEFAULT), MAX_INTERVAL
        )

    # -- out of range --

    def test_below_minimum(self):
        self.assertEqual(
            AppWindow._validate_interval(0.001, self.DEFAULT), self.DEFAULT
        )
        self.assertEqual(
            self.evdev_obj._validate_interval(0.001, self.DEFAULT), self.DEFAULT
        )

    def test_above_maximum(self):
        self.assertEqual(
            AppWindow._validate_interval(100.0, self.DEFAULT), self.DEFAULT
        )
        self.assertEqual(
            self.evdev_obj._validate_interval(100.0, self.DEFAULT), self.DEFAULT
        )

    def test_negative_interval(self):
        self.assertEqual(AppWindow._validate_interval(-1.0, self.DEFAULT), self.DEFAULT)
        self.assertEqual(
            self.evdev_obj._validate_interval(-1.0, self.DEFAULT), self.DEFAULT
        )

    # -- invalid types --

    def test_invalid_string(self):
        self.assertEqual(
            AppWindow._validate_interval("not a number", self.DEFAULT), self.DEFAULT
        )
        self.assertEqual(
            self.evdev_obj._validate_interval("not a number", self.DEFAULT),
            self.DEFAULT,
        )

    def test_none_value(self):
        self.assertEqual(AppWindow._validate_interval(None, self.DEFAULT), self.DEFAULT)
        self.assertEqual(
            self.evdev_obj._validate_interval(None, self.DEFAULT), self.DEFAULT
        )


class TestKeyMapping(unittest.TestCase):
    """Call DualAutoClicker._tk_key_to_evdev on a real evdev instance."""

    def setUp(self):
        self.obj = _make_evdev_obj()
        from evdev import ecodes

        self.e = ecodes

    def test_special_keys(self):
        self.assertEqual(self.obj._tk_key_to_evdev("space"), self.e.KEY_SPACE)
        self.assertEqual(self.obj._tk_key_to_evdev("Return"), self.e.KEY_ENTER)
        self.assertEqual(self.obj._tk_key_to_evdev("Tab"), self.e.KEY_TAB)
        self.assertEqual(self.obj._tk_key_to_evdev("Escape"), self.e.KEY_ESC)

    def test_arrow_keys(self):
        self.assertEqual(self.obj._tk_key_to_evdev("Up"), self.e.KEY_UP)
        self.assertEqual(self.obj._tk_key_to_evdev("Down"), self.e.KEY_DOWN)
        self.assertEqual(self.obj._tk_key_to_evdev("Left"), self.e.KEY_LEFT)
        self.assertEqual(self.obj._tk_key_to_evdev("Right"), self.e.KEY_RIGHT)

    def test_function_keys(self):
        self.assertEqual(self.obj._tk_key_to_evdev("F1"), self.e.KEY_F1)
        self.assertEqual(self.obj._tk_key_to_evdev("F6"), self.e.KEY_F6)
        self.assertEqual(self.obj._tk_key_to_evdev("F12"), self.e.KEY_F12)

    def test_letter_keys(self):
        self.assertEqual(self.obj._tk_key_to_evdev("a"), self.e.KEY_A)
        self.assertEqual(self.obj._tk_key_to_evdev("z"), self.e.KEY_Z)

    def test_number_keys(self):
        self.assertEqual(self.obj._tk_key_to_evdev("0"), self.e.KEY_0)
        self.assertEqual(self.obj._tk_key_to_evdev("1"), self.e.KEY_1)
        self.assertEqual(self.obj._tk_key_to_evdev("9"), self.e.KEY_9)

    def test_modifier_keys(self):
        self.assertEqual(self.obj._tk_key_to_evdev("Shift_L"), self.e.KEY_LEFTSHIFT)
        self.assertEqual(self.obj._tk_key_to_evdev("Control_L"), self.e.KEY_LEFTCTRL)
        self.assertEqual(self.obj._tk_key_to_evdev("Alt_L"), self.e.KEY_LEFTALT)

    def test_unknown_key_returns_none(self):
        self.assertIsNone(self.obj._tk_key_to_evdev("unknown"))
        self.assertIsNone(self.obj._tk_key_to_evdev(""))


class TestKeySerialization(unittest.TestCase):
    """Call _serialize_key / _deserialize_key on both backends."""

    def setUp(self):
        self.evdev_obj = _make_evdev_obj()

    # -- serialize --

    def test_serialize_special_key_pyqt(self):
        key = _make_special_key("f6")
        result = AppWindow._serialize_key(key)
        self.assertEqual(result, {"type": "special", "name": "f6"})

    def test_serialize_special_key_evdev(self):
        key = _make_special_key("f7")
        result = self.evdev_obj._serialize_key(key)
        self.assertEqual(result, {"type": "special", "name": "f7"})

    def test_serialize_char_key_pyqt(self):
        key = _make_char_key("a")
        result = AppWindow._serialize_key(key)
        self.assertEqual(result, {"type": "char", "char": "a"})

    def test_serialize_char_key_evdev(self):
        key = _make_char_key("z")
        result = self.evdev_obj._serialize_key(key)
        self.assertEqual(result, {"type": "char", "char": "z"})

    def test_serialize_fallback_pyqt(self):
        key = object()  # no .name, no .char
        result = AppWindow._serialize_key(key)
        self.assertEqual(result, {"type": "special", "name": "f6"})

    def test_serialize_fallback_evdev(self):
        key = object()
        result = self.evdev_obj._serialize_key(key)
        self.assertEqual(result, {"type": "special", "name": "f6"})

    # -- deserialize --

    def test_deserialize_special_key_pyqt(self):
        result = AppWindow._deserialize_key({"type": "special", "name": "f7"})
        self.assertEqual(result, mock_key.f7)

    def test_deserialize_special_key_evdev(self):
        result = self.evdev_obj._deserialize_key({"type": "special", "name": "f7"})
        self.assertEqual(result, mock_key.f7)

    def test_deserialize_char_key_pyqt(self):
        result = AppWindow._deserialize_key({"type": "char", "char": "a"})
        self.assertEqual(result.char, "a")

    def test_deserialize_char_key_evdev(self):
        result = self.evdev_obj._deserialize_key({"type": "char", "char": "x"})
        self.assertEqual(result.char, "x")

    def test_deserialize_invalid_type_pyqt(self):
        for bad in ("not a dict", None, 123, []):
            result = AppWindow._deserialize_key(bad)
            self.assertEqual(result, mock_key.f6)

    def test_deserialize_invalid_type_evdev(self):
        for bad in ("not a dict", None, 123, []):
            result = self.evdev_obj._deserialize_key(bad)
            self.assertEqual(result, mock_key.f6)

    def test_deserialize_missing_char_pyqt(self):
        result = AppWindow._deserialize_key({"type": "char"})
        self.assertEqual(result, mock_key.f6)

    def test_deserialize_missing_char_evdev(self):
        result = self.evdev_obj._deserialize_key({"type": "char"})
        self.assertEqual(result, mock_key.f6)

    def test_deserialize_invalid_char_pyqt(self):
        result = AppWindow._deserialize_key({"type": "char", "char": "ab"})
        self.assertEqual(result, mock_key.f6)

    def test_deserialize_unknown_type_pyqt(self):
        result = AppWindow._deserialize_key({"type": "unknown", "name": "test"})
        self.assertEqual(result, mock_key.f6)

    def test_deserialize_unknown_type_evdev(self):
        result = self.evdev_obj._deserialize_key({"type": "unknown", "name": "test"})
        self.assertEqual(result, mock_key.f6)

    def test_deserialize_non_string_type_field(self):
        result = AppWindow._deserialize_key({"type": 42})
        self.assertEqual(result, mock_key.f6)

    def test_deserialize_non_string_name_field(self):
        result = AppWindow._deserialize_key({"type": "special", "name": 999})
        self.assertEqual(result, mock_key.f6)

    # -- round-trip --

    def test_roundtrip_special_pyqt(self):
        key = _make_special_key("f8")
        serialized = AppWindow._serialize_key(key)
        deserialized = AppWindow._deserialize_key(serialized)
        self.assertEqual(deserialized, mock_key.f8)

    def test_roundtrip_char_pyqt(self):
        key = _make_char_key("m")
        serialized = AppWindow._serialize_key(key)
        deserialized = AppWindow._deserialize_key(serialized)
        self.assertEqual(deserialized.char, "m")

    def test_roundtrip_special_evdev(self):
        key = _make_special_key("f9")
        serialized = self.evdev_obj._serialize_key(key)
        deserialized = self.evdev_obj._deserialize_key(serialized)
        self.assertEqual(deserialized, mock_key.f9)


class TestKeyDisplayName(unittest.TestCase):
    """Call get_key_display_name on both backends."""

    def setUp(self):
        self.evdev_obj = _make_evdev_obj()

    def test_function_key_display_pyqt(self):
        self.assertEqual(AppWindow.get_key_display_name(_make_special_key("f6")), "F6")
        self.assertEqual(
            AppWindow.get_key_display_name(_make_special_key("f12")), "F12"
        )

    def test_function_key_display_evdev(self):
        self.assertEqual(
            self.evdev_obj.get_key_display_name(_make_special_key("f6")), "F6"
        )
        self.assertEqual(
            self.evdev_obj.get_key_display_name(_make_special_key("f12")), "F12"
        )

    def test_special_key_display_pyqt(self):
        self.assertEqual(
            AppWindow.get_key_display_name(_make_special_key("shift")), "Shift"
        )
        self.assertEqual(
            AppWindow.get_key_display_name(_make_special_key("ctrl")), "Ctrl"
        )

    def test_special_key_display_evdev(self):
        self.assertEqual(
            self.evdev_obj.get_key_display_name(_make_special_key("shift")), "Shift"
        )
        self.assertEqual(
            self.evdev_obj.get_key_display_name(_make_special_key("ctrl")), "Ctrl"
        )

    def test_char_key_display_pyqt(self):
        self.assertEqual(AppWindow.get_key_display_name(_make_char_key("a")), "A")
        self.assertEqual(AppWindow.get_key_display_name(_make_char_key("z")), "Z")

    def test_char_key_display_evdev(self):
        self.assertEqual(self.evdev_obj.get_key_display_name(_make_char_key("a")), "A")
        self.assertEqual(self.evdev_obj.get_key_display_name(_make_char_key("z")), "Z")

    def test_fallback_display_pyqt(self):
        key = object()
        result = AppWindow.get_key_display_name(key)
        self.assertIsInstance(result, str)

    def test_fallback_display_evdev(self):
        key = object()
        result = self.evdev_obj.get_key_display_name(key)
        self.assertIsInstance(result, str)


class TestVersionComparison(unittest.TestCase):
    """Call AppWindow._version_newer (static)."""

    def test_basic_comparison(self):
        self.assertTrue(AppWindow._version_newer("1.1.0", "1.0.0"))
        self.assertTrue(AppWindow._version_newer("2.0.0", "1.9.9"))
        self.assertTrue(AppWindow._version_newer("1.0.1", "1.0.0"))
        self.assertFalse(AppWindow._version_newer("1.0.0", "1.0.0"))
        self.assertFalse(AppWindow._version_newer("1.0.0", "1.0.1"))

    def test_pre_release_versions(self):
        self.assertTrue(AppWindow._version_newer("1.4.0", "1.4.0-beta"))
        self.assertTrue(AppWindow._version_newer("1.4.0", "1.4.0-alpha"))
        self.assertTrue(AppWindow._version_newer("1.4.0", "1.4.0-rc1"))
        self.assertFalse(AppWindow._version_newer("1.4.0-beta", "1.4.0"))
        self.assertTrue(AppWindow._version_newer("1.4.0-beta2", "1.4.0-beta1"))

    def test_v_prefix(self):
        self.assertTrue(AppWindow._version_newer("v1.1.0", "v1.0.0"))
        self.assertTrue(AppWindow._version_newer("v1.1.0", "1.0.0"))
        self.assertTrue(AppWindow._version_newer("1.1.0", "v1.0.0"))

    def test_two_part_versions(self):
        self.assertTrue(AppWindow._version_newer("1.1", "1.0"))
        self.assertFalse(AppWindow._version_newer("1.1.0", "1.1"))
        self.assertFalse(AppWindow._version_newer("1.0", "1.0.0"))

    def test_invalid_versions(self):
        self.assertFalse(AppWindow._version_newer(None, "1.0.0"))
        self.assertFalse(AppWindow._version_newer("", "1.0.0"))
        self.assertFalse(AppWindow._version_newer("invalid", "1.0.0"))
        self.assertTrue(AppWindow._version_newer("1.0.0", None))
        self.assertTrue(AppWindow._version_newer("1.0.0", ""))

    def test_edge_cases(self):
        self.assertTrue(AppWindow._version_newer("100.0.0", "99.99.99"))
        self.assertTrue(AppWindow._version_newer("0.0.1", "0.0.0"))
        self.assertFalse(AppWindow._version_newer("1.0.0-beta", "1.0.0-beta"))


class TestComputeGitBlobSha(unittest.TestCase):
    """Call AppWindow._compute_git_blob_sha with known data."""

    def setUp(self):
        self.obj = object.__new__(AppWindow)

    def test_known_blob_sha(self):
        # "git hash-object" for "hello\n" = ce013625030ba8dba906f756967f9e9ca394464a
        content = b"hello\n"
        expected = hashlib.sha1(b"blob 6\0hello\n").hexdigest()
        result = self.obj._compute_git_blob_sha(content)
        self.assertEqual(result, expected)
        self.assertEqual(result, "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_empty_content(self):
        content = b""
        expected = hashlib.sha1(b"blob 0\0").hexdigest()
        result = self.obj._compute_git_blob_sha(content)
        self.assertEqual(result, expected)

    def test_binary_content(self):
        content = b"\x00\x01\x02\xff"
        expected = hashlib.sha1(b"blob 4\0\x00\x01\x02\xff").hexdigest()
        result = self.obj._compute_git_blob_sha(content)
        self.assertEqual(result, expected)


class TestConfigPersistence(unittest.TestCase):
    """Patch config_path, then call save_config / load_config on evdev."""

    def _make_configured_obj(self, config_path: Path) -> DualAutoClicker:
        """Build a minimally-initialized DualAutoClicker for config tests."""
        obj = _make_evdev_obj()
        obj.config_path = config_path

        # Set all state attrs that save_config / load_config touch
        obj.clicker1_interval = 0.15
        obj.clicker2_interval = 0.55
        obj.keypresser_interval = 0.25
        obj.clicker1_hotkey = mock_key.f6
        obj.clicker1_hotkey_display = "F6"
        obj.clicker2_hotkey = mock_key.f7
        obj.clicker2_hotkey_display = "F7"
        obj.keypresser_hotkey = mock_key.f8
        obj.keypresser_hotkey_display = "F8"
        obj.keypresser_target_key = 57  # KEY_SPACE
        obj.keypresser_target_key_display = "Space"
        obj.emergency_stop_hotkey = mock_key.f9
        obj.emergency_stop_hotkey_display = "F9"
        return obj

    def test_save_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "autoclicker" / "config.json"
            obj = self._make_configured_obj(cfg)
            obj.save_config()
            self.assertTrue(cfg.exists())

    def test_roundtrip_intervals(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "autoclicker" / "config.json"
            obj = self._make_configured_obj(cfg)
            obj.save_config()

            # Create a fresh object and load
            obj2 = self._make_configured_obj(cfg)
            obj2.clicker1_interval = DEFAULT_CLICKER1_INTERVAL
            obj2.clicker2_interval = DEFAULT_CLICKER2_INTERVAL
            obj2.keypresser_interval = DEFAULT_KEYPRESSER_INTERVAL
            obj2.load_config()

            self.assertAlmostEqual(obj2.clicker1_interval, 0.15)
            self.assertAlmostEqual(obj2.clicker2_interval, 0.55)
            self.assertAlmostEqual(obj2.keypresser_interval, 0.25)

    def test_load_missing_file_keeps_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "nonexistent" / "config.json"
            obj = self._make_configured_obj(cfg)
            obj.clicker1_interval = DEFAULT_CLICKER1_INTERVAL
            obj.load_config()  # should not crash
            self.assertEqual(obj.clicker1_interval, DEFAULT_CLICKER1_INTERVAL)

    def test_load_corrupt_json_keeps_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.json"
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text("not valid json {{{")
            obj = self._make_configured_obj(cfg)
            obj.clicker1_interval = DEFAULT_CLICKER1_INTERVAL
            obj.load_config()  # should not crash
            self.assertEqual(obj.clicker1_interval, DEFAULT_CLICKER1_INTERVAL)

    def test_save_merges_with_existing(self):
        """save_config should preserve keys from the other backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "autoclicker" / "config.json"
            cfg.parent.mkdir(parents=True, exist_ok=True)
            # Pre-existing config from the PyQt6 side
            cfg.write_text(json.dumps({"dark_mode": True, "extra_key": 42}))

            obj = self._make_configured_obj(cfg)
            obj.save_config()

            data = json.loads(cfg.read_text())
            # Our values written
            self.assertAlmostEqual(data["clicker1_interval"], 0.15)
            # Pre-existing keys preserved
            self.assertTrue(data.get("dark_mode"))
            self.assertEqual(data.get("extra_key"), 42)


class TestHotkeyRateLimiting(unittest.TestCase):
    """Call DualAutoClicker.on_hotkey_press and verify rate limiting."""

    def _make_hotkey_obj(self):
        obj = _make_evdev_obj()
        obj.last_hotkey_time = {}
        obj.hotkey_timing_lock = threading.Lock()
        obj.hotkey_cooldown = 0.2
        obj.clicker1_hotkey = mock_key.f6
        obj.clicker2_hotkey = mock_key.f7
        obj.keypresser_hotkey = mock_key.f8
        obj.emergency_stop_hotkey = mock_key.f9
        # Patch toggle methods so we can count calls
        obj.toggle_clicker1 = MagicMock()
        obj.toggle_clicker2 = MagicMock()
        obj.toggle_keypresser = MagicMock()
        obj.emergency_stop_all = MagicMock()
        return obj

    def test_first_press_accepted(self):
        obj = self._make_hotkey_obj()
        obj.on_hotkey_press(mock_key.f6)
        obj.toggle_clicker1.assert_called_once()

    def test_rapid_press_rejected(self):
        obj = self._make_hotkey_obj()
        obj.on_hotkey_press(mock_key.f6)
        obj.on_hotkey_press(mock_key.f6)  # too fast
        self.assertEqual(obj.toggle_clicker1.call_count, 1)

    def test_press_after_cooldown_accepted(self):
        obj = self._make_hotkey_obj()
        obj.on_hotkey_press(mock_key.f6)
        # Manipulate the stored time to simulate cooldown expiring
        key_str = str(mock_key.f6)
        with obj.hotkey_timing_lock:
            obj.last_hotkey_time[key_str] -= 0.3
        obj.on_hotkey_press(mock_key.f6)
        self.assertEqual(obj.toggle_clicker1.call_count, 2)

    def test_different_keys_independent(self):
        obj = self._make_hotkey_obj()
        obj.on_hotkey_press(mock_key.f6)
        obj.on_hotkey_press(mock_key.f7)
        obj.toggle_clicker1.assert_called_once()
        obj.toggle_clicker2.assert_called_once()

    def test_emergency_stop_has_priority(self):
        obj = self._make_hotkey_obj()
        obj.on_hotkey_press(mock_key.f9)
        obj.emergency_stop_all.assert_called_once()

    def test_keypresser_hotkey(self):
        obj = self._make_hotkey_obj()
        obj.on_hotkey_press(mock_key.f8)
        obj.toggle_keypresser.assert_called_once()


class TestConstants(unittest.TestCase):
    """Test module constants from autoclicker_evdev."""

    def test_interval_bounds(self):
        self.assertGreater(MIN_INTERVAL, 0)
        self.assertLess(MIN_INTERVAL, 1)
        self.assertGreater(MAX_INTERVAL, MIN_INTERVAL)
        self.assertLessEqual(MAX_INTERVAL, 3600)

    def test_default_intervals(self):
        self.assertGreaterEqual(DEFAULT_CLICKER1_INTERVAL, MIN_INTERVAL)
        self.assertLessEqual(DEFAULT_CLICKER1_INTERVAL, MAX_INTERVAL)
        self.assertGreaterEqual(DEFAULT_CLICKER2_INTERVAL, MIN_INTERVAL)
        self.assertLessEqual(DEFAULT_CLICKER2_INTERVAL, MAX_INTERVAL)
        self.assertGreaterEqual(DEFAULT_KEYPRESSER_INTERVAL, MIN_INTERVAL)
        self.assertLessEqual(DEFAULT_KEYPRESSER_INTERVAL, MAX_INTERVAL)


class TestThreadSafety(unittest.TestCase):
    """Tests for toggle mutual exclusion and emergency stop using evdev backend."""

    def _make_clicker(self):
        """Create a minimally-initialized DualAutoClicker for toggle tests."""
        obj = object.__new__(DualAutoClicker)
        obj.clicker1_lock = threading.Lock()
        obj.clicker2_lock = threading.Lock()
        obj.keypresser_lock = threading.Lock()
        obj.clicker1_clicking = False
        obj.clicker2_clicking = False
        obj.keypresser_pressing = False
        obj.clicker1_interval = 0.1
        obj.clicker2_interval = 0.5
        obj.keypresser_interval = 0.1
        obj.clicker1_thread = None
        obj.clicker2_thread = None
        obj.keypresser_thread = None
        obj.clicker1_stop = threading.Event()
        obj.clicker1_stop.set()
        obj.clicker2_stop = threading.Event()
        obj.clicker2_stop.set()
        obj.keypresser_stop = threading.Event()
        obj.keypresser_stop.set()
        obj.keypresser_target_key = 57  # KEY_SPACE
        obj.virtual_mouse = None
        obj.virtual_keyboard = None
        # Mock UI elements
        obj.status1_var = MagicMock()
        obj.status1_label = MagicMock()
        obj.status2_var = MagicMock()
        obj.status2_label = MagicMock()
        obj.keypresser_status_var = MagicMock()
        obj.keypresser_status_label = MagicMock()
        obj.window = MagicMock()
        return obj

    def test_start_clicker1_sets_flag(self):
        obj = self._make_clicker()
        # Mock perform_click to be a no-op so the thread doesn't actually click
        obj.perform_click = MagicMock()
        obj.start_clicker1()
        self.assertTrue(obj.clicker1_clicking)
        self.assertIsNotNone(obj.clicker1_thread)
        # Clean up
        obj.stop_clicker1()
        if obj.clicker1_thread:
            obj.clicker1_thread.join(timeout=2)

    def test_stop_clicker1_clears_flag(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.start_clicker1()
        obj.stop_clicker1()
        self.assertFalse(obj.clicker1_clicking)

    def test_toggle_clicker1_starts_when_idle(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.toggle_clicker1()
        self.assertTrue(obj.clicker1_clicking)
        obj.stop_clicker1()
        for t in [
            obj.clicker1_thread,
            obj.clicker2_thread,
            getattr(obj, "keypresser_thread", None),
        ]:
            if t and t.is_alive():
                t.join(timeout=2)

    def test_toggle_clicker1_stops_when_active(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.start_clicker1()
        obj.toggle_clicker1()
        self.assertFalse(obj.clicker1_clicking)

    def test_mutual_exclusion_clicker1_stops_clicker2(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.start_clicker2()
        self.assertTrue(obj.clicker2_clicking)
        obj.toggle_clicker1()
        self.assertTrue(obj.clicker1_clicking)
        self.assertFalse(obj.clicker2_clicking)
        obj.stop_clicker1()
        for t in [
            obj.clicker1_thread,
            obj.clicker2_thread,
            getattr(obj, "keypresser_thread", None),
        ]:
            if t and t.is_alive():
                t.join(timeout=2)

    def test_mutual_exclusion_clicker2_stops_clicker1(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.start_clicker1()
        self.assertTrue(obj.clicker1_clicking)
        obj.toggle_clicker2()
        self.assertTrue(obj.clicker2_clicking)
        self.assertFalse(obj.clicker1_clicking)
        obj.stop_clicker2()
        for t in [
            obj.clicker1_thread,
            obj.clicker2_thread,
            getattr(obj, "keypresser_thread", None),
        ]:
            if t and t.is_alive():
                t.join(timeout=2)

    def test_emergency_stop_all(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.perform_keypress = MagicMock()
        obj.start_clicker1()
        obj.start_keypresser()
        self.assertTrue(obj.clicker1_clicking)
        self.assertTrue(obj.keypresser_pressing)
        obj.emergency_stop_all()
        self.assertFalse(obj.clicker1_clicking)
        self.assertFalse(obj.clicker2_clicking)
        self.assertFalse(obj.keypresser_pressing)
        for t in [
            obj.clicker1_thread,
            obj.clicker2_thread,
            getattr(obj, "keypresser_thread", None),
        ]:
            if t and t.is_alive():
                t.join(timeout=2)

    def test_keypresser_independent_of_clickers(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.perform_keypress = MagicMock()
        obj.start_clicker1()
        obj.start_keypresser()
        self.assertTrue(obj.clicker1_clicking)
        self.assertTrue(obj.keypresser_pressing)
        obj.stop_clicker1()
        self.assertFalse(obj.clicker1_clicking)
        self.assertTrue(obj.keypresser_pressing)
        obj.stop_keypresser()
        for t in [
            obj.clicker1_thread,
            obj.clicker2_thread,
            getattr(obj, "keypresser_thread", None),
        ]:
            if t and t.is_alive():
                t.join(timeout=2)


class TestVersionNewerPyQt(unittest.TestCase):
    """Additional _version_newer tests calling production code from AppWindow."""

    def test_tag_format_validation(self):
        """Verify the tag regex used in _apply_update."""
        import re

        pattern = r"^v?\d+\.\d+(\.\d+)?(-[\w.]+)?$"
        self.assertIsNotNone(re.match(pattern, "v1.11"))
        self.assertIsNotNone(re.match(pattern, "1.11.0"))
        self.assertIsNotNone(re.match(pattern, "v2.0.0-beta1"))
        self.assertIsNone(re.match(pattern, "../../../evil"))
        self.assertIsNone(re.match(pattern, "main"))
        self.assertIsNone(re.match(pattern, ""))


# ═════════════════════════════════════════════════════════════════════
#  New tests added by audit
# ═════════════════════════════════════════════════════════════════════


class TestVerifyFileIntegrity(unittest.TestCase):
    """Test _compute_git_blob_sha and _verify_file_against_github."""

    def setUp(self):
        self.obj = object.__new__(AppWindow)

    def test_verify_matching_sha_passes(self):
        content = b"hello world\n"
        expected_sha = self.obj._compute_git_blob_sha(content)
        # Mock urlopen to return the expected SHA
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({"sha": expected_sha}).encode()

        import urllib.request

        with unittest.mock.patch.object(
            urllib.request, "urlopen", return_value=mock_response
        ):
            # Should not raise
            self.obj._verify_file_against_github(
                "v1.0", "test.py", content, {"User-Agent": "test"}
            )

    def test_verify_mismatching_sha_raises(self):
        content = b"hello world\n"
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({"sha": "0000bad"}).encode()

        import urllib.request

        with unittest.mock.patch.object(
            urllib.request, "urlopen", return_value=mock_response
        ):
            with self.assertRaises(RuntimeError):
                self.obj._verify_file_against_github(
                    "v1.0", "test.py", content, {"User-Agent": "test"}
                )

    def test_verify_empty_sha_raises(self):
        content = b"data"
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({"sha": ""}).encode()

        import urllib.request

        with unittest.mock.patch.object(
            urllib.request, "urlopen", return_value=mock_response
        ):
            with self.assertRaises(RuntimeError):
                self.obj._verify_file_against_github(
                    "v1.0", "test.py", content, {"User-Agent": "test"}
                )


class TestConfigPersistencePyQt(unittest.TestCase):
    """Test PyQt6 AppWindow _save_config / _load_config."""

    def _make_pyqt_obj(self, config_path: Path):
        obj = object.__new__(AppWindow)
        # Minimal state for config save/load
        obj.clicker1_interval = 0.2
        obj.clicker2_interval = 0.6
        obj.clicker1_hotkey = mock_key.f6
        obj.clicker1_hotkey_display = "F6"
        obj.clicker2_hotkey = mock_key.f7
        obj.clicker2_hotkey_display = "F7"
        obj.keypresser_interval = 0.3
        obj.keypresser_hotkey = mock_key.f8
        obj.keypresser_hotkey_display = "F8"
        obj.keypresser_target_key = mock_key.space
        obj.keypresser_target_key_display = "Space"
        obj.emergency_stop_hotkey = mock_key.f9
        obj.emergency_stop_hotkey_display = "F9"
        obj.auto_check_updates = False
        # Mock geometry
        geo = MagicMock()
        geo.width.return_value = 600
        geo.height.return_value = 800
        geo.x.return_value = 100
        geo.y.return_value = 50
        obj.geometry = MagicMock(return_value=geo)
        # Patch _config_path
        type(obj)._config_path = property(lambda self: config_path)
        return obj

    def test_save_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "autoclicker" / "config.json"
            obj = self._make_pyqt_obj(cfg)
            obj._save_config()
            self.assertTrue(cfg.exists())

    def test_roundtrip_intervals(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "autoclicker" / "config.json"
            obj = self._make_pyqt_obj(cfg)
            obj._save_config()

            obj2 = self._make_pyqt_obj(cfg)
            obj2.clicker1_interval = 0.1
            obj2.clicker2_interval = 0.5
            obj2.keypresser_interval = 0.1
            obj2.auto_check_updates = True
            # Mock resize/move for geometry loading
            obj2.resize = MagicMock()
            obj2.move = MagicMock()
            obj2._load_config()

            self.assertAlmostEqual(obj2.clicker1_interval, 0.2)
            self.assertAlmostEqual(obj2.clicker2_interval, 0.6)
            self.assertAlmostEqual(obj2.keypresser_interval, 0.3)
            self.assertFalse(obj2.auto_check_updates)

    def test_roundtrip_hotkeys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "autoclicker" / "config.json"
            obj = self._make_pyqt_obj(cfg)
            obj._save_config()

            obj2 = self._make_pyqt_obj(cfg)
            obj2.resize = MagicMock()
            obj2.move = MagicMock()
            obj2._load_config()

            self.assertEqual(obj2.clicker1_hotkey_display, "F6")
            self.assertEqual(obj2.clicker2_hotkey_display, "F7")
            self.assertEqual(obj2.emergency_stop_hotkey_display, "F9")

    def test_load_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "nope" / "config.json"
            obj = self._make_pyqt_obj(cfg)
            obj._load_config()  # should not crash
            self.assertAlmostEqual(obj.clicker1_interval, 0.2)

    def test_load_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.json"
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text("{{{not json")
            obj = self._make_pyqt_obj(cfg)
            obj._load_config()  # should not crash

    def test_geometry_string_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.json"
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(json.dumps({"window_geometry": "800x600+100+200"}))
            obj = self._make_pyqt_obj(cfg)
            obj.resize = MagicMock()
            obj.move = MagicMock()
            obj._load_config()
            obj.resize.assert_called_with(800, 600)
            obj.move.assert_called_with(100, 200)

    def test_geometry_dict_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.json"
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(
                json.dumps({"window_geometry": {"w": 700, "h": 500, "x": 50, "y": 25}})
            )
            obj = self._make_pyqt_obj(cfg)
            obj.resize = MagicMock()
            obj.move = MagicMock()
            obj._load_config()
            obj.resize.assert_called_with(700, 500)
            obj.move.assert_called_with(50, 25)


class TestHotkeyRateLimitingPyQt(unittest.TestCase):
    """Test AppWindow.on_hotkey_press rate limiting and dispatch."""

    def _make_hotkey_obj(self):
        obj = object.__new__(AppWindow)
        obj.last_hotkey_time = {}
        obj.hotkey_timing_lock = threading.Lock()
        obj.hotkey_cooldown = 0.2
        obj.clicker1_hotkey = mock_key.f6
        obj.clicker2_hotkey = mock_key.f7
        obj.keypresser_hotkey = mock_key.f8
        obj.emergency_stop_hotkey = mock_key.f9
        obj.toggle_clicker1 = MagicMock()
        obj.toggle_clicker2 = MagicMock()
        obj.toggle_keypresser = MagicMock()
        obj.emergency_stop_all = MagicMock()
        return obj

    def test_first_press_accepted(self):
        obj = self._make_hotkey_obj()
        obj.on_hotkey_press(mock_key.f6)
        obj.toggle_clicker1.assert_called_once()

    def test_rapid_press_rejected(self):
        obj = self._make_hotkey_obj()
        obj.on_hotkey_press(mock_key.f6)
        obj.on_hotkey_press(mock_key.f6)
        self.assertEqual(obj.toggle_clicker1.call_count, 1)

    def test_emergency_stop(self):
        obj = self._make_hotkey_obj()
        obj.on_hotkey_press(mock_key.f9)
        obj.emergency_stop_all.assert_called_once()

    def test_all_hotkeys_dispatch(self):
        obj = self._make_hotkey_obj()
        obj.on_hotkey_press(mock_key.f6)
        obj.on_hotkey_press(mock_key.f7)
        obj.on_hotkey_press(mock_key.f8)
        obj.toggle_clicker1.assert_called_once()
        obj.toggle_clicker2.assert_called_once()
        obj.toggle_keypresser.assert_called_once()


class TestThreadSafetyPyQt(unittest.TestCase):
    """Test toggle/start/stop/mutual-exclusion for PyQt6 AppWindow."""

    def _make_clicker(self):
        obj = object.__new__(AppWindow)
        obj.clicker1_lock = threading.Lock()
        obj.clicker2_lock = threading.Lock()
        obj.keypresser_lock = threading.Lock()
        obj.clicker1_clicking = False
        obj.clicker2_clicking = False
        obj.keypresser_pressing = False
        obj.clicker1_interval = 0.1
        obj.clicker2_interval = 0.5
        obj.keypresser_interval = 0.1
        obj.clicker1_thread = None
        obj.clicker2_thread = None
        obj.keypresser_thread = None
        obj.clicker1_stop = threading.Event()
        obj.clicker1_stop.set()
        obj.clicker2_stop = threading.Event()
        obj.clicker2_stop.set()
        obj.keypresser_stop = threading.Event()
        obj.keypresser_stop.set()
        obj.keypresser_target_key = mock_key.space
        obj.mouse_controller = MagicMock()
        obj.keyboard_controller = MagicMock()
        # Mock UI
        obj._status1_label = MagicMock()
        obj._status2_label = MagicMock()
        obj._kp_status_label = MagicMock()
        obj._ui_updater = MagicMock()
        obj._ui_updater.requested = MagicMock()
        return obj

    def test_start_clicker1(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.start_clicker1()
        self.assertTrue(obj.clicker1_clicking)
        obj.stop_clicker1()
        if obj.clicker1_thread:
            obj.clicker1_thread.join(timeout=1)

    def test_stop_clicker1(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.start_clicker1()
        obj.stop_clicker1()
        self.assertFalse(obj.clicker1_clicking)
        if obj.clicker1_thread:
            obj.clicker1_thread.join(timeout=1)

    def test_toggle_starts_when_idle(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.toggle_clicker1()
        self.assertTrue(obj.clicker1_clicking)
        obj.stop_clicker1()
        if obj.clicker1_thread:
            obj.clicker1_thread.join(timeout=1)

    def test_toggle_stops_when_active(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.start_clicker1()
        obj.toggle_clicker1()
        self.assertFalse(obj.clicker1_clicking)
        if obj.clicker1_thread:
            obj.clicker1_thread.join(timeout=1)

    def test_mutual_exclusion(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.start_clicker2()
        self.assertTrue(obj.clicker2_clicking)
        obj.toggle_clicker1()
        self.assertTrue(obj.clicker1_clicking)
        self.assertFalse(obj.clicker2_clicking)
        obj.stop_clicker1()
        if obj.clicker1_thread:
            obj.clicker1_thread.join(timeout=1)
        if obj.clicker2_thread:
            obj.clicker2_thread.join(timeout=1)

    def test_emergency_stop_all(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.perform_keypress = MagicMock()
        obj.start_clicker1()
        obj.start_keypresser()
        obj.emergency_stop_all()
        self.assertFalse(obj.clicker1_clicking)
        self.assertFalse(obj.clicker2_clicking)
        self.assertFalse(obj.keypresser_pressing)
        for t in [obj.clicker1_thread, obj.keypresser_thread]:
            if t:
                t.join(timeout=1)

    def test_keypresser_independent(self):
        obj = self._make_clicker()
        obj.perform_click = MagicMock()
        obj.perform_keypress = MagicMock()
        obj.start_clicker1()
        obj.start_keypresser()
        self.assertTrue(obj.clicker1_clicking)
        self.assertTrue(obj.keypresser_pressing)
        obj.stop_clicker1()
        self.assertTrue(obj.keypresser_pressing)
        obj.stop_keypresser()
        for t in [obj.clicker1_thread, obj.keypresser_thread]:
            if t:
                t.join(timeout=1)


class TestActionLoopError(unittest.TestCase):
    """Test that action_loop from core handles errors gracefully."""

    def test_action_loop_error_calls_on_error(self):
        from autoclicker_core import action_loop as _action_loop

        stop = threading.Event()
        error_caught = {}

        def on_error(e):
            error_caught["exc"] = e
            stop.set()

        action = MagicMock(side_effect=RuntimeError("no uinput"))
        _action_loop(stop, lambda: 0.01, action, on_error)
        self.assertIn("exc", error_caught)
        self.assertIsInstance(error_caught["exc"], RuntimeError)

    def test_action_loop_stops_on_event(self):
        from autoclicker_core import action_loop as _action_loop

        stop = threading.Event()
        call_count = {"n": 0}

        def action():
            call_count["n"] += 1
            if call_count["n"] >= 3:
                stop.set()

        _action_loop(stop, lambda: 0.001, action, lambda e: None)
        self.assertGreaterEqual(call_count["n"], 3)


class TestConfigRoundtripHotkeysEvdev(unittest.TestCase):
    """Test that evdev config round-trips hotkey values (not just intervals)."""

    def _make_configured_obj(self, config_path: Path) -> DualAutoClicker:
        obj = _make_evdev_obj()
        obj.config_path = config_path
        obj.clicker1_interval = 0.15
        obj.clicker2_interval = 0.55
        obj.keypresser_interval = 0.25
        obj.clicker1_hotkey = mock_key.f6
        obj.clicker1_hotkey_display = "F6"
        obj.clicker2_hotkey = mock_key.f7
        obj.clicker2_hotkey_display = "F7"
        obj.keypresser_hotkey = mock_key.f8
        obj.keypresser_hotkey_display = "F8"
        obj.keypresser_target_key = 57
        obj.keypresser_target_key_display = "Space"
        obj.emergency_stop_hotkey = mock_key.f9
        obj.emergency_stop_hotkey_display = "F9"
        return obj

    def test_roundtrip_hotkey_displays(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "autoclicker" / "config.json"
            obj = self._make_configured_obj(cfg)
            obj.save_config()

            obj2 = self._make_configured_obj(cfg)
            obj2.clicker1_hotkey_display = "?"
            obj2.emergency_stop_hotkey_display = "?"
            obj2.load_config()

            self.assertEqual(obj2.clicker1_hotkey_display, "F6")
            self.assertEqual(obj2.emergency_stop_hotkey_display, "F9")

    def test_invalid_target_key_uses_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.json"
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(json.dumps({"keypresser_target_key": 999}))
            obj = self._make_configured_obj(cfg)
            obj.keypresser_target_key = 57  # default
            obj.load_config()
            self.assertEqual(obj.keypresser_target_key, 57)  # stayed default


class TestAutoclickerCore(unittest.TestCase):
    """Test autoclicker_core functions directly (not through backend wrappers)."""

    def test_validate_interval_direct(self):
        from autoclicker_core import validate_interval, MIN_INTERVAL, MAX_INTERVAL

        self.assertEqual(validate_interval(0.5, 0.1), 0.5)
        self.assertEqual(validate_interval(None, 0.1), 0.1)
        self.assertEqual(validate_interval(-1, 0.1), 0.1)
        self.assertEqual(validate_interval(MIN_INTERVAL, 0.1), MIN_INTERVAL)
        self.assertEqual(validate_interval(MAX_INTERVAL, 0.1), MAX_INTERVAL)

    def test_serialize_key_direct(self):
        from autoclicker_core import serialize_key

        self.assertEqual(
            serialize_key(_make_special_key("f6")),
            {"type": "special", "name": "f6"},
        )
        self.assertEqual(
            serialize_key(_make_char_key("a")),
            {"type": "char", "char": "a"},
        )

    def test_deserialize_key_direct(self):
        from autoclicker_core import deserialize_key

        result = deserialize_key({"type": "special", "name": "f6"})
        self.assertEqual(result, mock_key.f6)
        result = deserialize_key({"type": "char", "char": "a"})
        self.assertEqual(result.char, "a")
        # Invalid inputs
        self.assertEqual(deserialize_key(None), mock_key.f6)
        self.assertEqual(deserialize_key({"type": "char", "char": "ab"}), mock_key.f6)

    def test_get_key_display_name_direct(self):
        from autoclicker_core import get_key_display_name

        self.assertEqual(get_key_display_name(_make_special_key("f6")), "F6")
        self.assertEqual(get_key_display_name(_make_char_key("a")), "A")


class TestSafeAfter(unittest.TestCase):
    """Test _safe_after edge cases for both backends."""

    def test_evdev_safe_after_destroyed_window(self):
        obj = _make_evdev_obj()
        obj.window = MagicMock()
        obj.window.winfo_exists.return_value = False
        # Should not raise
        obj._safe_after(0, lambda: None)

    def test_evdev_safe_after_tcl_error(self):
        import tkinter as tk

        obj = _make_evdev_obj()
        obj.window = MagicMock()
        obj.window.winfo_exists.return_value = True
        obj.window.after.side_effect = tk.TclError("destroyed")
        # Should not raise
        obj._safe_after(0, lambda: None)

    def test_evdev_safe_after_no_window(self):
        obj = _make_evdev_obj()
        obj.window = None
        # Should not raise
        obj._safe_after(0, lambda: None)

    def test_pyqt_safe_after_runtime_error(self):
        obj = object.__new__(AppWindow)
        obj._ui_updater = MagicMock()
        obj._ui_updater.requested = MagicMock()
        obj._ui_updater.requested.emit.side_effect = RuntimeError("deleted")
        # Should not raise
        obj._safe_after(0, lambda: None)


class TestPerformActionsEvdev(unittest.TestCase):
    """Test evdev perform_click / perform_keypress call sequences."""

    def test_perform_click_sequence(self):

        obj = _make_evdev_obj()
        obj.virtual_mouse = MagicMock()
        obj.perform_click()
        calls = obj.virtual_mouse.method_calls
        # Expect: write(EV_KEY, BTN_LEFT, 1), syn(), write(EV_KEY, BTN_LEFT, 0), syn()
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0][0], "write")
        self.assertEqual(calls[1][0], "syn")
        self.assertEqual(calls[2][0], "write")
        self.assertEqual(calls[3][0], "syn")
        # Key down (value=1) then key up (value=0)
        self.assertEqual(calls[0][1][2], 1)
        self.assertEqual(calls[2][1][2], 0)

    def test_perform_keypress_sequence(self):
        obj = _make_evdev_obj()
        obj.virtual_keyboard = MagicMock()
        obj.keypresser_target_key = 57  # KEY_SPACE
        obj.perform_keypress()
        calls = obj.virtual_keyboard.method_calls
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0][0], "write")
        self.assertEqual(calls[1][0], "syn")
        self.assertEqual(calls[2][0], "write")
        self.assertEqual(calls[3][0], "syn")
        self.assertEqual(calls[0][1][2], 1)
        self.assertEqual(calls[2][1][2], 0)


class TestApplyIntervalEvdev(unittest.TestCase):
    """Test DualAutoClicker._apply_interval with UI validation."""

    def _make_obj(self):
        obj = _make_evdev_obj()
        obj.clicker1_lock = threading.Lock()
        obj.clicker2_lock = threading.Lock()
        obj.keypresser_lock = threading.Lock()
        obj.clicker1_interval = 0.1
        obj.clicker2_interval = 0.5
        obj.keypresser_interval = 0.1
        obj.save_config = MagicMock()
        obj.window = MagicMock()
        return obj

    def test_valid_interval_applied(self):
        obj = self._make_obj()
        obj.interval1_var = MagicMock()
        obj.interval1_var.get.return_value = "0.25"
        with unittest.mock.patch("autoclicker_evdev.messagebox"):
            obj.apply_interval1()
        self.assertAlmostEqual(obj.clicker1_interval, 0.25)
        obj.save_config.assert_called_once()

    def test_invalid_interval_rejected(self):
        obj = self._make_obj()
        obj.interval1_var = MagicMock()
        obj.interval1_var.get.return_value = "not_a_number"
        with unittest.mock.patch("autoclicker_evdev.messagebox"):
            obj.apply_interval1()
        self.assertAlmostEqual(obj.clicker1_interval, 0.1)  # unchanged

    def test_below_min_rejected(self):
        obj = self._make_obj()
        obj.interval1_var = MagicMock()
        obj.interval1_var.get.return_value = "0.001"
        with unittest.mock.patch("autoclicker_evdev.messagebox"):
            obj.apply_interval1()
        self.assertAlmostEqual(obj.clicker1_interval, 0.1)  # unchanged


class TestDispatchHotkey(unittest.TestCase):
    """Test the shared dispatch_hotkey from autoclicker_core."""

    def test_dispatch_calls_matching_action(self):
        from autoclicker_core import dispatch_hotkey

        action = MagicMock()
        dispatch_hotkey(
            mock_key.f6,
            [(mock_key.f6, action)],
            threading.Lock(),
            {},
            0.2,
        )
        action.assert_called_once()

    def test_dispatch_rate_limits(self):
        from autoclicker_core import dispatch_hotkey

        action = MagicMock()
        state = {}
        lock = threading.Lock()
        dispatch_hotkey(mock_key.f6, [(mock_key.f6, action)], lock, state, 0.2)
        dispatch_hotkey(mock_key.f6, [(mock_key.f6, action)], lock, state, 0.2)
        self.assertEqual(action.call_count, 1)

    def test_dispatch_prunes_stale(self):
        from autoclicker_core import dispatch_hotkey

        state = {f"old_{i}": 0.0 for i in range(25)}  # 25 stale entries
        lock = threading.Lock()
        dispatch_hotkey(mock_key.f6, [(mock_key.f6, MagicMock())], lock, state, 0.2)
        self.assertLess(len(state), 25)


class TestApplyIntervalPyQt(unittest.TestCase):
    """Test AppWindow._apply_interval (PyQt6 backend)."""

    def _make_obj(self):
        obj = object.__new__(AppWindow)
        obj.clicker1_lock = threading.Lock()
        obj.clicker2_lock = threading.Lock()
        obj.keypresser_lock = threading.Lock()
        obj.clicker1_interval = 0.1
        obj.clicker2_interval = 0.5
        obj.keypresser_interval = 0.1
        obj._save_config = MagicMock()
        obj._ui_updater = MagicMock()
        obj._ui_updater.requested = MagicMock()
        return obj

    def test_valid_interval_applied(self):
        obj = self._make_obj()
        edit = MagicMock()
        edit.text.return_value = "0.25"
        with unittest.mock.patch("autoclicker.QMessageBox"):
            obj._apply_interval(edit, "clicker1_interval", "Clicker 1")
        self.assertAlmostEqual(obj.clicker1_interval, 0.25)
        obj._save_config.assert_called_once()

    def test_invalid_interval_rejected(self):
        obj = self._make_obj()
        edit = MagicMock()
        edit.text.return_value = "not_a_number"
        with unittest.mock.patch("autoclicker.QMessageBox"):
            obj._apply_interval(edit, "clicker1_interval", "Clicker 1")
        self.assertAlmostEqual(obj.clicker1_interval, 0.1)  # unchanged

    def test_below_min_rejected(self):
        obj = self._make_obj()
        edit = MagicMock()
        edit.text.return_value = "0.001"
        with unittest.mock.patch("autoclicker.QMessageBox"):
            obj._apply_interval(edit, "clicker1_interval", "Clicker 1")
        self.assertAlmostEqual(obj.clicker1_interval, 0.1)  # unchanged

    def test_above_max_rejected(self):
        obj = self._make_obj()
        edit = MagicMock()
        edit.text.return_value = "999"
        with unittest.mock.patch("autoclicker.QMessageBox"):
            obj._apply_interval(edit, "clicker1_interval", "Clicker 1")
        self.assertAlmostEqual(obj.clicker1_interval, 0.1)  # unchanged

    def test_keypresser_interval_uses_correct_lock(self):
        obj = self._make_obj()
        edit = MagicMock()
        edit.text.return_value = "0.3"
        with unittest.mock.patch("autoclicker.QMessageBox"):
            obj._apply_interval(edit, "keypresser_interval", "Key Presser")
        self.assertAlmostEqual(obj.keypresser_interval, 0.3)


class TestOnKeyPressCapturePyQt(unittest.TestCase):
    """Test AppWindow._on_key_press in hotkey capture mode."""

    def _make_obj(self):
        obj = object.__new__(AppWindow)
        obj.hotkey_capture_lock = threading.Lock()
        obj.listening_for_hotkey = False
        obj.hotkey_target = None
        obj.clicker1_hotkey = mock_key.f6
        obj.clicker1_hotkey_display = "F6"
        obj.clicker2_hotkey = mock_key.f7
        obj.clicker2_hotkey_display = "F7"
        obj.keypresser_hotkey = mock_key.f8
        obj.keypresser_hotkey_display = "F8"
        obj.emergency_stop_hotkey = mock_key.f9
        obj.emergency_stop_hotkey_display = "F9"
        obj._hotkey1_btn = MagicMock()
        obj._hotkey2_btn = MagicMock()
        obj._kp_hotkey_btn = MagicMock()
        obj._emergency_stop_btn = MagicMock()
        obj._save_config = MagicMock()
        obj._ui_updater = MagicMock()
        obj._ui_updater.requested = MagicMock()
        obj.last_hotkey_time = {}
        obj.hotkey_timing_lock = threading.Lock()
        obj.hotkey_cooldown = 0.2
        obj.toggle_clicker1 = MagicMock()
        obj.toggle_clicker2 = MagicMock()
        obj.toggle_keypresser = MagicMock()
        obj.emergency_stop_all = MagicMock()
        return obj

    def test_capture_mode_sets_hotkey(self):
        obj = self._make_obj()
        obj.listening_for_hotkey = True
        obj.hotkey_target = "clicker1"
        obj._on_key_press(mock_key.f7)
        self.assertFalse(obj.listening_for_hotkey)
        self.assertEqual(obj.clicker1_hotkey, mock_key.f7)
        obj._save_config.assert_called_once()

    def test_capture_mode_resets_flag(self):
        obj = self._make_obj()
        obj.listening_for_hotkey = True
        obj.hotkey_target = "emergency_stop"
        obj._on_key_press(mock_key.f6)
        self.assertFalse(obj.listening_for_hotkey)
        self.assertEqual(obj.emergency_stop_hotkey, mock_key.f6)

    def test_non_capture_dispatches_normally(self):
        obj = self._make_obj()
        obj.listening_for_hotkey = False
        obj._on_key_press(mock_key.f6)
        obj.toggle_clicker1.assert_called_once()


class TestOnKeyCaptureEvdev(unittest.TestCase):
    """Test DualAutoClicker._on_key_press in hotkey capture mode."""

    def _make_obj(self):
        obj = _make_evdev_obj()
        obj.hotkey_capture_lock = threading.Lock()
        obj.listening_for_hotkey = False
        obj.hotkey_target = None
        obj.clicker1_hotkey = mock_key.f6
        obj.clicker1_hotkey_display = "F6"
        obj.clicker2_hotkey = mock_key.f7
        obj.clicker2_hotkey_display = "F7"
        obj.keypresser_hotkey = mock_key.f8
        obj.keypresser_hotkey_display = "F8"
        obj.emergency_stop_hotkey = mock_key.f9
        obj.emergency_stop_hotkey_display = "F9"
        obj.hotkey1_button = MagicMock()
        obj.hotkey2_button = MagicMock()
        obj.keypresser_hotkey_button = MagicMock()
        obj.emergency_stop_button = MagicMock()
        obj.save_config = MagicMock()
        obj.window = MagicMock()
        obj.last_hotkey_time = {}
        obj.hotkey_timing_lock = threading.Lock()
        obj.hotkey_cooldown = 0.2
        obj.toggle_clicker1 = MagicMock()
        obj.toggle_clicker2 = MagicMock()
        obj.toggle_keypresser = MagicMock()
        obj.emergency_stop_all = MagicMock()
        return obj

    def test_capture_mode_sets_hotkey(self):
        obj = self._make_obj()
        obj.listening_for_hotkey = True
        obj.hotkey_target = "clicker2"
        obj._on_key_press(mock_key.f9)
        self.assertFalse(obj.listening_for_hotkey)
        self.assertEqual(obj.clicker2_hotkey, mock_key.f9)
        obj.save_config.assert_called_once()

    def test_non_capture_dispatches_normally(self):
        obj = self._make_obj()
        obj.listening_for_hotkey = False
        obj._on_key_press(mock_key.f7)
        obj.toggle_clicker2.assert_called_once()


class TestDuplicateHotkey(unittest.TestCase):
    """Test behavior when two features share the same hotkey."""

    def test_first_match_wins(self):
        from autoclicker_core import dispatch_hotkey

        action1 = MagicMock()
        action2 = MagicMock()
        dispatch_hotkey(
            mock_key.f6,
            [(mock_key.f6, action1), (mock_key.f6, action2)],
            threading.Lock(),
            {},
            0.2,
        )
        action1.assert_called_once()
        action2.assert_not_called()


class TestActionLoopDriftReset(unittest.TestCase):
    """Test action_loop handles overrun (action slower than interval)."""

    def test_drift_reset_does_not_hang(self):
        from autoclicker_core import action_loop as _action_loop

        stop = threading.Event()
        call_count = {"n": 0}

        def slow_action():
            call_count["n"] += 1
            time.sleep(0.005)  # action takes 5ms, interval is 1ms
            if call_count["n"] >= 5:
                stop.set()

        _action_loop(stop, lambda: 0.001, slow_action, lambda e: None)
        self.assertGreaterEqual(call_count["n"], 5)


class TestVerifyOversizedResponse(unittest.TestCase):
    """Test _verify_file_against_github rejects oversized API responses."""

    def test_oversized_api_response_raises(self):
        obj = object.__new__(AppWindow)
        content = b"hello"

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        # Return exactly MAX_METADATA_RESPONSE_SIZE + 1 bytes
        from autoclicker import MAX_METADATA_RESPONSE_SIZE

        mock_response.read.return_value = b"x" * (MAX_METADATA_RESPONSE_SIZE + 1)

        import urllib.request

        with unittest.mock.patch.object(
            urllib.request, "urlopen", return_value=mock_response
        ):
            with self.assertRaises(ValueError):
                obj._verify_file_against_github(
                    "v1.0", "test.py", content, {"User-Agent": "test"}
                )


class TestThreadJoinVerification(unittest.TestCase):
    """Verify threads actually stop after stop is called."""

    def _make_pyqt_clicker(self):
        obj = object.__new__(AppWindow)
        obj.clicker1_lock = threading.Lock()
        obj.clicker2_lock = threading.Lock()
        obj.keypresser_lock = threading.Lock()
        obj.clicker1_clicking = False
        obj.clicker2_clicking = False
        obj.keypresser_pressing = False
        obj.clicker1_interval = 0.01
        obj.clicker2_interval = 0.01
        obj.keypresser_interval = 0.01
        obj.clicker1_thread = None
        obj.clicker2_thread = None
        obj.keypresser_thread = None
        obj.clicker1_stop = threading.Event()
        obj.clicker1_stop.set()
        obj.clicker2_stop = threading.Event()
        obj.clicker2_stop.set()
        obj.keypresser_stop = threading.Event()
        obj.keypresser_stop.set()
        obj.keypresser_target_key = mock_key.space
        obj.mouse_controller = MagicMock()
        obj.keyboard_controller = MagicMock()
        obj._status1_label = MagicMock()
        obj._status2_label = MagicMock()
        obj._kp_status_label = MagicMock()
        obj._ui_updater = MagicMock()
        obj._ui_updater.requested = MagicMock()
        return obj

    def test_thread_actually_stops(self):
        obj = self._make_pyqt_clicker()
        obj.perform_click = MagicMock()
        obj.start_clicker1()
        self.assertTrue(obj.clicker1_clicking)
        obj.stop_clicker1()
        if obj.clicker1_thread:
            obj.clicker1_thread.join(timeout=2)
            self.assertFalse(
                obj.clicker1_thread.is_alive(), "Thread did not stop within timeout"
            )

    def test_keypresser_thread_stops(self):
        obj = self._make_pyqt_clicker()
        obj.perform_keypress = MagicMock()
        obj.start_keypresser()
        self.assertTrue(obj.keypresser_pressing)
        obj.stop_keypresser()
        if obj.keypresser_thread:
            obj.keypresser_thread.join(timeout=2)
            self.assertFalse(
                obj.keypresser_thread.is_alive(),
                "Keypresser thread did not stop within timeout",
            )


class TestConfigTargetKeyRoundtripPyQt(unittest.TestCase):
    """Verify keypresser_target_key survives PyQt6 config save/load."""

    def test_roundtrip_target_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "autoclicker" / "config.json"
            obj = object.__new__(AppWindow)
            obj.clicker1_interval = 0.1
            obj.clicker2_interval = 0.5
            obj.clicker1_hotkey = mock_key.f6
            obj.clicker1_hotkey_display = "F6"
            obj.clicker2_hotkey = mock_key.f7
            obj.clicker2_hotkey_display = "F7"
            obj.keypresser_interval = 0.1
            obj.keypresser_hotkey = mock_key.f8
            obj.keypresser_hotkey_display = "F8"
            obj.keypresser_target_key = mock_key.enter
            obj.keypresser_target_key_display = "Enter"
            obj.emergency_stop_hotkey = mock_key.f9
            obj.emergency_stop_hotkey_display = "F9"
            obj.auto_check_updates = True
            geo = MagicMock()
            geo.width.return_value = 600
            geo.height.return_value = 800
            geo.x.return_value = 100
            geo.y.return_value = 50
            obj.geometry = MagicMock(return_value=geo)
            type(obj)._config_path = property(lambda self: cfg)
            obj._save_config()

            obj2 = object.__new__(AppWindow)
            obj2.clicker1_interval = 0.1
            obj2.clicker2_interval = 0.5
            obj2.clicker1_hotkey = mock_key.f6
            obj2.clicker1_hotkey_display = "F6"
            obj2.clicker2_hotkey = mock_key.f7
            obj2.clicker2_hotkey_display = "F7"
            obj2.keypresser_interval = 0.1
            obj2.keypresser_hotkey = mock_key.f8
            obj2.keypresser_hotkey_display = "F8"
            obj2.keypresser_target_key = mock_key.space
            obj2.keypresser_target_key_display = "Space"
            obj2.emergency_stop_hotkey = mock_key.f9
            obj2.emergency_stop_hotkey_display = "F9"
            obj2.auto_check_updates = True
            obj2.resize = MagicMock()
            obj2.move = MagicMock()
            type(obj2)._config_path = property(lambda self: cfg)
            obj2._load_config()

            self.assertEqual(obj2.keypresser_target_key_display, "Enter")


if __name__ == "__main__":
    unittest.main()

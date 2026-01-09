#!/usr/bin/env python3
"""Unit tests for autoclicker_evdev.py"""
import unittest
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock the evdev module since tests may run on non-Linux systems
sys.modules['evdev'] = MagicMock()
sys.modules['evdev'].UInput = MagicMock()
sys.modules['evdev'].ecodes = MagicMock()
sys.modules['evdev'].ecodes.KEY_SPACE = 57
sys.modules['evdev'].ecodes.KEY_ENTER = 28
sys.modules['evdev'].ecodes.KEY_TAB = 15
sys.modules['evdev'].ecodes.KEY_ESC = 1
sys.modules['evdev'].ecodes.KEY_BACKSPACE = 14
sys.modules['evdev'].ecodes.KEY_DELETE = 111
sys.modules['evdev'].ecodes.KEY_UP = 103
sys.modules['evdev'].ecodes.KEY_DOWN = 108
sys.modules['evdev'].ecodes.KEY_LEFT = 105
sys.modules['evdev'].ecodes.KEY_RIGHT = 106
sys.modules['evdev'].ecodes.KEY_HOME = 102
sys.modules['evdev'].ecodes.KEY_END = 107
sys.modules['evdev'].ecodes.KEY_PAGEUP = 104
sys.modules['evdev'].ecodes.KEY_PAGEDOWN = 109
sys.modules['evdev'].ecodes.KEY_INSERT = 110
sys.modules['evdev'].ecodes.KEY_LEFTSHIFT = 42
sys.modules['evdev'].ecodes.KEY_RIGHTSHIFT = 54
sys.modules['evdev'].ecodes.KEY_LEFTCTRL = 29
sys.modules['evdev'].ecodes.KEY_RIGHTCTRL = 97
sys.modules['evdev'].ecodes.KEY_LEFTALT = 56
sys.modules['evdev'].ecodes.KEY_RIGHTALT = 100
sys.modules['evdev'].ecodes.KEY_F1 = 59
sys.modules['evdev'].ecodes.KEY_F2 = 60
sys.modules['evdev'].ecodes.KEY_F3 = 61
sys.modules['evdev'].ecodes.KEY_F4 = 62
sys.modules['evdev'].ecodes.KEY_F5 = 63
sys.modules['evdev'].ecodes.KEY_F6 = 64
sys.modules['evdev'].ecodes.KEY_F7 = 65
sys.modules['evdev'].ecodes.KEY_F8 = 66
sys.modules['evdev'].ecodes.KEY_F9 = 67
sys.modules['evdev'].ecodes.KEY_F10 = 68
sys.modules['evdev'].ecodes.KEY_F11 = 87
sys.modules['evdev'].ecodes.KEY_F12 = 88
sys.modules['evdev'].ecodes.KEY_A = 30
sys.modules['evdev'].ecodes.KEY_B = 48
sys.modules['evdev'].ecodes.KEY_Z = 44
sys.modules['evdev'].ecodes.KEY_0 = 11
sys.modules['evdev'].ecodes.KEY_1 = 2
sys.modules['evdev'].ecodes.KEY_9 = 10
sys.modules['evdev'].ecodes.BTN_LEFT = 272
sys.modules['evdev'].ecodes.BTN_RIGHT = 273
sys.modules['evdev'].ecodes.BTN_MIDDLE = 274
sys.modules['evdev'].ecodes.EV_KEY = 1
sys.modules['evdev'].ecodes.KEY_KPDOT = 83

# Mock pynput
mock_key = MagicMock()
mock_key.f6 = MagicMock(name='f6')
mock_key.f6.name = 'f6'
mock_key.f7 = MagicMock(name='f7')
mock_key.f7.name = 'f7'
mock_key.f8 = MagicMock(name='f8')
mock_key.f8.name = 'f8'
mock_key.f9 = MagicMock(name='f9')
mock_key.f9.name = 'f9'

mock_keycode = MagicMock()
mock_keycode.from_char = MagicMock(return_value=MagicMock(char='a'))

mock_keyboard_module = MagicMock()
mock_keyboard_module.Key = mock_key
mock_keyboard_module.KeyCode = mock_keycode
mock_keyboard_module.Listener = MagicMock()

sys.modules['pynput'] = MagicMock()
sys.modules['pynput.keyboard'] = mock_keyboard_module


class TestValidateInterval(unittest.TestCase):
    """Tests for _validate_interval method"""

    def setUp(self):
        # Create a mock instance with the method
        self.clicker = MagicMock()
        # Import the actual validate logic
        from autoclicker_evdev import MIN_INTERVAL, MAX_INTERVAL, DEFAULT_CLICKER1_INTERVAL
        self.MIN_INTERVAL = MIN_INTERVAL
        self.MAX_INTERVAL = MAX_INTERVAL
        self.DEFAULT = DEFAULT_CLICKER1_INTERVAL

    def _validate_interval(self, interval, default):
        """Replicate the validation logic for testing"""
        try:
            interval_float = float(interval)
            if self.MIN_INTERVAL <= interval_float <= self.MAX_INTERVAL:
                return interval_float
        except (ValueError, TypeError):
            pass
        return default

    def test_valid_interval(self):
        """Test valid intervals within bounds"""
        self.assertEqual(self._validate_interval(0.1, self.DEFAULT), 0.1)
        self.assertEqual(self._validate_interval(1.0, self.DEFAULT), 1.0)
        self.assertEqual(self._validate_interval(30.0, self.DEFAULT), 30.0)

    def test_string_interval(self):
        """Test string conversion"""
        self.assertEqual(self._validate_interval("0.5", self.DEFAULT), 0.5)
        self.assertEqual(self._validate_interval("1", self.DEFAULT), 1.0)

    def test_below_minimum(self):
        """Test interval below minimum returns default"""
        result = self._validate_interval(0.001, self.DEFAULT)
        self.assertEqual(result, self.DEFAULT)

    def test_above_maximum(self):
        """Test interval above maximum returns default"""
        result = self._validate_interval(100.0, self.DEFAULT)
        self.assertEqual(result, self.DEFAULT)

    def test_invalid_string(self):
        """Test invalid string returns default"""
        self.assertEqual(self._validate_interval("not a number", self.DEFAULT), self.DEFAULT)

    def test_none_value(self):
        """Test None returns default"""
        self.assertEqual(self._validate_interval(None, self.DEFAULT), self.DEFAULT)

    def test_boundary_minimum(self):
        """Test exactly at minimum boundary"""
        self.assertEqual(self._validate_interval(self.MIN_INTERVAL, self.DEFAULT), self.MIN_INTERVAL)

    def test_boundary_maximum(self):
        """Test exactly at maximum boundary"""
        self.assertEqual(self._validate_interval(self.MAX_INTERVAL, self.DEFAULT), self.MAX_INTERVAL)

    def test_negative_interval(self):
        """Test negative interval returns default"""
        self.assertEqual(self._validate_interval(-1.0, self.DEFAULT), self.DEFAULT)


class TestKeyMapping(unittest.TestCase):
    """Tests for _tk_key_to_evdev method"""

    def setUp(self):
        from evdev import ecodes as e
        self.e = e

    def _tk_key_to_evdev(self, tk_key):
        """Replicate the key mapping logic for testing"""
        key_map = {
            'space': self.e.KEY_SPACE,
            'Return': self.e.KEY_ENTER,
            'Tab': self.e.KEY_TAB,
            'Escape': self.e.KEY_ESC,
            'BackSpace': self.e.KEY_BACKSPACE,
            'Delete': self.e.KEY_DELETE,
            'Up': self.e.KEY_UP,
            'Down': self.e.KEY_DOWN,
            'Left': self.e.KEY_LEFT,
            'Right': self.e.KEY_RIGHT,
            'Home': self.e.KEY_HOME,
            'End': self.e.KEY_END,
            'Page_Up': self.e.KEY_PAGEUP,
            'Page_Down': self.e.KEY_PAGEDOWN,
            'Insert': self.e.KEY_INSERT,
            'Shift_L': self.e.KEY_LEFTSHIFT,
            'Shift_R': self.e.KEY_RIGHTSHIFT,
            'Control_L': self.e.KEY_LEFTCTRL,
            'Control_R': self.e.KEY_RIGHTCTRL,
            'Alt_L': self.e.KEY_LEFTALT,
            'Alt_R': self.e.KEY_RIGHTALT,
        }

        if tk_key in key_map:
            return key_map[tk_key]

        if tk_key.startswith('F') and tk_key[1:].isdigit():
            f_num = int(tk_key[1:])
            if 1 <= f_num <= 12:
                return getattr(self.e, f'KEY_F{f_num}', self.e.KEY_SPACE)

        if len(tk_key) == 1 and tk_key.isalpha():
            return getattr(self.e, f'KEY_{tk_key.upper()}', self.e.KEY_SPACE)

        if len(tk_key) == 1 and tk_key.isdigit():
            return getattr(self.e, f'KEY_{tk_key}', self.e.KEY_SPACE)

        return self.e.KEY_SPACE

    def test_special_keys(self):
        """Test special key mapping"""
        self.assertEqual(self._tk_key_to_evdev('space'), self.e.KEY_SPACE)
        self.assertEqual(self._tk_key_to_evdev('Return'), self.e.KEY_ENTER)
        self.assertEqual(self._tk_key_to_evdev('Tab'), self.e.KEY_TAB)
        self.assertEqual(self._tk_key_to_evdev('Escape'), self.e.KEY_ESC)

    def test_arrow_keys(self):
        """Test arrow key mapping"""
        self.assertEqual(self._tk_key_to_evdev('Up'), self.e.KEY_UP)
        self.assertEqual(self._tk_key_to_evdev('Down'), self.e.KEY_DOWN)
        self.assertEqual(self._tk_key_to_evdev('Left'), self.e.KEY_LEFT)
        self.assertEqual(self._tk_key_to_evdev('Right'), self.e.KEY_RIGHT)

    def test_function_keys(self):
        """Test function key mapping"""
        self.assertEqual(self._tk_key_to_evdev('F1'), self.e.KEY_F1)
        self.assertEqual(self._tk_key_to_evdev('F6'), self.e.KEY_F6)
        self.assertEqual(self._tk_key_to_evdev('F12'), self.e.KEY_F12)

    def test_letter_keys(self):
        """Test letter key mapping"""
        self.assertEqual(self._tk_key_to_evdev('a'), self.e.KEY_A)
        self.assertEqual(self._tk_key_to_evdev('A'), self.e.KEY_A)
        self.assertEqual(self._tk_key_to_evdev('z'), self.e.KEY_Z)

    def test_number_keys(self):
        """Test number key mapping"""
        self.assertEqual(self._tk_key_to_evdev('0'), self.e.KEY_0)
        self.assertEqual(self._tk_key_to_evdev('1'), self.e.KEY_1)
        self.assertEqual(self._tk_key_to_evdev('9'), self.e.KEY_9)

    def test_modifier_keys(self):
        """Test modifier key mapping"""
        self.assertEqual(self._tk_key_to_evdev('Shift_L'), self.e.KEY_LEFTSHIFT)
        self.assertEqual(self._tk_key_to_evdev('Control_L'), self.e.KEY_LEFTCTRL)
        self.assertEqual(self._tk_key_to_evdev('Alt_L'), self.e.KEY_LEFTALT)

    def test_unknown_key_defaults_to_space(self):
        """Test unknown keys default to space"""
        self.assertEqual(self._tk_key_to_evdev('unknown'), self.e.KEY_SPACE)
        self.assertEqual(self._tk_key_to_evdev(''), self.e.KEY_SPACE)


class TestKeySerialization(unittest.TestCase):
    """Tests for _serialize_key and _deserialize_key methods"""

    def _serialize_key(self, key):
        """Replicate serialization logic"""
        if hasattr(key, 'name'):
            return {'type': 'special', 'name': key.name}
        elif hasattr(key, 'char'):
            return {'type': 'char', 'char': key.char}
        else:
            return {'type': 'special', 'name': 'f6'}

    def _deserialize_key(self, key_data):
        """Replicate deserialization logic"""
        from pynput.keyboard import Key, KeyCode

        if not isinstance(key_data, dict):
            return Key.f6

        key_type = key_data.get('type', 'special')
        if not isinstance(key_type, str):
            return Key.f6

        if key_type == 'special':
            name = key_data.get('name', 'f6')
            if not isinstance(name, str):
                return Key.f6
            return getattr(Key, name, Key.f6)
        elif key_type == 'char':
            char = key_data.get('char')
            if char and isinstance(char, str) and len(char) == 1:
                return KeyCode.from_char(char)
            return Key.f6
        else:
            return Key.f6

    def test_serialize_special_key(self):
        """Test serialization of special keys"""
        key = MagicMock()
        key.name = 'f6'
        result = self._serialize_key(key)
        self.assertEqual(result, {'type': 'special', 'name': 'f6'})

    def test_serialize_char_key(self):
        """Test serialization of character keys"""
        key = MagicMock(spec=['char'])
        key.char = 'a'
        del key.name  # Ensure 'name' attribute doesn't exist
        result = self._serialize_key(key)
        self.assertEqual(result, {'type': 'char', 'char': 'a'})

    def test_deserialize_invalid_type(self):
        """Test deserialization with invalid data type"""
        from pynput.keyboard import Key
        result = self._deserialize_key("not a dict")
        self.assertEqual(result, Key.f6)
        result = self._deserialize_key(None)
        self.assertEqual(result, Key.f6)
        result = self._deserialize_key(123)
        self.assertEqual(result, Key.f6)

    def test_deserialize_special_key(self):
        """Test deserialization of special keys"""
        from pynput.keyboard import Key
        result = self._deserialize_key({'type': 'special', 'name': 'f7'})
        self.assertEqual(result, Key.f7)

    def test_deserialize_missing_char(self):
        """Test deserialization with missing char"""
        from pynput.keyboard import Key
        result = self._deserialize_key({'type': 'char'})
        self.assertEqual(result, Key.f6)

    def test_deserialize_invalid_char(self):
        """Test deserialization with invalid char"""
        from pynput.keyboard import Key
        result = self._deserialize_key({'type': 'char', 'char': 'ab'})
        self.assertEqual(result, Key.f6)

    def test_deserialize_unknown_type(self):
        """Test deserialization with unknown type"""
        from pynput.keyboard import Key
        result = self._deserialize_key({'type': 'unknown', 'name': 'test'})
        self.assertEqual(result, Key.f6)


class TestKeyDisplayName(unittest.TestCase):
    """Tests for get_key_display_name method"""

    def get_key_display_name(self, key):
        """Replicate display name logic"""
        if hasattr(key, 'name'):
            name = key.name
            if name.startswith('f') and name[1:].isdigit():
                return name.upper()
            return name.capitalize()
        elif hasattr(key, 'char') and key.char:
            return key.char.upper()
        else:
            return str(key)

    def test_function_key_display(self):
        """Test function key display names"""
        key = MagicMock()
        key.name = 'f6'
        self.assertEqual(self.get_key_display_name(key), 'F6')

        key.name = 'f12'
        self.assertEqual(self.get_key_display_name(key), 'F12')

    def test_special_key_display(self):
        """Test special key display names"""
        key = MagicMock()
        key.name = 'shift'
        self.assertEqual(self.get_key_display_name(key), 'Shift')

        key.name = 'ctrl'
        self.assertEqual(self.get_key_display_name(key), 'Ctrl')

    def test_char_key_display(self):
        """Test character key display names"""
        key = MagicMock(spec=['char'])
        key.char = 'a'
        del key.name
        self.assertEqual(self.get_key_display_name(key), 'A')

        key.char = 'z'
        self.assertEqual(self.get_key_display_name(key), 'Z')

    def test_fallback_display(self):
        """Test fallback to string representation"""
        key = MagicMock(spec=[])  # No name or char
        del key.name
        del key.char
        result = self.get_key_display_name(key)
        self.assertIsInstance(result, str)


class TestConfigPersistence(unittest.TestCase):
    """Tests for config save/load"""

    def test_config_file_creation(self):
        """Test config directory and file creation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "autoclicker" / "config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)

            config = {
                'clicker1_interval': 0.1,
                'clicker2_interval': 0.5,
            }

            with open(config_path, 'w') as f:
                json.dump(config, f)

            self.assertTrue(config_path.exists())

            with open(config_path, 'r') as f:
                loaded = json.load(f)

            self.assertEqual(loaded['clicker1_interval'], 0.1)
            self.assertEqual(loaded['clicker2_interval'], 0.5)

    def test_config_invalid_json(self):
        """Test handling of invalid JSON in config"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            with open(config_path, 'w') as f:
                f.write("not valid json {{{")

            try:
                with open(config_path, 'r') as f:
                    json.load(f)
                self.fail("Should have raised JSONDecodeError")
            except json.JSONDecodeError:
                pass  # Expected


class TestVersionComparison(unittest.TestCase):
    """Tests for _version_newer method"""

    def _version_newer(self, latest, current):
        """
        Replicate the version comparison logic for testing.
        Handles semantic versioning with pre-release suffixes.
        """
        def parse_version(version_str):
            if not version_str or not isinstance(version_str, str):
                return (0, 0, 0, '', 0)

            version_str = version_str.lstrip('v')

            if '-' in version_str:
                main_part, pre_release = version_str.split('-', 1)
            else:
                main_part, pre_release = version_str, ''

            parts = []
            for part in main_part.split('.'):
                try:
                    parts.append(int(part))
                except ValueError:
                    digits = ''
                    for c in part:
                        if c.isdigit():
                            digits += c
                        else:
                            break
                    parts.append(int(digits) if digits else 0)

            while len(parts) < 3:
                parts.append(0)

            pre_release_num = 0
            if pre_release:
                digits = ''.join(c for c in pre_release if c.isdigit())
                pre_release_num = int(digits) if digits else 0

            return (parts[0], parts[1], parts[2], pre_release == '', pre_release_num)

        try:
            latest_parsed = parse_version(latest)
            current_parsed = parse_version(current)
            return latest_parsed > current_parsed
        except Exception:
            return False

    def test_basic_comparison(self):
        """Test basic version comparisons"""
        self.assertTrue(self._version_newer("1.1.0", "1.0.0"))
        self.assertTrue(self._version_newer("2.0.0", "1.9.9"))
        self.assertTrue(self._version_newer("1.0.1", "1.0.0"))
        self.assertFalse(self._version_newer("1.0.0", "1.0.0"))
        self.assertFalse(self._version_newer("1.0.0", "1.0.1"))

    def test_pre_release_versions(self):
        """Test pre-release version handling"""
        # Stable > pre-release with same version
        self.assertTrue(self._version_newer("1.4.0", "1.4.0-beta"))
        self.assertTrue(self._version_newer("1.4.0", "1.4.0-alpha"))
        self.assertTrue(self._version_newer("1.4.0", "1.4.0-rc1"))

        # Pre-release < stable
        self.assertFalse(self._version_newer("1.4.0-beta", "1.4.0"))

        # Beta2 > beta1
        self.assertTrue(self._version_newer("1.4.0-beta2", "1.4.0-beta1"))

    def test_v_prefix(self):
        """Test version strings with 'v' prefix"""
        self.assertTrue(self._version_newer("v1.1.0", "v1.0.0"))
        self.assertTrue(self._version_newer("v1.1.0", "1.0.0"))
        self.assertTrue(self._version_newer("1.1.0", "v1.0.0"))

    def test_two_part_versions(self):
        """Test two-part version strings"""
        self.assertTrue(self._version_newer("1.1", "1.0"))
        # "1.1.0" and "1.1" are equivalent (both parse to 1.1.0)
        self.assertFalse(self._version_newer("1.1.0", "1.1"))
        self.assertFalse(self._version_newer("1.0", "1.0.0"))

    def test_invalid_versions(self):
        """Test handling of invalid version strings"""
        # Invalid latest version should not be considered newer
        self.assertFalse(self._version_newer(None, "1.0.0"))
        self.assertFalse(self._version_newer("", "1.0.0"))
        self.assertFalse(self._version_newer("invalid", "1.0.0"))
        # Any valid version IS newer than invalid/None current
        self.assertTrue(self._version_newer("1.0.0", None))
        self.assertTrue(self._version_newer("1.0.0", ""))

    def test_edge_cases(self):
        """Test edge cases"""
        # Large version numbers
        self.assertTrue(self._version_newer("100.0.0", "99.99.99"))

        # Zero versions
        self.assertTrue(self._version_newer("0.0.1", "0.0.0"))

        # Same pre-release
        self.assertFalse(self._version_newer("1.0.0-beta", "1.0.0-beta"))


class TestConstants(unittest.TestCase):
    """Tests for module constants"""

    def test_interval_bounds(self):
        """Test interval bounds are sensible"""
        from autoclicker_evdev import MIN_INTERVAL, MAX_INTERVAL
        self.assertGreater(MIN_INTERVAL, 0)
        self.assertLess(MIN_INTERVAL, 1)
        self.assertGreater(MAX_INTERVAL, MIN_INTERVAL)
        self.assertLessEqual(MAX_INTERVAL, 3600)  # Not more than 1 hour

    def test_default_intervals(self):
        """Test default intervals are within bounds"""
        from autoclicker_evdev import (
            MIN_INTERVAL, MAX_INTERVAL,
            DEFAULT_CLICKER1_INTERVAL,
            DEFAULT_CLICKER2_INTERVAL,
            DEFAULT_KEYPRESSER_INTERVAL
        )
        self.assertGreaterEqual(DEFAULT_CLICKER1_INTERVAL, MIN_INTERVAL)
        self.assertLessEqual(DEFAULT_CLICKER1_INTERVAL, MAX_INTERVAL)
        self.assertGreaterEqual(DEFAULT_CLICKER2_INTERVAL, MIN_INTERVAL)
        self.assertLessEqual(DEFAULT_CLICKER2_INTERVAL, MAX_INTERVAL)
        self.assertGreaterEqual(DEFAULT_KEYPRESSER_INTERVAL, MIN_INTERVAL)
        self.assertLessEqual(DEFAULT_KEYPRESSER_INTERVAL, MAX_INTERVAL)


if __name__ == '__main__':
    unittest.main()

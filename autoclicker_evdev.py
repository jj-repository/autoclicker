#!/usr/bin/env python3
"""
Dual AutoClicker + Key Presser - Linux evdev Version

This version uses evdev for low-level input simulation via the Linux kernel.
Works on Linux (X11 and Wayland) with games and applications that don't
detect higher-level input libraries.

Use this version when:
- Running on Linux (X11 or Wayland)
- Games/apps don't detect pynput mouse clicks
- You need keyboard key pressing automation

Requirements:
- Linux only (evdev is Linux-specific)
- Requires uinput access (run with sudo or add user to 'input' group)
- Install: pip install -r requirements-linux.txt

For cross-platform support (Windows/macOS), use autoclicker.py instead.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, Union
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
from evdev import UInput, ecodes as e

# Constants
MIN_INTERVAL = 0.01  # Minimum interval: 10ms (100 clicks/sec max)
MAX_INTERVAL = 60.0  # Maximum interval: 60 seconds
DEFAULT_CLICKER1_INTERVAL = 0.1
DEFAULT_CLICKER2_INTERVAL = 0.5
DEFAULT_KEYPRESSER_INTERVAL = 0.1


class DualAutoClicker:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Dual AutoClicker + Key Presser")
        self.window.geometry("750x850")
        self.window.resizable(True, True)

        # Config file path
        self.config_path = Path.home() / ".config" / "autoclicker" / "config.json"

        # Thread locks for thread-safe state access
        self.clicker1_lock = threading.Lock()
        self.clicker2_lock = threading.Lock()
        self.keypresser_lock = threading.Lock()

        # Clicker 1 state (defaults)
        self.clicker1_hotkey = Key.f6
        self.clicker1_hotkey_display = "F6"
        self.clicker1_interval = DEFAULT_CLICKER1_INTERVAL
        self.clicker1_clicking = False
        self.clicker1_thread = None

        # Clicker 2 state (defaults)
        self.clicker2_hotkey = Key.f7
        self.clicker2_hotkey_display = "F7"
        self.clicker2_interval = DEFAULT_CLICKER2_INTERVAL
        self.clicker2_clicking = False
        self.clicker2_thread = None

        # Keyboard Key Presser state (defaults)
        self.keypresser_hotkey = Key.f8
        self.keypresser_hotkey_display = "F8"
        self.keypresser_interval = DEFAULT_KEYPRESSER_INTERVAL
        self.keypresser_target_key = e.KEY_SPACE  # Default to spacebar
        self.keypresser_target_key_display = "Space"
        self.keypresser_pressing = False
        self.keypresser_thread = None

        # Emergency Stop hotkey (defaults)
        self.emergency_stop_hotkey = Key.f9
        self.emergency_stop_hotkey_display = "F9"

        # Shared state
        self.virtual_mouse = None  # Will be initialized when needed
        self.virtual_keyboard = None  # Will be initialized when needed
        self.keyboard_listener = None
        self.hotkey_capture_listener = None
        self.hotkey_capture_lock = threading.Lock()  # Lock for hotkey capture state
        self.listening_for_hotkey = False
        self.hotkey_target = None  # "clicker1", "clicker2", "keypresser", or "emergency_stop"

        # Rate limiting for hotkey presses
        self.last_hotkey_time = {}
        self.hotkey_cooldown = 0.2  # 200ms cooldown between hotkey presses

        # UI elements
        self.interval1_var = None
        self.interval2_var = None
        self.hotkey1_button = None
        self.hotkey2_button = None
        self.status1_var = None
        self.status2_var = None
        self.keypresser_interval_var = None
        self.keypresser_hotkey_button = None
        self.keypresser_target_key_button = None
        self.keypresser_status_var = None
        self.emergency_stop_button = None

        # Load saved configuration
        self.load_config()

        self.setup_ui()
        self.start_keyboard_listener()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _validate_interval(self, interval: Any, default: float) -> float:
        """Validate interval is within acceptable bounds."""
        try:
            interval_float = float(interval)
            if MIN_INTERVAL <= interval_float <= MAX_INTERVAL:
                return interval_float
        except (ValueError, TypeError):
            pass
        return default

    def load_config(self):
        """Load saved configuration from JSON file"""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            # Load and validate intervals
            self.clicker1_interval = self._validate_interval(
                config.get('clicker1_interval', self.clicker1_interval),
                DEFAULT_CLICKER1_INTERVAL
            )
            self.clicker2_interval = self._validate_interval(
                config.get('clicker2_interval', self.clicker2_interval),
                DEFAULT_CLICKER2_INTERVAL
            )
            self.keypresser_interval = self._validate_interval(
                config.get('keypresser_interval', self.keypresser_interval),
                DEFAULT_KEYPRESSER_INTERVAL
            )

            # Load hotkeys
            if 'clicker1_hotkey' in config:
                self.clicker1_hotkey = self._deserialize_key(config['clicker1_hotkey'])
                self.clicker1_hotkey_display = config.get('clicker1_hotkey_display', 'F6')

            if 'clicker2_hotkey' in config:
                self.clicker2_hotkey = self._deserialize_key(config['clicker2_hotkey'])
                self.clicker2_hotkey_display = config.get('clicker2_hotkey_display', 'F7')

            if 'keypresser_hotkey' in config:
                self.keypresser_hotkey = self._deserialize_key(config['keypresser_hotkey'])
                self.keypresser_hotkey_display = config.get('keypresser_hotkey_display', 'F8')

            # Load keypresser target key with validation
            target_key = config.get('keypresser_target_key', self.keypresser_target_key)
            if isinstance(target_key, int) and 0 <= target_key <= 255:
                self.keypresser_target_key = target_key
            else:
                print(f"Warning: Invalid keypresser_target_key in config, using default")
            self.keypresser_target_key_display = config.get('keypresser_target_key_display', 'Space')

            # Load emergency stop hotkey
            if 'emergency_stop_hotkey' in config:
                self.emergency_stop_hotkey = self._deserialize_key(config['emergency_stop_hotkey'])
                self.emergency_stop_hotkey_display = config.get('emergency_stop_hotkey_display', 'F9')

        except json.JSONDecodeError as e:
            print(f"Error: Config file is corrupted: {e}")
        except (IOError, OSError) as e:
            print(f"Error: Cannot read config file: {e}")
        except Exception as e:
            print(f"Error loading config: {e}")

    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            # Create config directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            config = {
                'clicker1_interval': self.clicker1_interval,
                'clicker2_interval': self.clicker2_interval,
                'clicker1_hotkey': self._serialize_key(self.clicker1_hotkey),
                'clicker1_hotkey_display': self.clicker1_hotkey_display,
                'clicker2_hotkey': self._serialize_key(self.clicker2_hotkey),
                'clicker2_hotkey_display': self.clicker2_hotkey_display,
                'keypresser_interval': self.keypresser_interval,
                'keypresser_hotkey': self._serialize_key(self.keypresser_hotkey),
                'keypresser_hotkey_display': self.keypresser_hotkey_display,
                'keypresser_target_key': self.keypresser_target_key,
                'keypresser_target_key_display': self.keypresser_target_key_display,
                'emergency_stop_hotkey': self._serialize_key(self.emergency_stop_hotkey),
                'emergency_stop_hotkey_display': self.emergency_stop_hotkey_display,
            }

            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)

        except Exception as e:
            print(f"Error saving config: {e}")

    def _serialize_key(self, key: Union[Key, KeyCode]) -> Dict[str, str]:
        """Convert a pynput key to a JSON-serializable format."""
        if hasattr(key, 'name'):
            return {'type': 'special', 'name': key.name}
        elif hasattr(key, 'char'):
            return {'type': 'char', 'char': key.char}
        else:
            return {'type': 'special', 'name': 'f6'}  # fallback

    def _deserialize_key(self, key_data: Any) -> Union[Key, KeyCode]:
        """Convert JSON data back to a pynput key."""
        # Validate that key_data is a dict with expected structure
        if not isinstance(key_data, dict):
            print(f"Warning: Invalid hotkey data type, expected dict, got {type(key_data).__name__}")
            return Key.f6

        key_type = key_data.get('type', 'special')
        if not isinstance(key_type, str):
            return Key.f6

        if key_type == 'special':
            # Get the Key attribute by name
            name = key_data.get('name', 'f6')
            if not isinstance(name, str):
                return Key.f6
            return getattr(Key, name, Key.f6)
        elif key_type == 'char':
            char = key_data.get('char')
            if char and isinstance(char, str) and len(char) == 1:
                return KeyCode.from_char(char)
            return Key.f6  # fallback if char is missing or invalid
        else:
            return Key.f6  # fallback

    def setup_ui(self):
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        title_label = ttk.Label(main_frame, text="Dual AutoClicker + Key Presser", font=("Arial", 18, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # Separator 1 (between clicker 1 and 2)
        separator1 = ttk.Separator(main_frame, orient='vertical')
        separator1.grid(row=1, column=1, rowspan=6, sticky='ns', padx=20)

        # ----- CLICKER 1 (Mouse Button) -----
        self._setup_clicker1_ui(main_frame, 0, 1)

        # ----- CLICKER 2 (Mouse Button) -----
        self._setup_clicker2_ui(main_frame, 2, 1)

        # Horizontal separator before keyboard presser
        hseparator = ttk.Separator(main_frame, orient='horizontal')
        hseparator.grid(row=9, column=0, columnspan=3, sticky='ew', pady=(30, 30))

        # ----- KEYBOARD KEY PRESSER -----
        # Title
        keypresser_title = ttk.Label(main_frame, text="Keyboard Key Presser", font=("Arial", 14, "bold"))
        keypresser_title.grid(row=10, column=0, columnspan=3, pady=(0, 15))

        # Left side (column 0)
        self._setup_keypresser_left_ui(main_frame, 0, 11)

        # Separator between left and right
        separator2 = ttk.Separator(main_frame, orient='vertical')
        separator2.grid(row=11, column=1, rowspan=5, sticky='ns', padx=20)

        # Right side (column 2)
        self._setup_keypresser_right_ui(main_frame, 2, 11)

        # Emergency Stop Section
        hseparator2 = ttk.Separator(main_frame, orient='horizontal')
        hseparator2.grid(row=17, column=0, columnspan=3, sticky='ew', pady=(30, 20))

        emergency_title = ttk.Label(main_frame, text="Emergency Stop All", font=("Arial", 12, "bold"), foreground="red")
        emergency_title.grid(row=18, column=0, columnspan=3)

        emergency_label = ttk.Label(main_frame, text="Hotkey to stop ALL autoclickers:")
        emergency_label.grid(row=19, column=0, columnspan=3, pady=(10, 5))

        self.emergency_stop_button = ttk.Button(
            main_frame,
            text=f"Current: {self.emergency_stop_hotkey_display}",
            command=lambda: self.start_hotkey_capture("emergency_stop"),
            width=20
        )
        self.emergency_stop_button.grid(row=20, column=0, columnspan=3, pady=5)

        # Instructions at bottom
        instructions = ttk.Label(
            main_frame,
            text="Mouse clickers stop each other when started. Keyboard presser is independent.\nEmergency Stop will stop everything at once.",
            wraplength=650,
            justify=tk.CENTER,
            font=("Arial", 9, "italic")
        )
        instructions.grid(row=21, column=0, columnspan=3, pady=(30, 0))

    def _setup_clicker1_ui(self, parent, column, start_row):
        """Setup UI for Clicker 1"""
        # Title
        title = ttk.Label(parent, text="Clicker 1", font=("Arial", 14, "bold"))
        title.grid(row=start_row, column=column, pady=(0, 15))

        # Interval
        interval_label = ttk.Label(parent, text="Interval (seconds):")
        interval_label.grid(row=start_row+1, column=column, sticky=tk.W, pady=5)

        self.interval1_var = tk.StringVar(value=str(self.clicker1_interval))
        interval_entry = ttk.Entry(parent, textvariable=self.interval1_var, width=20)
        interval_entry.grid(row=start_row+2, column=column, sticky=tk.W, pady=5)

        # Apply interval button
        apply_button = ttk.Button(
            parent,
            text="Apply Interval",
            command=self.apply_interval1
        )
        apply_button.grid(row=start_row+3, column=column, pady=5)

        # Hotkey
        hotkey_label = ttk.Label(parent, text="Toggle Hotkey:")
        hotkey_label.grid(row=start_row+4, column=column, sticky=tk.W, pady=(10, 5))

        self.hotkey1_button = ttk.Button(
            parent,
            text=f"Current: {self.clicker1_hotkey_display}",
            command=lambda: self.start_hotkey_capture("clicker1"),
            width=20
        )
        self.hotkey1_button.grid(row=start_row+5, column=column, sticky=tk.W, pady=5)

        # Status
        self.status1_var = tk.StringVar(value="Idle")
        self.status1_label = tk.Label(parent, textvariable=self.status1_var, font=("Arial", 10, "bold"), fg="green")
        self.status1_label.grid(row=start_row+6, column=column, pady=(10, 5))

    def _setup_clicker2_ui(self, parent, column, start_row):
        """Setup UI for Clicker 2"""
        # Title
        title = ttk.Label(parent, text="Clicker 2", font=("Arial", 14, "bold"))
        title.grid(row=start_row, column=column, pady=(0, 15))

        # Interval
        interval_label = ttk.Label(parent, text="Interval (seconds):")
        interval_label.grid(row=start_row+1, column=column, sticky=tk.W, pady=5)

        self.interval2_var = tk.StringVar(value=str(self.clicker2_interval))
        interval_entry = ttk.Entry(parent, textvariable=self.interval2_var, width=20)
        interval_entry.grid(row=start_row+2, column=column, sticky=tk.W, pady=5)

        # Apply interval button
        apply_button = ttk.Button(
            parent,
            text="Apply Interval",
            command=self.apply_interval2
        )
        apply_button.grid(row=start_row+3, column=column, pady=5)

        # Hotkey
        hotkey_label = ttk.Label(parent, text="Toggle Hotkey:")
        hotkey_label.grid(row=start_row+4, column=column, sticky=tk.W, pady=(10, 5))

        self.hotkey2_button = ttk.Button(
            parent,
            text=f"Current: {self.clicker2_hotkey_display}",
            command=lambda: self.start_hotkey_capture("clicker2"),
            width=20
        )
        self.hotkey2_button.grid(row=start_row+5, column=column, sticky=tk.W, pady=5)

        # Status
        self.status2_var = tk.StringVar(value="Idle")
        self.status2_label = tk.Label(parent, textvariable=self.status2_var, font=("Arial", 10, "bold"), fg="green")
        self.status2_label.grid(row=start_row+6, column=column, pady=(10, 5))

    def _setup_keypresser_left_ui(self, parent, column, start_row):
        """Setup left side of Keyboard Key Presser UI"""
        # Target Key Selection
        target_key_label = ttk.Label(parent, text="Key to Press:")
        target_key_label.grid(row=start_row, column=column, sticky=tk.W, pady=5)

        self.keypresser_target_key_button = ttk.Button(
            parent,
            text=f"Current: {self.keypresser_target_key_display}",
            command=self.select_target_key,
            width=20
        )
        self.keypresser_target_key_button.grid(row=start_row+1, column=column, sticky=tk.W, pady=5)

        # Interval
        interval_label = ttk.Label(parent, text="Interval (seconds):")
        interval_label.grid(row=start_row+2, column=column, sticky=tk.W, pady=(15, 5))

        self.keypresser_interval_var = tk.StringVar(value=str(self.keypresser_interval))
        interval_entry = ttk.Entry(parent, textvariable=self.keypresser_interval_var, width=20)
        interval_entry.grid(row=start_row+3, column=column, sticky=tk.W, pady=5)

        # Apply interval button
        apply_button = ttk.Button(
            parent,
            text="Apply Interval",
            command=self.apply_keypresser_interval
        )
        apply_button.grid(row=start_row+4, column=column, pady=5)

    def _setup_keypresser_right_ui(self, parent, column, start_row):
        """Setup right side of Keyboard Key Presser UI"""
        # Hotkey
        hotkey_label = ttk.Label(parent, text="Toggle Hotkey:")
        hotkey_label.grid(row=start_row, column=column, sticky=tk.W, pady=5)

        self.keypresser_hotkey_button = ttk.Button(
            parent,
            text=f"Current: {self.keypresser_hotkey_display}",
            command=lambda: self.start_hotkey_capture("keypresser"),
            width=20
        )
        self.keypresser_hotkey_button.grid(row=start_row+1, column=column, sticky=tk.W, pady=5)

        # Status
        status_label = ttk.Label(parent, text="Status:")
        status_label.grid(row=start_row+2, column=column, sticky=tk.W, pady=(15, 5))

        self.keypresser_status_var = tk.StringVar(value="Idle")
        self.keypresser_status_label = tk.Label(parent, textvariable=self.keypresser_status_var, font=("Arial", 10, "bold"), fg="green")
        self.keypresser_status_label.grid(row=start_row+3, column=column, pady=5)

    def _apply_interval(self, interval_var, target_attr, name):
        """Consolidated interval application with validation"""
        try:
            interval_value = float(interval_var.get())
            if interval_value < MIN_INTERVAL:
                raise ValueError(f"Interval must be at least {MIN_INTERVAL}s (prevents system overload)")
            if interval_value > MAX_INTERVAL:
                raise ValueError(f"Interval must be at most {MAX_INTERVAL}s")
            # Use appropriate lock when modifying interval values
            if target_attr == 'clicker1_interval':
                with self.clicker1_lock:
                    setattr(self, target_attr, interval_value)
            elif target_attr == 'clicker2_interval':
                with self.clicker2_lock:
                    setattr(self, target_attr, interval_value)
            elif target_attr == 'keypresser_interval':
                with self.keypresser_lock:
                    setattr(self, target_attr, interval_value)
            else:
                setattr(self, target_attr, interval_value)
            self.save_config()
            messagebox.showinfo("Success", f"{name} interval updated to {interval_value}s")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid interval: {e}")

    def apply_interval1(self):
        self._apply_interval(self.interval1_var, 'clicker1_interval', 'Clicker 1')

    def apply_interval2(self):
        self._apply_interval(self.interval2_var, 'clicker2_interval', 'Clicker 2')

    def apply_keypresser_interval(self):
        self._apply_interval(self.keypresser_interval_var, 'keypresser_interval', 'Key Presser')

    def select_target_key(self):
        """Let user select which keyboard key to auto-press"""
        # Create a simple dialog to capture a key press
        dialog = tk.Toplevel(self.window)
        dialog.title("Select Key to Press")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        dialog.grab_set()  # Make it modal

        label = ttk.Label(dialog, text="Press any key...", font=("Arial", 12))
        label.pack(pady=40)

        def on_key_press(event):
            # Map the key to evdev keycode
            key_name = event.keysym
            evdev_keycode = self._tk_key_to_evdev(key_name)
            if evdev_keycode:
                self.keypresser_target_key = evdev_keycode
                self.keypresser_target_key_display = key_name.upper() if len(key_name) == 1 else key_name.capitalize()
                self.keypresser_target_key_button.config(text=f"Current: {self.keypresser_target_key_display}")
                self.save_config()
            dialog.destroy()

        dialog.bind("<Key>", on_key_press)
        dialog.focus_set()

    def _tk_key_to_evdev(self, tk_key: str) -> int:
        """Convert tkinter key name to evdev keycode."""
        # Common key mappings
        key_map = {
            'space': e.KEY_SPACE,
            'Return': e.KEY_ENTER,
            'Tab': e.KEY_TAB,
            'Escape': e.KEY_ESC,
            'BackSpace': e.KEY_BACKSPACE,
            'Delete': e.KEY_DELETE,
            'Up': e.KEY_UP,
            'Down': e.KEY_DOWN,
            'Left': e.KEY_LEFT,
            'Right': e.KEY_RIGHT,
            'Home': e.KEY_HOME,
            'End': e.KEY_END,
            'Page_Up': e.KEY_PAGEUP,
            'Page_Down': e.KEY_PAGEDOWN,
            'Insert': e.KEY_INSERT,
            'Shift_L': e.KEY_LEFTSHIFT,
            'Shift_R': e.KEY_RIGHTSHIFT,
            'Control_L': e.KEY_LEFTCTRL,
            'Control_R': e.KEY_RIGHTCTRL,
            'Alt_L': e.KEY_LEFTALT,
            'Alt_R': e.KEY_RIGHTALT,
        }

        # Check if it's in the map
        if tk_key in key_map:
            return key_map[tk_key]

        # Handle F keys
        if tk_key.startswith('F') and tk_key[1:].isdigit():
            f_num = int(tk_key[1:])
            if 1 <= f_num <= 12:
                return getattr(e, f'KEY_F{f_num}', e.KEY_SPACE)

        # Handle letter keys
        if len(tk_key) == 1 and tk_key.isalpha():
            return getattr(e, f'KEY_{tk_key.upper()}', e.KEY_SPACE)

        # Handle number keys
        if len(tk_key) == 1 and tk_key.isdigit():
            return getattr(e, f'KEY_{tk_key}', e.KEY_SPACE)

        # Default to spacebar if unknown
        return e.KEY_SPACE

    def start_hotkey_capture(self, target):
        with self.hotkey_capture_lock:
            if self.listening_for_hotkey:
                return

            self.listening_for_hotkey = True
            self.hotkey_target = target

        if target == "clicker1":
            self.hotkey1_button.config(text="Press a key...")
        elif target == "clicker2":
            self.hotkey2_button.config(text="Press a key...")
        elif target == "keypresser":
            self.keypresser_hotkey_button.config(text="Press a key...")
        else:  # emergency_stop
            self.emergency_stop_button.config(text="Press a key...")

        # Stop the main keyboard listener temporarily
        self.stop_keyboard_listener()

        # Start a temporary listener to capture the hotkey
        with self.hotkey_capture_lock:
            self.hotkey_capture_listener = keyboard.Listener(on_press=self.capture_hotkey)
            self.hotkey_capture_listener.start()

    def capture_hotkey(self, key):
        with self.hotkey_capture_lock:
            if not self.listening_for_hotkey:
                return

            # Stop the capture listener
            if self.hotkey_capture_listener:
                self.hotkey_capture_listener.stop()
                self.hotkey_capture_listener = None

            self.listening_for_hotkey = False
            target = self.hotkey_target

        # Set the new hotkey
        key_display = self.get_key_display_name(key)

        if target == "clicker1":
            self.clicker1_hotkey = key
            self.clicker1_hotkey_display = key_display
            self.window.after(0, lambda: self.hotkey1_button.config(text=f"Current: {key_display}"))
        elif target == "clicker2":
            self.clicker2_hotkey = key
            self.clicker2_hotkey_display = key_display
            self.window.after(0, lambda: self.hotkey2_button.config(text=f"Current: {key_display}"))
        elif target == "keypresser":
            self.keypresser_hotkey = key
            self.keypresser_hotkey_display = key_display
            self.window.after(0, lambda: self.keypresser_hotkey_button.config(text=f"Current: {key_display}"))
        else:  # emergency_stop
            self.emergency_stop_hotkey = key
            self.emergency_stop_hotkey_display = key_display
            self.window.after(0, lambda: self.emergency_stop_button.config(text=f"Current: {key_display}"))

        # Save the new configuration
        self.save_config()

        # Restart the main keyboard listener
        self.window.after(0, self.start_keyboard_listener)

    def init_virtual_mouse(self):
        """Initialize the virtual mouse device using evdev"""
        if self.virtual_mouse is None:
            try:
                # Create a virtual mouse device with button capabilities
                cap = {
                    e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
                }
                self.virtual_mouse = UInput(cap, name="AutoClicker-Virtual-Mouse")
            except Exception as ex:
                print(f"Failed to create virtual mouse device: {ex}")
                print("You may need to run with: sudo python3 autoclicker_evdev.py")
                raise

    def perform_click(self):
        """Perform a single left mouse click using evdev"""
        if self.virtual_mouse is None:
            self.init_virtual_mouse()

        # Press left button
        self.virtual_mouse.write(e.EV_KEY, e.BTN_LEFT, 1)
        self.virtual_mouse.syn()

        # Release left button
        self.virtual_mouse.write(e.EV_KEY, e.BTN_LEFT, 0)
        self.virtual_mouse.syn()

    def init_virtual_keyboard(self):
        """Initialize the virtual keyboard device using evdev"""
        if self.virtual_keyboard is None:
            try:
                # Create a virtual keyboard device with all key capabilities
                # We need to include all keys we might want to press
                keys = list(range(e.KEY_ESC, e.KEY_KPDOT + 1))
                cap = {
                    e.EV_KEY: keys,
                }
                self.virtual_keyboard = UInput(cap, name="AutoClicker-Virtual-Keyboard")
            except Exception as ex:
                print(f"Failed to create virtual keyboard device: {ex}")
                print("You may need to run with: sudo python3 autoclicker_evdev.py")
                raise

    def perform_keypress(self):
        """Perform a single key press using evdev"""
        if self.virtual_keyboard is None:
            self.init_virtual_keyboard()

        # Press the key
        self.virtual_keyboard.write(e.EV_KEY, self.keypresser_target_key, 1)
        self.virtual_keyboard.syn()

        # Release the key
        self.virtual_keyboard.write(e.EV_KEY, self.keypresser_target_key, 0)
        self.virtual_keyboard.syn()

    def get_key_display_name(self, key):
        # Handle special keys
        if hasattr(key, 'name'):
            name = key.name
            # Format function keys nicely
            if name.startswith('f') and name[1:].isdigit():
                return name.upper()
            # Capitalize first letter for other special keys
            return name.capitalize()
        # Handle character keys
        elif hasattr(key, 'char') and key.char:
            return key.char.upper()
        else:
            return str(key)

    def on_hotkey_press(self, key):
        """Handle hotkey presses with rate limiting"""
        try:
            # Rate limiting to prevent rapid toggling
            current_time = time.time()
            key_str = str(key)

            if key_str in self.last_hotkey_time:
                if current_time - self.last_hotkey_time[key_str] < self.hotkey_cooldown:
                    return  # Ignore rapid key presses

            self.last_hotkey_time[key_str] = current_time

            # Check emergency stop hotkey first (highest priority)
            if key == self.emergency_stop_hotkey:
                self.emergency_stop_all()
            # Check clicker 1 hotkey
            elif key == self.clicker1_hotkey:
                self.toggle_clicker1()
            # Check clicker 2 hotkey
            elif key == self.clicker2_hotkey:
                self.toggle_clicker2()
            # Check keypresser hotkey
            elif key == self.keypresser_hotkey:
                self.toggle_keypresser()
        except AttributeError as e:
            # Key comparison failed - likely a key object without expected attributes
            # This can happen with some special key combinations
            pass

    def toggle_clicker1(self):
        with self.clicker1_lock:
            clicking = self.clicker1_clicking
        if clicking:
            # Stop clicker 1
            self.stop_clicker1()
        else:
            # Start clicker 1 (and stop clicker 2 if running)
            self.stop_clicker2()
            self.start_clicker1()

    def toggle_clicker2(self):
        with self.clicker2_lock:
            clicking = self.clicker2_clicking
        if clicking:
            # Stop clicker 2
            self.stop_clicker2()
        else:
            # Start clicker 2 (and stop clicker 1 if running)
            self.stop_clicker1()
            self.start_clicker2()

    def start_clicker1(self):
        with self.clicker1_lock:
            if not self.clicker1_clicking:
                self.clicker1_clicking = True
                self.status1_var.set("Clicking...")
                self.status1_label.config(fg="red")
                self.clicker1_thread = threading.Thread(target=self._click_loop1, daemon=True)
                self.clicker1_thread.start()

    def stop_clicker1(self):
        with self.clicker1_lock:
            if self.clicker1_clicking:
                self.clicker1_clicking = False
                self.status1_var.set("Idle")
                self.status1_label.config(fg="green")

    def start_clicker2(self):
        with self.clicker2_lock:
            if not self.clicker2_clicking:
                self.clicker2_clicking = True
                self.status2_var.set("Clicking...")
                self.status2_label.config(fg="red")
                self.clicker2_thread = threading.Thread(target=self._click_loop2, daemon=True)
                self.clicker2_thread.start()

    def stop_clicker2(self):
        with self.clicker2_lock:
            if self.clicker2_clicking:
                self.clicker2_clicking = False
                self.status2_var.set("Idle")
                self.status2_label.config(fg="green")

    def _click_loop1(self):
        """Click loop for clicker 1 with error handling"""
        while True:
            with self.clicker1_lock:
                if not self.clicker1_clicking:
                    break
                interval = self.clicker1_interval

            try:
                self.perform_click()
            except Exception as e:
                print(f"Error in clicker 1: {e}")
                with self.clicker1_lock:
                    self.clicker1_clicking = False
                self.window.after(0, lambda: self.status1_var.set("Error"))
                self.window.after(0, lambda: self.status1_label.config(fg="orange"))
                break

            time.sleep(interval)

    def _click_loop2(self):
        """Click loop for clicker 2 with error handling"""
        while True:
            with self.clicker2_lock:
                if not self.clicker2_clicking:
                    break
                interval = self.clicker2_interval

            try:
                self.perform_click()
            except Exception as e:
                print(f"Error in clicker 2: {e}")
                with self.clicker2_lock:
                    self.clicker2_clicking = False
                self.window.after(0, lambda: self.status2_var.set("Error"))
                self.window.after(0, lambda: self.status2_label.config(fg="orange"))
                break

            time.sleep(interval)

    def toggle_keypresser(self):
        # Thread-safe: read state while holding lock to prevent race condition
        with self.keypresser_lock:
            is_pressing = self.keypresser_pressing

        if is_pressing:
            # Stop keypresser
            self.stop_keypresser()
        else:
            # Start keypresser (independent from clickers)
            self.start_keypresser()

    def start_keypresser(self):
        with self.keypresser_lock:
            if not self.keypresser_pressing:
                self.keypresser_pressing = True
                self.keypresser_status_var.set("Pressing...")
                self.keypresser_status_label.config(fg="red")
                self.keypresser_thread = threading.Thread(target=self._keypresser_loop, daemon=True)
                self.keypresser_thread.start()

    def stop_keypresser(self):
        with self.keypresser_lock:
            if self.keypresser_pressing:
                self.keypresser_pressing = False
                self.keypresser_status_var.set("Idle")
                self.keypresser_status_label.config(fg="green")

    def _keypresser_loop(self):
        """Key press loop with error handling"""
        while True:
            with self.keypresser_lock:
                if not self.keypresser_pressing:
                    break
                interval = self.keypresser_interval

            try:
                self.perform_keypress()
            except Exception as e:
                print(f"Error in key presser: {e}")
                with self.keypresser_lock:
                    self.keypresser_pressing = False
                self.window.after(0, lambda: self.keypresser_status_var.set("Error"))
                self.window.after(0, lambda: self.keypresser_status_label.config(fg="orange"))
                break

            time.sleep(interval)

    def emergency_stop_all(self):
        """Stop all autoclickers and key presser immediately"""
        self.stop_clicker1()
        self.stop_clicker2()
        self.stop_keypresser()
        # Visual feedback could be added here if desired

    def start_keyboard_listener(self):
        # Stop existing listener first if present to prevent resource leak
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass
        self.keyboard_listener = keyboard.Listener(on_press=self.on_hotkey_press)
        self.keyboard_listener.start()

    def stop_keyboard_listener(self):
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass

    def on_closing(self):
        self.stop_clicker1()
        self.stop_clicker2()
        self.stop_keypresser()
        self.stop_keyboard_listener()
        if self.hotkey_capture_listener:
            try:
                self.hotkey_capture_listener.stop()
            except Exception:
                pass
        # Wait for threads to finish to ensure clean shutdown
        if self.clicker1_thread:
            if self.clicker1_thread.is_alive():
                self.clicker1_thread.join(timeout=1.0)
            if self.clicker1_thread.is_alive():
                print("Warning: Clicker 1 thread did not exit cleanly")
        if self.clicker2_thread:
            if self.clicker2_thread.is_alive():
                self.clicker2_thread.join(timeout=1.0)
            if self.clicker2_thread.is_alive():
                print("Warning: Clicker 2 thread did not exit cleanly")
        if self.keypresser_thread:
            if self.keypresser_thread.is_alive():
                self.keypresser_thread.join(timeout=1.0)
            if self.keypresser_thread.is_alive():
                print("Warning: Key presser thread did not exit cleanly")
        # Clean up virtual devices
        if self.virtual_mouse:
            try:
                self.virtual_mouse.close()
            except Exception as e:
                print(f"Warning: Error closing virtual mouse: {e}")
        if self.virtual_keyboard:
            try:
                self.virtual_keyboard.close()
            except Exception as e:
                print(f"Warning: Error closing virtual keyboard: {e}")
        self.window.destroy()

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    import sys
    import platform

    # Verify we're on Linux (evdev is Linux-only)
    if platform.system() != 'Linux':
        print("ERROR: autoclicker_evdev.py requires Linux (evdev is Linux-only)")
        print("Use autoclicker.py for cross-platform support")
        sys.exit(1)

    # Check if running with root/sudo (required for evdev)
    if hasattr(os, 'geteuid') and os.geteuid() != 0:
        print("ERROR: This script must be run with sudo/root privileges")
        print("Usage: sudo python3 autoclicker_evdev.py")
        sys.exit(1)

    app = DualAutoClicker()
    app.run()

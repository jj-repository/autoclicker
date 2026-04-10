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

import atexit
import json
import os
import platform
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from pynput import keyboard
from pynput.keyboard import Key
from evdev import UInput, ecodes as e

from autoclicker_core import (
    MIN_INTERVAL,
    MAX_INTERVAL,
    DEFAULT_CLICKER1_INTERVAL,
    DEFAULT_CLICKER2_INTERVAL,
    DEFAULT_KEYPRESSER_INTERVAL,
    action_loop,
    dispatch_hotkey,
    validate_interval,
    serialize_key,
    deserialize_key,
    get_key_display_name as _core_get_key_display_name,
)


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
        self.clicker1_stop = threading.Event()
        self.clicker1_stop.set()

        # Clicker 2 state (defaults)
        self.clicker2_hotkey = Key.f7
        self.clicker2_hotkey_display = "F7"
        self.clicker2_interval = DEFAULT_CLICKER2_INTERVAL
        self.clicker2_clicking = False
        self.clicker2_thread = None
        self.clicker2_stop = threading.Event()
        self.clicker2_stop.set()

        # Keyboard Key Presser state (defaults)
        self.keypresser_hotkey = Key.f8
        self.keypresser_hotkey_display = "F8"
        self.keypresser_interval = DEFAULT_KEYPRESSER_INTERVAL
        self.keypresser_target_key = e.KEY_SPACE  # Default to spacebar
        self.keypresser_target_key_display = "Space"
        self.keypresser_pressing = False
        self.keypresser_thread = None
        self.keypresser_stop = threading.Event()
        self.keypresser_stop.set()

        # Emergency Stop hotkey (defaults)
        self.emergency_stop_hotkey = Key.f9
        self.emergency_stop_hotkey_display = "F9"

        # Virtual devices (initialized eagerly to avoid latency on first click)
        self.virtual_mouse = None
        self.virtual_keyboard = None
        try:
            self.init_virtual_mouse()
            self.init_virtual_keyboard()
        except Exception as ex:
            print(f"Warning: Could not init virtual devices: {ex}")

        self.keyboard_listener = None
        self.hotkey_capture_lock = threading.Lock()  # Lock for hotkey capture state
        self.listening_for_hotkey = False
        self.hotkey_target = (
            None  # "clicker1", "clicker2", "keypresser", or "emergency_stop"
        )

        # Rate limiting for hotkey presses (thread-safe)
        self.last_hotkey_time = {}
        self.hotkey_timing_lock = threading.Lock()
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

    def _safe_after(self, delay_ms: int, callback) -> None:
        """
        Safely schedule a callback on the main thread.
        Prevents crashes if window is destroyed before callback runs.
        """
        try:
            if self.window.winfo_exists():
                self.window.after(delay_ms, callback)
        except (tk.TclError, AttributeError):
            # Window was destroyed, ignore the callback
            pass

    @staticmethod
    def _validate_interval(interval, default):
        return validate_interval(interval, default)

    def load_config(self):
        """Load saved configuration from JSON file"""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)

            # Load and validate intervals
            self.clicker1_interval = self._validate_interval(
                config.get("clicker1_interval", self.clicker1_interval),
                DEFAULT_CLICKER1_INTERVAL,
            )
            self.clicker2_interval = self._validate_interval(
                config.get("clicker2_interval", self.clicker2_interval),
                DEFAULT_CLICKER2_INTERVAL,
            )
            self.keypresser_interval = self._validate_interval(
                config.get("keypresser_interval", self.keypresser_interval),
                DEFAULT_KEYPRESSER_INTERVAL,
            )

            # Load hotkeys
            if "clicker1_hotkey" in config:
                self.clicker1_hotkey = self._deserialize_key(config["clicker1_hotkey"])
                self.clicker1_hotkey_display = config.get(
                    "clicker1_hotkey_display", "F6"
                )

            if "clicker2_hotkey" in config:
                self.clicker2_hotkey = self._deserialize_key(config["clicker2_hotkey"])
                self.clicker2_hotkey_display = config.get(
                    "clicker2_hotkey_display", "F7"
                )

            if "keypresser_hotkey" in config:
                self.keypresser_hotkey = self._deserialize_key(
                    config["keypresser_hotkey"]
                )
                self.keypresser_hotkey_display = config.get(
                    "keypresser_hotkey_display", "F8"
                )

            # Load keypresser target key with validation
            target_key = config.get("keypresser_target_key", self.keypresser_target_key)
            if isinstance(target_key, int) and 0 <= target_key <= 767:
                self.keypresser_target_key = target_key
            else:
                print("Warning: Invalid keypresser_target_key in config, using default")
            self.keypresser_target_key_display = config.get(
                "keypresser_target_key_display", "Space"
            )

            # Load emergency stop hotkey
            if "emergency_stop_hotkey" in config:
                self.emergency_stop_hotkey = self._deserialize_key(
                    config["emergency_stop_hotkey"]
                )
                self.emergency_stop_hotkey_display = config.get(
                    "emergency_stop_hotkey_display", "F9"
                )

        except json.JSONDecodeError as e:
            print(f"Error: Config file is corrupted: {e}")
        except (IOError, OSError) as e:
            print(f"Error: Cannot read config file: {e}")
        except (KeyError, TypeError, ValueError) as e:
            print(f"Error loading config values: {e}")

    def save_config(self):
        """Save current configuration to JSON file, merging with existing
        settings so that keys written by the pynput version are preserved."""
        try:
            # Drop root privileges for config I/O if running via sudo
            orig_euid = None
            sudo_uid = os.environ.get("SUDO_UID")
            if os.geteuid() == 0 and sudo_uid:
                uid = int(sudo_uid)
                if 1 <= uid <= 65533:
                    orig_euid = 0
                    os.seteuid(uid)

            # Create config directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing config first to preserve keys from the other version
            existing_config = {}
            if self.config_path.exists():
                try:
                    with open(self.config_path, "r") as f:
                        existing_config = json.load(f)
                except (json.JSONDecodeError, IOError, OSError):
                    existing_config = {}

            config = {
                "clicker1_interval": self.clicker1_interval,
                "clicker2_interval": self.clicker2_interval,
                "clicker1_hotkey": self._serialize_key(self.clicker1_hotkey),
                "clicker1_hotkey_display": self.clicker1_hotkey_display,
                "clicker2_hotkey": self._serialize_key(self.clicker2_hotkey),
                "clicker2_hotkey_display": self.clicker2_hotkey_display,
                "keypresser_interval": self.keypresser_interval,
                "keypresser_hotkey": self._serialize_key(self.keypresser_hotkey),
                "keypresser_hotkey_display": self.keypresser_hotkey_display,
                "keypresser_target_key": self.keypresser_target_key,
                "keypresser_target_key_display": self.keypresser_target_key_display,
                "emergency_stop_hotkey": self._serialize_key(
                    self.emergency_stop_hotkey
                ),
                "emergency_stop_hotkey_display": self.emergency_stop_hotkey_display,
            }

            existing_config.update(config)

            tmp = self.config_path.with_suffix(".json.tmp")
            fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump(existing_config, f, indent=2)
            os.replace(str(tmp), str(self.config_path))

            # Restore root privileges if we dropped them
            if orig_euid is not None:
                os.seteuid(orig_euid)

        except (OSError, ValueError, TypeError) as e:
            if orig_euid is not None:
                try:
                    os.seteuid(orig_euid)
                except OSError:
                    pass
            print(f"Error saving config: {e}")

    @staticmethod
    def _serialize_key(key):
        return serialize_key(key)

    @staticmethod
    def _deserialize_key(key_data):
        return deserialize_key(key_data)

    def setup_ui(self):
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Dual AutoClicker + Key Presser",
            font=("Arial", 18, "bold"),
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # Separator 1 (between clicker 1 and 2)
        separator1 = ttk.Separator(main_frame, orient="vertical")
        separator1.grid(row=1, column=1, rowspan=6, sticky="ns", padx=20)

        # ----- CLICKER 1 (Mouse Button) -----
        self._setup_clicker1_ui(main_frame, 0, 1)

        # ----- CLICKER 2 (Mouse Button) -----
        self._setup_clicker2_ui(main_frame, 2, 1)

        # Horizontal separator before keyboard presser
        hseparator = ttk.Separator(main_frame, orient="horizontal")
        hseparator.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(30, 30))

        # ----- KEYBOARD KEY PRESSER -----
        # Title
        keypresser_title = ttk.Label(
            main_frame, text="Keyboard Key Presser", font=("Arial", 14, "bold")
        )
        keypresser_title.grid(row=10, column=0, columnspan=3, pady=(0, 15))

        # Left side (column 0)
        self._setup_keypresser_left_ui(main_frame, 0, 11)

        # Separator between left and right
        separator2 = ttk.Separator(main_frame, orient="vertical")
        separator2.grid(row=11, column=1, rowspan=5, sticky="ns", padx=20)

        # Right side (column 2)
        self._setup_keypresser_right_ui(main_frame, 2, 11)

        # Emergency Stop Section
        hseparator2 = ttk.Separator(main_frame, orient="horizontal")
        hseparator2.grid(row=17, column=0, columnspan=3, sticky="ew", pady=(30, 20))

        emergency_title = ttk.Label(
            main_frame,
            text="Emergency Stop All",
            font=("Arial", 12, "bold"),
            foreground="red",
        )
        emergency_title.grid(row=18, column=0, columnspan=3)

        emergency_label = ttk.Label(main_frame, text="Hotkey to stop ALL autoclickers:")
        emergency_label.grid(row=19, column=0, columnspan=3, pady=(10, 5))

        self.emergency_stop_button = ttk.Button(
            main_frame,
            text=f"Current: {self.emergency_stop_hotkey_display}",
            command=lambda: self.start_hotkey_capture("emergency_stop"),
            width=20,
        )
        self.emergency_stop_button.grid(row=20, column=0, columnspan=3, pady=5)

        # Instructions at bottom
        instructions = ttk.Label(
            main_frame,
            text="Mouse clickers stop each other when started. Keyboard presser is independent.\nEmergency Stop will stop everything at once.",
            wraplength=650,
            justify=tk.CENTER,
            font=("Arial", 9, "italic"),
        )
        instructions.grid(row=21, column=0, columnspan=3, pady=(30, 0))

    def _setup_clicker1_ui(self, parent, column, start_row):
        """Setup UI for Clicker 1"""
        # Title
        title = ttk.Label(parent, text="Clicker 1", font=("Arial", 14, "bold"))
        title.grid(row=start_row, column=column, pady=(0, 15))

        # Interval
        interval_label = ttk.Label(parent, text="Interval (seconds):")
        interval_label.grid(row=start_row + 1, column=column, sticky=tk.W, pady=5)

        self.interval1_var = tk.StringVar(value=str(self.clicker1_interval))
        interval_entry = ttk.Entry(parent, textvariable=self.interval1_var, width=20)
        interval_entry.grid(row=start_row + 2, column=column, sticky=tk.W, pady=5)

        # Apply interval button
        apply_button = ttk.Button(
            parent, text="Apply Interval", command=self.apply_interval1
        )
        apply_button.grid(row=start_row + 3, column=column, pady=5)

        # Hotkey
        hotkey_label = ttk.Label(parent, text="Toggle Hotkey:")
        hotkey_label.grid(row=start_row + 4, column=column, sticky=tk.W, pady=(10, 5))

        self.hotkey1_button = ttk.Button(
            parent,
            text=f"Current: {self.clicker1_hotkey_display}",
            command=lambda: self.start_hotkey_capture("clicker1"),
            width=20,
        )
        self.hotkey1_button.grid(row=start_row + 5, column=column, sticky=tk.W, pady=5)

        # Status
        self.status1_var = tk.StringVar(value="Idle")
        self.status1_label = tk.Label(
            parent,
            textvariable=self.status1_var,
            font=("Arial", 10, "bold"),
            fg="green",
        )
        self.status1_label.grid(row=start_row + 6, column=column, pady=(10, 5))

    def _setup_clicker2_ui(self, parent, column, start_row):
        """Setup UI for Clicker 2"""
        # Title
        title = ttk.Label(parent, text="Clicker 2", font=("Arial", 14, "bold"))
        title.grid(row=start_row, column=column, pady=(0, 15))

        # Interval
        interval_label = ttk.Label(parent, text="Interval (seconds):")
        interval_label.grid(row=start_row + 1, column=column, sticky=tk.W, pady=5)

        self.interval2_var = tk.StringVar(value=str(self.clicker2_interval))
        interval_entry = ttk.Entry(parent, textvariable=self.interval2_var, width=20)
        interval_entry.grid(row=start_row + 2, column=column, sticky=tk.W, pady=5)

        # Apply interval button
        apply_button = ttk.Button(
            parent, text="Apply Interval", command=self.apply_interval2
        )
        apply_button.grid(row=start_row + 3, column=column, pady=5)

        # Hotkey
        hotkey_label = ttk.Label(parent, text="Toggle Hotkey:")
        hotkey_label.grid(row=start_row + 4, column=column, sticky=tk.W, pady=(10, 5))

        self.hotkey2_button = ttk.Button(
            parent,
            text=f"Current: {self.clicker2_hotkey_display}",
            command=lambda: self.start_hotkey_capture("clicker2"),
            width=20,
        )
        self.hotkey2_button.grid(row=start_row + 5, column=column, sticky=tk.W, pady=5)

        # Status
        self.status2_var = tk.StringVar(value="Idle")
        self.status2_label = tk.Label(
            parent,
            textvariable=self.status2_var,
            font=("Arial", 10, "bold"),
            fg="green",
        )
        self.status2_label.grid(row=start_row + 6, column=column, pady=(10, 5))

    def _setup_keypresser_left_ui(self, parent, column, start_row):
        """Setup left side of Keyboard Key Presser UI"""
        # Target Key Selection
        target_key_label = ttk.Label(parent, text="Key to Press:")
        target_key_label.grid(row=start_row, column=column, sticky=tk.W, pady=5)

        self.keypresser_target_key_button = ttk.Button(
            parent,
            text=f"Current: {self.keypresser_target_key_display}",
            command=self.select_target_key,
            width=20,
        )
        self.keypresser_target_key_button.grid(
            row=start_row + 1, column=column, sticky=tk.W, pady=5
        )

        # Interval
        interval_label = ttk.Label(parent, text="Interval (seconds):")
        interval_label.grid(row=start_row + 2, column=column, sticky=tk.W, pady=(15, 5))

        self.keypresser_interval_var = tk.StringVar(value=str(self.keypresser_interval))
        interval_entry = ttk.Entry(
            parent, textvariable=self.keypresser_interval_var, width=20
        )
        interval_entry.grid(row=start_row + 3, column=column, sticky=tk.W, pady=5)

        # Apply interval button
        apply_button = ttk.Button(
            parent, text="Apply Interval", command=self.apply_keypresser_interval
        )
        apply_button.grid(row=start_row + 4, column=column, pady=5)

    def _setup_keypresser_right_ui(self, parent, column, start_row):
        """Setup right side of Keyboard Key Presser UI"""
        # Hotkey
        hotkey_label = ttk.Label(parent, text="Toggle Hotkey:")
        hotkey_label.grid(row=start_row, column=column, sticky=tk.W, pady=5)

        self.keypresser_hotkey_button = ttk.Button(
            parent,
            text=f"Current: {self.keypresser_hotkey_display}",
            command=lambda: self.start_hotkey_capture("keypresser"),
            width=20,
        )
        self.keypresser_hotkey_button.grid(
            row=start_row + 1, column=column, sticky=tk.W, pady=5
        )

        # Status
        status_label = ttk.Label(parent, text="Status:")
        status_label.grid(row=start_row + 2, column=column, sticky=tk.W, pady=(15, 5))

        self.keypresser_status_var = tk.StringVar(value="Idle")
        self.keypresser_status_label = tk.Label(
            parent,
            textvariable=self.keypresser_status_var,
            font=("Arial", 10, "bold"),
            fg="green",
        )
        self.keypresser_status_label.grid(row=start_row + 3, column=column, pady=5)

    def _apply_interval(self, interval_var, target_attr, name):
        """Consolidated interval application with validation"""
        try:
            interval_value = float(interval_var.get())
            if interval_value < MIN_INTERVAL:
                raise ValueError(
                    f"Interval must be at least {MIN_INTERVAL}s (prevents system overload)"
                )
            if interval_value > MAX_INTERVAL:
                raise ValueError(f"Interval must be at most {MAX_INTERVAL}s")
            # Use appropriate lock when modifying interval values
            if target_attr == "clicker1_interval":
                with self.clicker1_lock:
                    setattr(self, target_attr, interval_value)
            elif target_attr == "clicker2_interval":
                with self.clicker2_lock:
                    setattr(self, target_attr, interval_value)
            elif target_attr == "keypresser_interval":
                with self.keypresser_lock:
                    setattr(self, target_attr, interval_value)
            else:
                setattr(self, target_attr, interval_value)
            self.save_config()
            messagebox.showinfo(
                "Success", f"{name} interval updated to {interval_value}s"
            )
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid interval: {e}")

    def apply_interval1(self):
        self._apply_interval(self.interval1_var, "clicker1_interval", "Clicker 1")

    def apply_interval2(self):
        self._apply_interval(self.interval2_var, "clicker2_interval", "Clicker 2")

    def apply_keypresser_interval(self):
        self._apply_interval(
            self.keypresser_interval_var, "keypresser_interval", "Key Presser"
        )

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
            if evdev_keycode is not None:
                self.keypresser_target_key = evdev_keycode
                self.keypresser_target_key_display = (
                    key_name.upper() if len(key_name) == 1 else key_name.capitalize()
                )
                self.keypresser_target_key_button.config(
                    text=f"Current: {self.keypresser_target_key_display}"
                )
                self.save_config()
            else:
                messagebox.showwarning(
                    "Unsupported Key",
                    f"The key '{key_name}' is not supported.\n\n"
                    "Please choose a standard letter, number, function key, "
                    "or one of the recognized special keys.",
                )
            dialog.destroy()

        dialog.bind("<Key>", on_key_press)
        dialog.focus_set()

    _TK_KEY_MAP = {
        "space": e.KEY_SPACE,
        "Return": e.KEY_ENTER,
        "Tab": e.KEY_TAB,
        "Escape": e.KEY_ESC,
        "BackSpace": e.KEY_BACKSPACE,
        "Delete": e.KEY_DELETE,
        "Up": e.KEY_UP,
        "Down": e.KEY_DOWN,
        "Left": e.KEY_LEFT,
        "Right": e.KEY_RIGHT,
        "Home": e.KEY_HOME,
        "End": e.KEY_END,
        "Page_Up": e.KEY_PAGEUP,
        "Page_Down": e.KEY_PAGEDOWN,
        "Insert": e.KEY_INSERT,
        "Shift_L": e.KEY_LEFTSHIFT,
        "Shift_R": e.KEY_RIGHTSHIFT,
        "Control_L": e.KEY_LEFTCTRL,
        "Control_R": e.KEY_RIGHTCTRL,
        "Alt_L": e.KEY_LEFTALT,
        "Alt_R": e.KEY_RIGHTALT,
    }

    def _tk_key_to_evdev(self, tk_key: str) -> int:
        """Convert tkinter key name to evdev keycode."""
        if tk_key in self._TK_KEY_MAP:
            return self._TK_KEY_MAP[tk_key]

        if tk_key.startswith("F") and tk_key[1:].isdigit():
            f_num = int(tk_key[1:])
            if 1 <= f_num <= 12:
                return getattr(e, f"KEY_F{f_num}", None)

        if len(tk_key) == 1 and tk_key.isalpha():
            return getattr(e, f"KEY_{tk_key.upper()}", None)

        if len(tk_key) == 1 and tk_key.isdigit():
            return getattr(e, f"KEY_{tk_key}", None)

        # Unknown key - return None so the caller can warn the user
        return None

    def start_hotkey_capture(self, target):
        with self.hotkey_capture_lock:
            if self.listening_for_hotkey:
                return
            self.listening_for_hotkey = True
            self.hotkey_target = target

        btn_map = {
            "clicker1": self.hotkey1_button,
            "clicker2": self.hotkey2_button,
            "keypresser": self.keypresser_hotkey_button,
            "emergency_stop": self.emergency_stop_button,
        }
        btn = btn_map.get(target)
        if btn:
            btn.config(text="Press a key...")

    def _on_key_press(self, key):
        """Unified key press handler: capture mode or normal hotkey dispatch."""
        if self.listening_for_hotkey:
            with self.hotkey_capture_lock:
                if not self.listening_for_hotkey:
                    self.on_hotkey_press(key)
                    return
                self.listening_for_hotkey = False
                target = self.hotkey_target
                key_display = self.get_key_display_name(key)
                btn_map = {
                    "clicker1": (
                        "clicker1_hotkey",
                        "clicker1_hotkey_display",
                        self.hotkey1_button,
                    ),
                    "clicker2": (
                        "clicker2_hotkey",
                        "clicker2_hotkey_display",
                        self.hotkey2_button,
                    ),
                    "keypresser": (
                        "keypresser_hotkey",
                        "keypresser_hotkey_display",
                        self.keypresser_hotkey_button,
                    ),
                    "emergency_stop": (
                        "emergency_stop_hotkey",
                        "emergency_stop_hotkey_display",
                        self.emergency_stop_button,
                    ),
                }
                if target in btn_map:
                    key_attr, display_attr, btn = btn_map[target]
                    setattr(self, key_attr, key)
                    setattr(self, display_attr, key_display)
                    self._safe_after(
                        0,
                        lambda b=btn, d=key_display: b.config(text=f"Current: {d}"),
                    )
                self.save_config()
                return
        # Normal hotkey dispatch
        self.on_hotkey_press(key)

    def init_virtual_mouse(self):
        """Initialize the virtual mouse device using evdev"""
        if self.virtual_mouse is None:
            try:
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

        self.virtual_mouse.write(e.EV_KEY, e.BTN_LEFT, 1)
        self.virtual_mouse.syn()
        self.virtual_mouse.write(e.EV_KEY, e.BTN_LEFT, 0)
        self.virtual_mouse.syn()

    def init_virtual_keyboard(self):
        """Initialize the virtual keyboard device using evdev"""
        if self.virtual_keyboard is None:
            try:
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

        self.virtual_keyboard.write(e.EV_KEY, self.keypresser_target_key, 1)
        self.virtual_keyboard.syn()
        self.virtual_keyboard.write(e.EV_KEY, self.keypresser_target_key, 0)
        self.virtual_keyboard.syn()

    @staticmethod
    def get_key_display_name(key):
        return _core_get_key_display_name(key)

    def on_hotkey_press(self, key):
        """Handle hotkey presses with rate limiting"""
        dispatch_hotkey(
            key,
            [
                (self.emergency_stop_hotkey, self.emergency_stop_all),
                (self.clicker1_hotkey, self.toggle_clicker1),
                (self.clicker2_hotkey, self.toggle_clicker2),
                (self.keypresser_hotkey, self.toggle_keypresser),
            ],
            self.hotkey_timing_lock,
            self.last_hotkey_time,
            self.hotkey_cooldown,
        )

    # ── Shared helpers ───────────────────────────────────────────

    def _set_status(self, var, label, text, color):
        self._safe_after(0, lambda: (var.set(text), label.config(fg=color)))

    # ── Clicker 1 ─────────────────────────────────────────────

    def toggle_clicker1(self):
        old_thread = None
        should_start = False
        with self.clicker1_lock:
            if self.clicker1_clicking:
                self._stop_clicker1_locked()
                old_thread = self.clicker1_thread
            else:
                should_start = True
                old_thread = self.clicker1_thread
        if old_thread and old_thread.is_alive():
            old_thread.join(timeout=0.5)
        if should_start:
            self.stop_clicker2()
            with self.clicker1_lock:
                self._start_clicker1_locked()

    def start_clicker1(self):
        with self.clicker1_lock:
            self._start_clicker1_locked()

    def _start_clicker1_locked(self):
        if not self.clicker1_clicking:
            self.clicker1_clicking = True
            self.clicker1_stop.clear()
            self._set_status(self.status1_var, self.status1_label, "Clicking...", "red")

            def on_error(ex):
                print(f"Error in clicker 1: {ex}")
                with self.clicker1_lock:
                    self.clicker1_clicking = False
                err_msg = f"Error: {ex}" if len(str(ex)) < 40 else "Error"
                self._set_status(
                    self.status1_var, self.status1_label, err_msg, "orange"
                )

            self.clicker1_thread = threading.Thread(
                target=action_loop,
                args=(
                    self.clicker1_stop,
                    lambda: self.clicker1_interval,
                    self.perform_click,
                    on_error,
                ),
                daemon=True,
            )
            self.clicker1_thread.start()

    def stop_clicker1(self):
        with self.clicker1_lock:
            self._stop_clicker1_locked()

    def _stop_clicker1_locked(self):
        if self.clicker1_clicking:
            self.clicker1_clicking = False
            self.clicker1_stop.set()
            self._set_status(self.status1_var, self.status1_label, "Idle", "green")

    # ── Clicker 2 ─────────────────────────────────────────────

    def toggle_clicker2(self):
        old_thread = None
        should_start = False
        with self.clicker2_lock:
            if self.clicker2_clicking:
                self._stop_clicker2_locked()
                old_thread = self.clicker2_thread
            else:
                should_start = True
                old_thread = self.clicker2_thread
        if old_thread and old_thread.is_alive():
            old_thread.join(timeout=0.5)
        if should_start:
            self.stop_clicker1()
            with self.clicker2_lock:
                self._start_clicker2_locked()

    def start_clicker2(self):
        with self.clicker2_lock:
            self._start_clicker2_locked()

    def _start_clicker2_locked(self):
        if not self.clicker2_clicking:
            self.clicker2_clicking = True
            self.clicker2_stop.clear()
            self._set_status(self.status2_var, self.status2_label, "Clicking...", "red")

            def on_error(ex):
                print(f"Error in clicker 2: {ex}")
                with self.clicker2_lock:
                    self.clicker2_clicking = False
                err_msg = f"Error: {ex}" if len(str(ex)) < 40 else "Error"
                self._set_status(
                    self.status2_var, self.status2_label, err_msg, "orange"
                )

            self.clicker2_thread = threading.Thread(
                target=action_loop,
                args=(
                    self.clicker2_stop,
                    lambda: self.clicker2_interval,
                    self.perform_click,
                    on_error,
                ),
                daemon=True,
            )
            self.clicker2_thread.start()

    def stop_clicker2(self):
        with self.clicker2_lock:
            self._stop_clicker2_locked()

    def _stop_clicker2_locked(self):
        if self.clicker2_clicking:
            self.clicker2_clicking = False
            self.clicker2_stop.set()
            self._set_status(self.status2_var, self.status2_label, "Idle", "green")

    # ── Key Presser ───────────────────────────────────────────

    def toggle_keypresser(self):
        old_thread = None
        should_start = False
        with self.keypresser_lock:
            if self.keypresser_pressing:
                self._stop_keypresser_locked()
                old_thread = self.keypresser_thread
            else:
                should_start = True
                old_thread = self.keypresser_thread
        if old_thread and old_thread.is_alive():
            old_thread.join(timeout=0.5)
        if should_start:
            with self.keypresser_lock:
                self._start_keypresser_locked()

    def start_keypresser(self):
        with self.keypresser_lock:
            self._start_keypresser_locked()

    def _start_keypresser_locked(self):
        if not self.keypresser_pressing:
            self.keypresser_pressing = True
            self.keypresser_stop.clear()
            self._set_status(
                self.keypresser_status_var,
                self.keypresser_status_label,
                "Pressing...",
                "red",
            )

            def on_error(ex):
                print(f"Error in key presser: {ex}")
                with self.keypresser_lock:
                    self.keypresser_pressing = False
                err_msg = f"Error: {ex}" if len(str(ex)) < 40 else "Error"
                self._set_status(
                    self.keypresser_status_var,
                    self.keypresser_status_label,
                    err_msg,
                    "orange",
                )

            self.keypresser_thread = threading.Thread(
                target=action_loop,
                args=(
                    self.keypresser_stop,
                    lambda: self.keypresser_interval,
                    self.perform_keypress,
                    on_error,
                ),
                daemon=True,
            )
            self.keypresser_thread.start()

    def stop_keypresser(self):
        with self.keypresser_lock:
            self._stop_keypresser_locked()

    def _stop_keypresser_locked(self):
        if self.keypresser_pressing:
            self.keypresser_pressing = False
            self.keypresser_stop.set()
            self._set_status(
                self.keypresser_status_var,
                self.keypresser_status_label,
                "Idle",
                "green",
            )

    # ── Emergency Stop ────────────────────────────────────────

    def emergency_stop_all(self):
        self.stop_clicker1()
        self.stop_clicker2()
        self.stop_keypresser()

    # ── Keyboard listener ─────────────────────────────────────

    def start_keyboard_listener(self):
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
                self.keyboard_listener.join(timeout=1.0)
            except Exception:
                pass
            self.keyboard_listener = None
        self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        self.keyboard_listener.start()

    def stop_keyboard_listener(self):
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
                self.keyboard_listener.join(timeout=1.0)
            except Exception:
                pass
            self.keyboard_listener = None

    # ── Cleanup ───────────────────────────────────────────────

    def _cleanup_devices(self):
        for dev in (self.virtual_mouse, self.virtual_keyboard):
            if dev:
                try:
                    dev.close()
                except Exception as ex:
                    print(f"Warning: Error closing virtual device: {ex}")

    def on_closing(self):
        self.stop_clicker1()
        self.stop_clicker2()
        self.stop_keypresser()
        self.stop_keyboard_listener()
        for name, thread in [
            ("Clicker 1", self.clicker1_thread),
            ("Clicker 2", self.clicker2_thread),
            ("Key presser", self.keypresser_thread),
        ]:
            if thread and thread.is_alive():
                thread.join(timeout=1.0)
                if thread.is_alive():
                    print(f"Warning: {name} thread did not exit cleanly")
        self._cleanup_devices()
        self.save_config()
        self.window.destroy()

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    # Verify we're on Linux (evdev is Linux-only)
    if platform.system() != "Linux":
        print("ERROR: autoclicker_evdev.py requires Linux (evdev is Linux-only)")
        print("Use autoclicker.py for cross-platform support")
        sys.exit(1)

    # Check if running with root/sudo (required for evdev UInput).
    # Alternative: grant uinput access without root via udev rule:
    #   echo 'KERNEL=="uinput", MODE="0660", GROUP="input"' | sudo tee /etc/udev/rules/99-uinput.rules
    #   sudo usermod -aG input $USER  # then re-login
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("ERROR: This script must be run with sudo/root privileges")
        print("Usage: sudo python3 autoclicker_evdev.py")
        sys.exit(1)

    app = DualAutoClicker()
    atexit.register(app._cleanup_devices)
    app.run()

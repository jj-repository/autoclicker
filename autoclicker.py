#!/usr/bin/env python3
"""
Dual AutoClicker + Key Presser - Cross-Platform Version (pynput)

This version uses pynput for mouse control, keyboard key pressing,
and hotkey detection. Works on Windows, macOS, and Linux (X11).

Use this version when:
- Running on Windows or macOS
- Running on Linux with X11 (not Wayland)

For Linux with Wayland or games that don't detect pynput input,
use autoclicker_evdev.py instead (requires root/uinput permissions).
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import sys
import os
from pathlib import Path
from pynput import keyboard, mouse
from pynput.keyboard import Key, KeyCode

__version__ = "1.8.1"

# Update Constants
GITHUB_REPO = "jj-repository/autoclicker"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}"

# Constants
MIN_INTERVAL = 0.01  # Minimum interval: 10ms (100 clicks/sec max)
MAX_INTERVAL = 60.0  # Maximum interval: 60 seconds
DEFAULT_CLICKER1_INTERVAL = 0.1
DEFAULT_CLICKER2_INTERVAL = 0.5
DEFAULT_KEYPRESSER_INTERVAL = 0.1
MAX_DOWNLOAD_SIZE = 5 * 1024 * 1024  # 5MB max download size for updates


class DualAutoClicker:
    # Color schemes
    THEMES = {
        'dark': {
            'bg': '#1e1e1e', 'fg': '#d4d4d4', 'accent': '#264f78',
            'entry_bg': '#2d2d2d', 'entry_fg': '#d4d4d4', 'button_bg': '#3c3c3c',
            'green': '#4ec9b0', 'red': '#f44747', 'orange': '#ce9178',
            'sep': '#404040', 'link': '#3794ff', 'muted': '#808080',
        },
        'light': {
            'bg': '#f0f0f0', 'fg': '#1e1e1e', 'accent': '#0078d4',
            'entry_bg': '#ffffff', 'entry_fg': '#1e1e1e', 'button_bg': '#e1e1e1',
            'green': '#16825d', 'red': '#cd3131', 'orange': '#c17e00',
            'sep': '#c8c8c8', 'link': '#0066cc', 'muted': '#6e6e6e',
        },
    }

    @property
    def _t(self):
        """Current theme colors."""
        return self.THEMES['dark' if self.dark_mode else 'light']

    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Dual AutoClicker + Key Presser")
        self.window.geometry("540x820")
        self.window.minsize(480, 500)

        # Theme state
        self.dark_mode = True
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._apply_theme()

        # Load takodachi image for About dialog
        self._about_image = None
        try:
            # PyInstaller bundles files into sys._MEIPASS; dev mode uses __file__ dir
            base_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
            img_path = base_dir / "takodachi.png"
            if img_path.exists():
                self._about_image = tk.PhotoImage(file=str(img_path))
        except Exception:
            pass

        # Config file path
        if sys.platform == 'win32':
            appdata = os.environ.get('APPDATA', str(Path.home()))
            self.config_path = Path(appdata) / "autoclicker" / "config.json"
        else:
            self.config_path = Path.home() / ".config" / "autoclicker" / "config.json"

        # Thread locks for thread-safe state access
        self.clicker1_lock = threading.Lock()
        self.clicker2_lock = threading.Lock()
        self.keypresser_lock = threading.Lock()
        self.hotkey_capture_lock = threading.Lock()

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
        self.keypresser_target_key = Key.space  # Default to spacebar
        self.keypresser_target_key_display = "Space"
        self.keypresser_pressing = False
        self.keypresser_thread = None

        # Emergency Stop hotkey (defaults)
        self.emergency_stop_hotkey = Key.f9
        self.emergency_stop_hotkey_display = "F9"

        # Shared state
        self.mouse_controller = mouse.Controller()  # pynput mouse controller
        self.keyboard_controller = keyboard.Controller()  # pynput keyboard controller
        self.keyboard_listener = None
        self.hotkey_capture_listener = None
        self.listening_for_hotkey = False
        self.hotkey_target = None  # "clicker1", "clicker2", "keypresser", or "emergency_stop"

        # Rate limiting for hotkey presses (thread-safe)
        self.last_hotkey_time = {}
        self.hotkey_timing_lock = threading.Lock()
        self.hotkey_cooldown = 0.2  # 200ms cooldown between hotkey presses

        # Update settings
        self.auto_check_updates = True  # Default: check for updates on startup

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

        # Check for updates on startup (delay to let UI initialize)
        if self.auto_check_updates:
            self.window.after(2000, lambda: threading.Thread(
                target=self._check_for_updates, args=(True,), daemon=True).start())

    def _apply_theme(self):
        """Apply current theme to all widgets."""
        t = self._t
        self.window.configure(bg=t['bg'])
        self.style.configure('.', background=t['bg'], foreground=t['fg'],
                             fieldbackground=t['entry_bg'], borderwidth=0)
        self.style.configure('TFrame', background=t['bg'])
        self.style.configure('TLabel', background=t['bg'], foreground=t['fg'])
        self.style.configure('TButton', background=t['button_bg'], foreground=t['fg'], padding=(8, 4))
        self.style.map('TButton', background=[('active', t['accent'])])
        self.style.configure('TEntry', fieldbackground=t['entry_bg'], foreground=t['entry_fg'])
        self.style.configure('TCheckbutton', background=t['bg'], foreground=t['fg'])
        self.style.configure('TSeparator', background=t['sep'])

        # Update tk.Label status widgets if they exist
        for label_attr, is_active_attr in [
            ('status1_label', 'clicker1_clicking'),
            ('status2_label', 'clicker2_clicking'),
            ('keypresser_status_label', 'keypresser_pressing'),
        ]:
            label = getattr(self, label_attr, None)
            if label:
                active = getattr(self, is_active_attr, False)
                label.config(bg=t['bg'], fg=t['red'] if active else t['green'])

    def _toggle_theme(self):
        """Toggle between dark and light mode."""
        self.dark_mode = not self.dark_mode
        self._apply_theme()

    def _toggle_keypresser_section(self):
        """Toggle visibility of the keyboard presser section."""
        if self.kp_expanded:
            self.kp_frame.grid_remove()
            self.kp_toggle_btn.config(text="Keyboard Key Presser  [+]")
            self.kp_expanded = False
        else:
            self.kp_frame.grid()
            self.kp_toggle_btn.config(text="Keyboard Key Presser  [-]")
            self.kp_expanded = True

    def _safe_after(self, delay_ms, callback):
        """
        Safely schedule a callback on the main thread.
        Prevents crashes if window is destroyed before callback runs.
        """
        try:
            if self.window and self.window.winfo_exists():
                self.window.after(delay_ms, callback)
        except tk.TclError:
            # Window was destroyed, ignore the callback
            pass

    def _validate_interval(self, interval, default):
        """Validate interval is within acceptable bounds"""
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

            # Load hotkeys with type validation
            if 'clicker1_hotkey' in config:
                self.clicker1_hotkey = self._deserialize_key(config['clicker1_hotkey'])
                display = config.get('clicker1_hotkey_display', 'F6')
                self.clicker1_hotkey_display = display if isinstance(display, str) else 'F6'

            if 'clicker2_hotkey' in config:
                self.clicker2_hotkey = self._deserialize_key(config['clicker2_hotkey'])
                display = config.get('clicker2_hotkey_display', 'F7')
                self.clicker2_hotkey_display = display if isinstance(display, str) else 'F7'

            # Load keypresser settings
            self.keypresser_interval = self._validate_interval(
                config.get('keypresser_interval', self.keypresser_interval),
                DEFAULT_KEYPRESSER_INTERVAL
            )

            if 'keypresser_hotkey' in config:
                self.keypresser_hotkey = self._deserialize_key(config['keypresser_hotkey'])
                self.keypresser_hotkey_display = config.get('keypresser_hotkey_display', 'F8')

            if 'keypresser_target_key_pynput' in config:
                self.keypresser_target_key = self._deserialize_key(config['keypresser_target_key_pynput'])
                self.keypresser_target_key_display = config.get('keypresser_target_key_display', 'Space')

            # Load emergency stop hotkey
            if 'emergency_stop_hotkey' in config:
                self.emergency_stop_hotkey = self._deserialize_key(config['emergency_stop_hotkey'])
                self.emergency_stop_hotkey_display = config.get('emergency_stop_hotkey_display', 'F9')

            # Load auto update setting
            if 'auto_check_updates' in config:
                self.auto_check_updates = bool(config.get('auto_check_updates', True))

        except json.JSONDecodeError as e:
            print(f"Error: Config file is corrupted: {e}")
        except (IOError, OSError) as e:
            print(f"Error: Cannot read config file: {e}")
        except Exception as e:
            print(f"Error loading config: {e}")

    def save_config(self):
        """Save current configuration to JSON file, merging with existing
        settings so that keys written by the evdev version are preserved."""
        try:
            # Create config directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing config first to preserve keys from the other version
            existing_config = {}
            if self.config_path.exists():
                try:
                    with open(self.config_path, 'r') as f:
                        existing_config = json.load(f)
                except (json.JSONDecodeError, IOError, OSError):
                    existing_config = {}

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
                'keypresser_target_key_pynput': self._serialize_key(self.keypresser_target_key),
                'keypresser_target_key_display': self.keypresser_target_key_display,
                'emergency_stop_hotkey': self._serialize_key(self.emergency_stop_hotkey),
                'emergency_stop_hotkey_display': self.emergency_stop_hotkey_display,
                'auto_check_updates': self.auto_check_updates,
            }

            # Merge: existing values first, then overwrite with our values
            existing_config.update(config)

            with open(self.config_path, 'w') as f:
                json.dump(existing_config, f, indent=2)

        except Exception as e:
            print(f"Error saving config: {e}")

    def _serialize_key(self, key):
        """Convert a pynput key to a JSON-serializable format"""
        if hasattr(key, 'name'):
            return {'type': 'special', 'name': key.name}
        elif hasattr(key, 'char'):
            return {'type': 'char', 'char': key.char}
        else:
            return {'type': 'special', 'name': 'f6'}  # fallback

    def _deserialize_key(self, key_data):
        """Convert JSON data back to a pynput key"""
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
                try:
                    return KeyCode.from_char(char)
                except Exception:
                    return Key.f6  # fallback if KeyCode creation fails
            return Key.f6  # fallback if char is missing or invalid
        else:
            return Key.f6  # fallback

    def setup_ui(self):
        # Create menu bar
        menubar = tk.Menu(self.window)
        self.window.config(menu=menubar)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Check for Updates", command=self._check_for_updates_clicked)

        # Auto-check updates toggle
        self.auto_check_var = tk.BooleanVar(value=self.auto_check_updates)
        help_menu.add_checkbutton(
            label="Check for Updates on Startup",
            variable=self.auto_check_var,
            command=self._toggle_auto_check_updates
        )
        help_menu.add_separator()
        help_menu.add_command(label="Toggle Dark/Light Mode", command=self._toggle_theme)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self._show_about)

        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        title_label = ttk.Label(main_frame, text="Dual AutoClicker", font=("Arial", 18, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # Separator
        separator = ttk.Separator(main_frame, orient='vertical')
        separator.grid(row=1, column=1, rowspan=6, sticky='ns', padx=20)

        # ----- CLICKER 1 -----
        self._setup_clicker1_ui(main_frame, 0, 1)

        # ----- CLICKER 2 -----
        self._setup_clicker2_ui(main_frame, 2, 1)

        # ----- EMERGENCY STOP (always visible) -----
        hsep_emerg = ttk.Separator(main_frame, orient='horizontal')
        hsep_emerg.grid(row=8, column=0, columnspan=3, sticky='ew', pady=(20, 10))

        emergency_title = ttk.Label(main_frame, text="Emergency Stop All", font=("Arial", 11, "bold"), foreground="red")
        emergency_title.grid(row=9, column=0, columnspan=3)

        emerg_row = ttk.Frame(main_frame)
        emerg_row.grid(row=10, column=0, columnspan=3, pady=(5, 0))

        ttk.Label(emerg_row, text="Hotkey:").pack(side=tk.LEFT, padx=(0, 5))
        self.emergency_stop_button = ttk.Button(
            emerg_row,
            text=f"Current: {self.emergency_stop_hotkey_display}",
            command=lambda: self.start_hotkey_capture("emergency_stop"),
            width=15
        )
        self.emergency_stop_button.pack(side=tk.LEFT)

        # ----- COLLAPSIBLE KEYBOARD KEY PRESSER -----
        hseparator = ttk.Separator(main_frame, orient='horizontal')
        hseparator.grid(row=11, column=0, columnspan=3, sticky='ew', pady=(15, 5))

        self.kp_expanded = True
        self.kp_toggle_btn = ttk.Button(
            main_frame, text="Keyboard Key Presser  [-]",
            command=self._toggle_keypresser_section
        )
        self.kp_toggle_btn.grid(row=12, column=0, columnspan=3, pady=(0, 5))

        # Collapsible content frame
        self.kp_frame = ttk.Frame(main_frame)
        self.kp_frame.grid(row=13, column=0, columnspan=3, sticky='ew')

        # Build keypresser content inside the collapsible frame
        inner = self.kp_frame

        # Left side: target key + interval
        target_key_label = ttk.Label(inner, text="Key to Press:")
        target_key_label.grid(row=0, column=0, sticky=tk.W, pady=5)

        self.keypresser_target_key_button = ttk.Button(
            inner,
            text=f"Current: {self.keypresser_target_key_display}",
            command=self.select_target_key,
            width=20
        )
        self.keypresser_target_key_button.grid(row=1, column=0, sticky=tk.W, pady=5)

        kp_interval_label = ttk.Label(inner, text="Interval (seconds):")
        kp_interval_label.grid(row=2, column=0, sticky=tk.W, pady=(15, 5))

        self.keypresser_interval_var = tk.StringVar(value=str(self.keypresser_interval))
        kp_interval_entry = ttk.Entry(inner, textvariable=self.keypresser_interval_var, width=20)
        kp_interval_entry.grid(row=3, column=0, sticky=tk.W, pady=5)

        ttk.Button(
            inner, text="Apply Interval",
            command=self.apply_keypresser_interval
        ).grid(row=4, column=0, pady=5)

        # Separator
        separator2 = ttk.Separator(inner, orient='vertical')
        separator2.grid(row=0, column=1, rowspan=5, sticky='ns', padx=20)

        # Right side: hotkey + status
        kp_hotkey_label = ttk.Label(inner, text="Toggle Hotkey:")
        kp_hotkey_label.grid(row=0, column=2, sticky=tk.W, pady=5)

        self.keypresser_hotkey_button = ttk.Button(
            inner,
            text=f"Current: {self.keypresser_hotkey_display}",
            command=lambda: self.start_hotkey_capture("keypresser"),
            width=20
        )
        self.keypresser_hotkey_button.grid(row=1, column=2, sticky=tk.W, pady=5)

        kp_status_label = ttk.Label(inner, text="Status:")
        kp_status_label.grid(row=2, column=2, sticky=tk.W, pady=(15, 5))

        self.keypresser_status_var = tk.StringVar(value="Idle")
        self.keypresser_status_label = tk.Label(inner, textvariable=self.keypresser_status_var, font=("Arial", 10, "bold"), fg=self._t['green'], bg=self._t['bg'])
        self.keypresser_status_label.grid(row=3, column=2, pady=5)

        # Instructions at bottom (outside collapsible frame)
        instructions = ttk.Label(
            main_frame,
            text="Mouse clickers stop each other when started. Keyboard presser is independent.\nEmergency Stop will stop everything at once.",
            wraplength=650,
            justify=tk.CENTER,
            font=("Arial", 9, "italic")
        )
        instructions.grid(row=14, column=0, columnspan=3, pady=(15, 0))

        # (Check for Updates is available via Help menu)

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
        self.status1_label = tk.Label(parent, textvariable=self.status1_var, font=("Arial", 10, "bold"), fg=self._t['green'], bg=self._t['bg'])
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
        self.status2_label = tk.Label(parent, textvariable=self.status2_var, font=("Arial", 10, "bold"), fg=self._t['green'], bg=self._t['bg'])
        self.status2_label.grid(row=start_row+6, column=column, pady=(10, 5))

    def _apply_interval(self, interval_var, target_attr, name):
        """Consolidated interval application with validation"""
        try:
            interval_value = float(interval_var.get())
            if interval_value < MIN_INTERVAL:
                raise ValueError(f"Interval must be at least {MIN_INTERVAL}s (prevents system overload)")
            if interval_value > MAX_INTERVAL:
                raise ValueError(f"Interval must be at most {MAX_INTERVAL}s")
            # Acquire the appropriate lock before modifying interval
            lock_map = {
                'clicker1_interval': self.clicker1_lock,
                'clicker2_interval': self.clicker2_lock,
                'keypresser_interval': self.keypresser_lock,
            }
            lock = lock_map.get(target_attr)
            if not lock:
                setattr(self, target_attr, interval_value)
                self.save_config()
                messagebox.showinfo("Success", f"{name} interval updated to {interval_value}s")
                return
            with lock:
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
        dialog = tk.Toplevel(self.window)
        dialog.title("Select Key to Press")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.configure(bg=self._t['bg'])

        label = tk.Label(dialog, text="Press any key...", font=("Arial", 12),
                         bg=self._t['bg'], fg=self._t['fg'])
        label.pack(pady=40)

        def on_key_press(event):
            key_name = event.keysym
            # Convert tkinter keysym to pynput Key/KeyCode
            pynput_key = self._tk_keysym_to_pynput(key_name)
            if pynput_key is not None:
                self.keypresser_target_key = pynput_key
                self.keypresser_target_key_display = key_name.upper() if len(key_name) == 1 else key_name.capitalize()
                self.keypresser_target_key_button.config(text=f"Current: {self.keypresser_target_key_display}")
                self.save_config()
            else:
                messagebox.showwarning(
                    "Unsupported Key",
                    f"The key '{key_name}' is not supported.\n\n"
                    "Please choose a standard letter, number, function key, "
                    "or one of the recognized special keys."
                )
            dialog.destroy()

        dialog.bind("<Key>", on_key_press)
        dialog.focus_set()

    def _tk_keysym_to_pynput(self, keysym):
        """Convert tkinter keysym to pynput Key or KeyCode."""
        special_map = {
            'space': Key.space, 'Return': Key.enter, 'Tab': Key.tab,
            'Escape': Key.esc, 'BackSpace': Key.backspace, 'Delete': Key.delete,
            'Up': Key.up, 'Down': Key.down, 'Left': Key.left, 'Right': Key.right,
            'Home': Key.home, 'End': Key.end,
            'Page_Up': Key.page_up, 'Page_Down': Key.page_down,
            'Insert': Key.insert,
            'Shift_L': Key.shift_l, 'Shift_R': Key.shift_r,
            'Control_L': Key.ctrl_l, 'Control_R': Key.ctrl_r,
            'Alt_L': Key.alt_l, 'Alt_R': Key.alt_r,
        }

        if keysym in special_map:
            return special_map[keysym]

        # F keys
        if keysym.startswith('F') and keysym[1:].isdigit():
            f_num = int(keysym[1:])
            if 1 <= f_num <= 12:
                return getattr(Key, f'f{f_num}', None)

        # Single character (letter or digit)
        if len(keysym) == 1:
            try:
                return KeyCode.from_char(keysym.lower())
            except Exception:
                return None

        return None

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

            self.hotkey_capture_listener = None

            self.listening_for_hotkey = False
            target = self.hotkey_target

        # Set the new hotkey
        key_display = self.get_key_display_name(key)

        if target == "clicker1":
            self.clicker1_hotkey = key
            self.clicker1_hotkey_display = key_display
            self._safe_after(0, lambda: self.hotkey1_button.config(text=f"Current: {key_display}"))
        elif target == "clicker2":
            self.clicker2_hotkey = key
            self.clicker2_hotkey_display = key_display
            self._safe_after(0, lambda: self.hotkey2_button.config(text=f"Current: {key_display}"))
        elif target == "keypresser":
            self.keypresser_hotkey = key
            self.keypresser_hotkey_display = key_display
            self._safe_after(0, lambda: self.keypresser_hotkey_button.config(text=f"Current: {key_display}"))
        else:  # emergency_stop
            self.emergency_stop_hotkey = key
            self.emergency_stop_hotkey_display = key_display
            self._safe_after(0, lambda: self.emergency_stop_button.config(text=f"Current: {key_display}"))

        # Save the new configuration (thread-safe file write)
        self.save_config()

        # Restart the main keyboard listener on main thread safely
        self._safe_after(0, self.start_keyboard_listener)

        # Return False to tell pynput to stop this listener (avoids deadlock
        # from calling stop() inside the callback)
        return False

    def perform_click(self):
        """Perform a single left mouse click using pynput"""
        self.mouse_controller.click(mouse.Button.left, 1)

    def perform_keypress(self):
        """Perform a single key press using pynput"""
        self.keyboard_controller.press(self.keypresser_target_key)
        self.keyboard_controller.release(self.keypresser_target_key)

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
            # Rate limiting to prevent rapid toggling (thread-safe)
            current_time = time.time()
            key_str = str(key)

            with self.hotkey_timing_lock:
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
                self._safe_after(0, lambda: self.status1_var.set("Clicking..."))
                self._safe_after(0, lambda: self.status1_label.config(fg=self._t['red']))
                self.clicker1_thread = threading.Thread(target=self._click_loop1, daemon=True)
                self.clicker1_thread.start()

    def stop_clicker1(self):
        with self.clicker1_lock:
            if self.clicker1_clicking:
                self.clicker1_clicking = False
                self._safe_after(0, lambda: self.status1_var.set("Idle"))
                self._safe_after(0, lambda: self.status1_label.config(fg=self._t['green']))

    def start_clicker2(self):
        with self.clicker2_lock:
            if not self.clicker2_clicking:
                self.clicker2_clicking = True
                self._safe_after(0, lambda: self.status2_var.set("Clicking..."))
                self._safe_after(0, lambda: self.status2_label.config(fg=self._t['red']))
                self.clicker2_thread = threading.Thread(target=self._click_loop2, daemon=True)
                self.clicker2_thread.start()

    def stop_clicker2(self):
        with self.clicker2_lock:
            if self.clicker2_clicking:
                self.clicker2_clicking = False
                self._safe_after(0, lambda: self.status2_var.set("Idle"))
                self._safe_after(0, lambda: self.status2_label.config(fg=self._t['green']))

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
                self._safe_after(0, lambda: self.status1_var.set("Error"))
                self._safe_after(0, lambda: self.status1_label.config(fg=self._t['orange']))
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
                self._safe_after(0, lambda: self.status2_var.set("Error"))
                self._safe_after(0, lambda: self.status2_label.config(fg=self._t['orange']))
                break

            time.sleep(interval)

    def toggle_keypresser(self):
        with self.keypresser_lock:
            is_pressing = self.keypresser_pressing
        if is_pressing:
            self.stop_keypresser()
        else:
            self.start_keypresser()

    def start_keypresser(self):
        with self.keypresser_lock:
            if not self.keypresser_pressing:
                self.keypresser_pressing = True
                self._safe_after(0, lambda: self.keypresser_status_var.set("Pressing..."))
                self._safe_after(0, lambda: self.keypresser_status_label.config(fg=self._t['red']))
                self.keypresser_thread = threading.Thread(target=self._keypresser_loop, daemon=True)
                self.keypresser_thread.start()

    def stop_keypresser(self):
        with self.keypresser_lock:
            if self.keypresser_pressing:
                self.keypresser_pressing = False
                self._safe_after(0, lambda: self.keypresser_status_var.set("Idle"))
                self._safe_after(0, lambda: self.keypresser_status_label.config(fg=self._t['green']))

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
                self._safe_after(0, lambda: self.keypresser_status_var.set("Error"))
                self._safe_after(0, lambda: self.keypresser_status_label.config(fg=self._t['orange']))
                break

            time.sleep(interval)

    def emergency_stop_all(self):
        """Stop all autoclickers and key presser immediately"""
        self.stop_clicker1()
        self.stop_clicker2()
        self.stop_keypresser()

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
        for name, thread in [("Clicker 1", self.clicker1_thread),
                             ("Clicker 2", self.clicker2_thread),
                             ("Key presser", self.keypresser_thread)]:
            if thread and thread.is_alive():
                thread.join(timeout=1.0)
                if thread.is_alive():
                    print(f"Warning: {name} thread did not exit cleanly")
        self.window.destroy()

    # Update feature methods
    def _show_about(self):
        """Show about dialog with clickable link and image."""
        t = self._t
        dialog = tk.Toplevel(self.window)
        dialog.title("About")
        dialog.configure(bg=t['bg'])
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text=f"Dual AutoClicker + Key Presser",
                 font=("Arial", 14, "bold"), bg=t['bg'], fg=t['fg']
                 ).pack(pady=(20, 5))

        tk.Label(dialog, text=f"v{__version__}",
                 font=("Arial", 10), bg=t['bg'], fg=t['muted']
                 ).pack(pady=(0, 10))

        tk.Label(dialog, text="A cross-platform dual autoclicker\nwith keyboard presser and configurable hotkeys.",
                 justify=tk.CENTER, bg=t['bg'], fg=t['fg']
                 ).pack(pady=(0, 10))

        # Clickable GitHub link
        link = tk.Label(dialog, text="github.com/jj-repository/autoclicker",
                        fg=t['link'], bg=t['bg'], cursor="hand2",
                        font=("Arial", 10, "underline"))
        link.pack(pady=(0, 15))
        link.bind("<Button-1>", lambda e: __import__('webbrowser').open("https://github.com/jj-repository/autoclicker"))

        # Takodachi image
        if self._about_image:
            tk.Label(dialog, image=self._about_image, bg=t['bg']).pack(pady=(5, 5))

        tk.Label(dialog, text="by JJ", font=("Arial", 11, "italic"),
                 bg=t['bg'], fg=t['muted']).pack(pady=(0, 15))

        ttk.Button(dialog, text="OK", command=dialog.destroy).pack(pady=(0, 20))

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_reqwidth()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{x}+{y}")

    def _version_newer(self, latest, current):
        """
        Compare version strings to check if latest is newer than current.

        Handles semantic versioning with pre-release suffixes:
        - "1.4.0" > "1.3.0"
        - "1.4.0" > "1.4.0-beta"
        - "1.4.0-beta2" > "1.4.0-beta1"
        """
        def parse_version(version_str):
            """Parse version string into comparable tuple."""
            if not version_str or not isinstance(version_str, str):
                return (0, 0, 0, '', 0)

            # Remove 'v' prefix if present
            version_str = version_str.lstrip('v')

            # Split by hyphen to separate main version from pre-release
            if '-' in version_str:
                main_part, pre_release = version_str.split('-', 1)
            else:
                main_part, pre_release = version_str, ''

            # Parse main version parts
            parts = []
            for part in main_part.split('.'):
                try:
                    parts.append(int(part))
                except ValueError:
                    # Handle non-numeric parts by extracting leading digits
                    digits = ''
                    for c in part:
                        if c.isdigit():
                            digits += c
                        else:
                            break
                    parts.append(int(digits) if digits else 0)

            # Pad to at least 3 parts
            while len(parts) < 3:
                parts.append(0)

            # Parse pre-release number if present (e.g., "beta2" -> 2)
            pre_release_num = 0
            if pre_release:
                digits = ''.join(c for c in pre_release if c.isdigit())
                pre_release_num = int(digits) if digits else 0

            # Return tuple: (major, minor, patch, pre_release_str, pre_release_num)
            # Empty pre_release string sorts AFTER any pre-release (stable > beta)
            return (parts[0], parts[1], parts[2], pre_release == '', pre_release_num)

        try:
            latest_parsed = parse_version(latest)
            current_parsed = parse_version(current)
            return latest_parsed > current_parsed
        except Exception:
            return False

    def _check_for_updates_clicked(self):
        """Handle Check for Updates menu click."""
        threading.Thread(target=self._check_for_updates, args=(False,), daemon=True).start()

    def _toggle_auto_check_updates(self):
        """Toggle automatic update checking on startup."""
        self.auto_check_updates = self.auto_check_var.get()
        self.save_config()

    def _check_for_updates(self, silent=True):
        """Check GitHub for new version."""
        import urllib.request
        import urllib.error

        try:
            request = urllib.request.Request(
                GITHUB_API_LATEST,
                headers={'User-Agent': f'DualAutoClicker/{__version__}'}
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())

            latest_version = data.get('tag_name', '').lstrip('v')

            if not latest_version:
                raise ValueError("No version tag found in release")

            if self._version_newer(latest_version, __version__):
                self._safe_after(0, lambda: self._show_update_dialog(latest_version, data))
            elif not silent:
                self._safe_after(0, lambda: messagebox.showinfo(
                    "Up to Date",
                    f"You are running the latest version (v{__version__})."
                ))

        except urllib.error.URLError as e:
            if not silent:
                self._safe_after(0, lambda: messagebox.showerror(
                    "Update Error",
                    f"Failed to check for updates:\n{e}"
                ))
        except Exception as e:
            if not silent:
                self._safe_after(0, lambda: messagebox.showerror(
                    "Update Error",
                    f"Failed to check for updates:\n{e}"
                ))

    def _show_update_dialog(self, latest_version, release_data):
        """Show update available dialog with options."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Update Available")
        dialog.transient(self.window)
        dialog.grab_set()
        dialog.geometry("400x200")
        dialog.resizable(False, False)

        msg = f"A new version is available!\n\nCurrent: v{__version__}\nLatest: v{latest_version}\n\nWould you like to update?"
        ttk.Label(dialog, text=msg, justify=tk.CENTER, wraplength=350).pack(pady=20)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        def update_now():
            dialog.destroy()
            threading.Thread(target=self._apply_update, args=(release_data,), daemon=True).start()

        def open_releases():
            dialog.destroy()
            import webbrowser
            webbrowser.open(GITHUB_RELEASES_URL)

        ttk.Button(btn_frame, text="Update Now", command=update_now).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Open Releases", command=open_releases).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Later", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def _apply_update(self, release_data):
        """
        Download and apply update with SHA256 checksum verification.

        Security measures:
        - SHA256 checksum verification BEFORE any file operations
        - Atomic file replacement using os.replace()
        - Temp file created in same directory as target for atomic replace
        - Backup created before replacement
        - All file operations are verified
        """
        import urllib.request
        import urllib.error
        import shutil
        import hashlib
        import os as os_module

        tmp_path = None

        try:
            tag_name = release_data.get('tag_name', 'main')
            download_url = f"{GITHUB_RAW_URL}/{tag_name}/autoclicker.py"
            checksum_url = f"{GITHUB_RAW_URL}/{tag_name}/autoclicker.py.sha256"

            headers = {'User-Agent': f'DualAutoClicker/{__version__}'}

            # First, download and validate the checksum file
            expected_checksum = None
            try:
                checksum_request = urllib.request.Request(checksum_url, headers=headers)
                with urllib.request.urlopen(checksum_request, timeout=30) as response:
                    checksum_content = response.read().decode().strip()
                    # Validate checksum file is not empty
                    if not checksum_content:
                        raise ValueError("Checksum file is empty")
                    # Format: "sha256hash  filename" or just "sha256hash"
                    parts = checksum_content.split()
                    if not parts:
                        raise ValueError("Checksum file contains no valid hash")
                    expected_checksum = parts[0].lower()
                    # Validate checksum format (must be exactly 64 hex characters)
                    if len(expected_checksum) != 64 or not all(c in '0123456789abcdef' for c in expected_checksum):
                        raise ValueError("Invalid checksum format - not a valid SHA256 hash")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    # Checksum file doesn't exist - abort for security
                    self._safe_after(0, lambda: messagebox.showwarning(
                        "Update Aborted",
                        "No checksum file found for this release.\n\n"
                        "This means the update cannot be verified for integrity.\n\n"
                        "For your security, updates without checksums are not allowed.\n\n"
                        "Please download the update manually from:\n"
                        f"{GITHUB_RELEASES_URL}"
                    ))
                    return
                raise

            # Download the update file to memory first with size validation
            request = urllib.request.Request(download_url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                # Check Content-Length header before reading
                content_length = response.headers.get('Content-Length')
                if content_length:
                    try:
                        size = int(content_length)
                        if size > MAX_DOWNLOAD_SIZE:
                            self._safe_after(0, lambda: messagebox.showerror(
                                "Update Failed",
                                f"Update file too large ({size / 1024 / 1024:.1f}MB).\n"
                                f"Maximum allowed: {MAX_DOWNLOAD_SIZE / 1024 / 1024:.1f}MB\n\n"
                                "This may indicate a compromised update. Please download manually."
                            ))
                            return
                    except ValueError:
                        pass  # Invalid Content-Length, proceed with caution

                # Read with size limit
                content = response.read(MAX_DOWNLOAD_SIZE + 1)
                if len(content) > MAX_DOWNLOAD_SIZE:
                    self._safe_after(0, lambda: messagebox.showerror(
                        "Update Failed",
                        f"Update file exceeds maximum size ({MAX_DOWNLOAD_SIZE / 1024 / 1024:.1f}MB).\n\n"
                        "This may indicate a compromised update. Please download manually."
                    ))
                    return

            # CRITICAL: Verify checksum BEFORE any file operations
            sha256_hash = hashlib.sha256(content).hexdigest().lower()

            if sha256_hash != expected_checksum:
                self._safe_after(0, lambda: messagebox.showerror(
                    "Security Error",
                    "CHECKSUM VERIFICATION FAILED!\n\n"
                    f"Expected: {expected_checksum}\n"
                    f"Got: {sha256_hash}\n\n"
                    "The downloaded file may have been tampered with.\n"
                    "Update has been aborted for your safety.\n\n"
                    "Please report this issue on GitHub."
                ))
                return

            # Checksum verified - now perform atomic file operations
            current_script = Path(__file__).resolve()
            script_dir = current_script.parent
            backup_path = current_script.with_suffix('.py.backup')

            # Create temp file in SAME directory as target for atomic replace
            # (os.replace() is only atomic within the same filesystem)
            tmp_path = script_dir / f".autoclicker_update_{os_module.getpid()}.tmp"

            # Write verified content to temp file
            try:
                with open(tmp_path, 'wb') as f:
                    f.write(content)
                    f.flush()
                    os_module.fsync(f.fileno())  # Ensure data is written to disk
            except (IOError, OSError) as write_error:
                self._safe_after(0, lambda: messagebox.showerror(
                    "Update Failed",
                    f"Failed to write update file:\n{write_error}"
                ))
                return

            # Verify the written file matches (defense against write errors)
            try:
                with open(tmp_path, 'rb') as f:
                    written_hash = hashlib.sha256(f.read()).hexdigest().lower()
                if written_hash != expected_checksum:
                    raise ValueError("Written file checksum doesn't match")
            except Exception as verify_error:
                self._safe_after(0, lambda: messagebox.showerror(
                    "Update Failed",
                    f"Failed to verify written file:\n{verify_error}"
                ))
                return

            # Create backup of current script
            try:
                shutil.copy2(current_script, backup_path)
            except (IOError, OSError) as backup_error:
                self._safe_after(0, lambda: messagebox.showerror(
                    "Update Failed",
                    f"Failed to create backup:\n{backup_error}"
                ))
                return

            # Replace the current script with the update
            try:
                if sys.platform == 'win32':
                    # On Windows, os.replace() can fail when the target file
                    # is locked.  Windows does allow renaming an in-use file,
                    # so rename the current script out of the way first, then
                    # move the new file in.  If the move fails, restore the
                    # original from the .old rename.
                    old_path = current_script.with_suffix('.py.old')
                    try:
                        # Remove any leftover .old file from a previous update
                        if old_path.exists():
                            old_path.unlink()
                        os_module.rename(str(current_script), str(old_path))
                    except OSError as rename_error:
                        self._safe_after(0, lambda: messagebox.showerror(
                            "Update Failed",
                            f"Failed to rename current script:\n{rename_error}\n\n"
                            f"Your backup is safe at:\n{backup_path}"
                        ))
                        return
                    try:
                        os_module.rename(str(tmp_path), str(current_script))
                        tmp_path = None  # Mark as successfully moved
                    except OSError as move_error:
                        # Restore the original file from .old
                        try:
                            os_module.rename(str(old_path), str(current_script))
                        except OSError:
                            pass  # backup_path still has a copy
                        self._safe_after(0, lambda: messagebox.showerror(
                            "Update Failed",
                            f"Failed to move update into place:\n{move_error}\n\n"
                            f"Your backup is safe at:\n{backup_path}"
                        ))
                        return
                else:
                    # POSIX: os.replace() is atomic
                    os_module.replace(str(tmp_path), str(current_script))
                    tmp_path = None  # Mark as successfully moved (no cleanup needed)
            except (IOError, OSError) as replace_error:
                self._safe_after(0, lambda: messagebox.showerror(
                    "Update Failed",
                    f"Failed to apply update:\n{replace_error}\n\n"
                    f"Your backup is safe at:\n{backup_path}"
                ))
                return

            self._safe_after(0, lambda: messagebox.showinfo(
                "Update Complete",
                "Update downloaded and verified successfully!\n\n"
                f"SHA256: {sha256_hash[:16]}...{sha256_hash[-8:]}\n"
                f"Backup saved to: {backup_path.name}\n\n"
                "Please restart the application to apply the update."
            ))

        except urllib.error.URLError as e:
            self._safe_after(0, lambda: messagebox.showerror(
                "Update Failed",
                f"Network error while downloading update:\n{e}"
            ))
        except Exception as e:
            self._safe_after(0, lambda: messagebox.showerror(
                "Update Failed",
                f"Unexpected error during update:\n{type(e).__name__}: {e}"
            ))
        finally:
            # Clean up temp file if it still exists (failed update)
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink()
                except OSError as cleanup_error:
                    print(f"Warning: Failed to clean up temp file {tmp_path}: {cleanup_error}")

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    app = DualAutoClicker()
    app.run()

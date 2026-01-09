#!/usr/bin/env python3
"""
Dual AutoClicker - Cross-Platform Version (pynput)

This version uses pynput for mouse control and keyboard hotkey detection.
Works on Windows, macOS, and Linux (X11).

Use this version when:
- Running on Windows or macOS
- Running on Linux with X11 (not Wayland)
- You only need mouse auto-clicking

For Linux with Wayland or games that don't detect pynput clicks,
use autoclicker_evdev.py instead (requires root/uinput permissions).
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
from pathlib import Path
from pynput import keyboard, mouse
from pynput.keyboard import Key, KeyCode

__version__ = "1.4.0"

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


class DualAutoClicker:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Dual AutoClicker")
        self.window.geometry("500x420")
        self.window.resizable(False, False)

        # Config file path
        self.config_path = Path.home() / ".config" / "autoclicker" / "config.json"

        # Thread locks for thread-safe state access
        self.clicker1_lock = threading.Lock()
        self.clicker2_lock = threading.Lock()
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

        # Shared state
        self.mouse_controller = mouse.Controller()  # pynput mouse controller
        self.keyboard_listener = None
        self.hotkey_capture_listener = None
        self.listening_for_hotkey = False
        self.hotkey_target = None  # "clicker1" or "clicker2"

        # Rate limiting for hotkey presses
        self.last_hotkey_time = {}
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

        # Load saved configuration
        self.load_config()

        self.setup_ui()
        self.start_keyboard_listener()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Check for updates on startup (delay to let UI initialize)
        if self.auto_check_updates:
            self.window.after(2000, lambda: threading.Thread(
                target=self._check_for_updates, args=(True,), daemon=True).start())

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
                'auto_check_updates': self.auto_check_updates,
            }

            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)

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
                return KeyCode.from_char(char)
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

        # Instructions at bottom
        instructions = ttk.Label(
            main_frame,
            text="Starting one autoclicker will automatically stop the other",
            wraplength=650,
            justify=tk.CENTER,
            font=("Arial", 9, "italic")
        )
        instructions.grid(row=7, column=0, columnspan=3, pady=(60, 0))

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

    def _apply_interval(self, interval_var, target_attr, name):
        """Consolidated interval application with validation"""
        try:
            interval_value = float(interval_var.get())
            if interval_value < MIN_INTERVAL:
                raise ValueError(f"Interval must be at least {MIN_INTERVAL}s (prevents system overload)")
            if interval_value > MAX_INTERVAL:
                raise ValueError(f"Interval must be at most {MAX_INTERVAL}s")
            # Acquire the appropriate lock before modifying interval
            lock = self.clicker1_lock if target_attr == 'clicker1_interval' else self.clicker2_lock
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

    def start_hotkey_capture(self, target):
        with self.hotkey_capture_lock:
            if self.listening_for_hotkey:
                return

            self.listening_for_hotkey = True
            self.hotkey_target = target

        if target == "clicker1":
            self.hotkey1_button.config(text="Press a key...")
        else:
            self.hotkey2_button.config(text="Press a key...")

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
            # Schedule UI update on main thread safely
            self._safe_after(0, lambda: self.hotkey1_button.config(text=f"Current: {key_display}"))
        else:
            self.clicker2_hotkey = key
            self.clicker2_hotkey_display = key_display
            # Schedule UI update on main thread safely
            self._safe_after(0, lambda: self.hotkey2_button.config(text=f"Current: {key_display}"))

        # Save the new configuration (thread-safe file write)
        self.save_config()

        # Restart the main keyboard listener on main thread safely
        self._safe_after(0, self.start_keyboard_listener)

    def perform_click(self):
        """Perform a single left mouse click using pynput"""
        self.mouse_controller.click(mouse.Button.left, 1)

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

            # Check clicker 1 hotkey
            if key == self.clicker1_hotkey:
                self.toggle_clicker1()
            # Check clicker 2 hotkey
            elif key == self.clicker2_hotkey:
                self.toggle_clicker2()
        except AttributeError:
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
                self._safe_after(0, lambda: self.status1_var.set("Error"))
                self._safe_after(0, lambda: self.status1_label.config(fg="orange"))
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
                self._safe_after(0, lambda: self.status2_label.config(fg="orange"))
                break

            time.sleep(interval)

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
        self.stop_keyboard_listener()
        if self.hotkey_capture_listener:
            try:
                self.hotkey_capture_listener.stop()
            except Exception:
                pass
        # Wait for clicker threads to finish to ensure clean shutdown
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
        self.window.destroy()

    # Update feature methods
    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "About",
            f"Dual AutoClicker v{__version__}\n\n"
            "A cross-platform dual autoclicker with configurable hotkeys.\n\n"
            "https://github.com/jj-repository/autoclicker"
        )

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
                    # Format: "sha256hash  filename" or just "sha256hash"
                    expected_checksum = checksum_content.split()[0].lower()
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

            # Download the update file to memory first
            request = urllib.request.Request(download_url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                content = response.read()

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

            # ATOMIC REPLACE: os.replace() is atomic on POSIX systems
            # and on Windows when source and dest are on the same filesystem
            try:
                os_module.replace(str(tmp_path), str(current_script))
                tmp_path = None  # Mark as successfully moved (no cleanup needed)
            except (IOError, OSError) as replace_error:
                self._safe_after(0, lambda: messagebox.showerror(
                    "Update Failed",
                    f"Failed to apply update (atomic replace failed):\n{replace_error}\n\n"
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

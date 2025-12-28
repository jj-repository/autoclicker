#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import os
from pathlib import Path
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
from evdev import UInput, ecodes as e

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
        self.virtual_mouse = None  # Will be initialized when needed
        self.keyboard_listener = None
        self.hotkey_capture_listener = None
        self.listening_for_hotkey = False
        self.hotkey_target = None  # "clicker1" or "clicker2"

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

        # Load saved configuration
        self.load_config()

        self.setup_ui()
        self.start_keyboard_listener()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

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

            # Load hotkeys
            if 'clicker1_hotkey' in config:
                self.clicker1_hotkey = self._deserialize_key(config['clicker1_hotkey'])
                self.clicker1_hotkey_display = config.get('clicker1_hotkey_display', 'F6')

            if 'clicker2_hotkey' in config:
                self.clicker2_hotkey = self._deserialize_key(config['clicker2_hotkey'])
                self.clicker2_hotkey_display = config.get('clicker2_hotkey_display', 'F7')

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
        if key_data['type'] == 'special':
            # Get the Key attribute by name
            return getattr(Key, key_data['name'], Key.f6)
        elif key_data['type'] == 'char':
            return KeyCode.from_char(key_data['char'])
        else:
            return Key.f6  # fallback

    def setup_ui(self):
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
        self.hotkey_capture_listener = keyboard.Listener(on_press=self.capture_hotkey)
        self.hotkey_capture_listener.start()

    def capture_hotkey(self, key):
        if not self.listening_for_hotkey:
            return

        # Stop the capture listener
        if self.hotkey_capture_listener:
            self.hotkey_capture_listener.stop()
            self.hotkey_capture_listener = None

        self.listening_for_hotkey = False

        # Set the new hotkey
        key_display = self.get_key_display_name(key)

        if self.hotkey_target == "clicker1":
            self.clicker1_hotkey = key
            self.clicker1_hotkey_display = key_display
            self.hotkey1_button.config(text=f"Current: {key_display}")
        else:
            self.clicker2_hotkey = key
            self.clicker2_hotkey_display = key_display
            self.hotkey2_button.config(text=f"Current: {key_display}")

        # Save the new configuration
        self.save_config()

        # Restart the main keyboard listener
        self.start_keyboard_listener()

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
                print("You may need to run with: sudo python3 autoclicker.py")
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
        if self.clicker1_clicking:
            # Stop clicker 1
            self.stop_clicker1()
        else:
            # Start clicker 1 (and stop clicker 2 if running)
            self.stop_clicker2()
            self.start_clicker1()

    def toggle_clicker2(self):
        if self.clicker2_clicking:
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

    def start_keyboard_listener(self):
        self.keyboard_listener = keyboard.Listener(on_press=self.on_hotkey_press)
        self.keyboard_listener.start()

    def stop_keyboard_listener(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()

    def on_closing(self):
        self.stop_clicker1()
        self.stop_clicker2()
        self.stop_keyboard_listener()
        if self.hotkey_capture_listener:
            self.hotkey_capture_listener.stop()
        if self.virtual_mouse:
            self.virtual_mouse.close()
        self.window.destroy()

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    app = DualAutoClicker()
    app.run()

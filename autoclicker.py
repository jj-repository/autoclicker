#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from pynput import mouse, keyboard
from pynput.keyboard import Key, KeyCode


class DualAutoClicker:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Dual AutoClicker")
        self.window.geometry("700x380")
        self.window.resizable(False, False)

        # Clicker 1 state
        self.clicker1_hotkey = Key.f6
        self.clicker1_hotkey_display = "F6"
        self.clicker1_interval = 0.1
        self.clicker1_clicking = False
        self.clicker1_thread = None

        # Clicker 2 state
        self.clicker2_hotkey = Key.f7
        self.clicker2_hotkey_display = "F7"
        self.clicker2_interval = 0.5
        self.clicker2_clicking = False
        self.clicker2_thread = None

        # Shared state
        self.mouse_controller = mouse.Controller()
        self.keyboard_listener = None
        self.hotkey_capture_listener = None
        self.listening_for_hotkey = False
        self.hotkey_target = None  # "clicker1" or "clicker2"

        # UI elements
        self.interval1_var = None
        self.interval2_var = None
        self.hotkey1_button = None
        self.hotkey2_button = None
        self.status1_var = None
        self.status2_var = None

        self.setup_ui()
        self.start_keyboard_listener()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

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
        instructions.grid(row=7, column=0, columnspan=3, pady=(20, 0))

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
        status_label = ttk.Label(parent, text="Status:")
        status_label.grid(row=start_row+6, column=column, sticky=tk.W, pady=(10, 5))

        self.status1_var = tk.StringVar(value="Idle")
        status_value = ttk.Label(parent, textvariable=self.status1_var, font=("Arial", 10, "bold"))
        status_value.grid(row=start_row+7, column=column, sticky=tk.W, pady=5)

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
        status_label = ttk.Label(parent, text="Status:")
        status_label.grid(row=start_row+6, column=column, sticky=tk.W, pady=(10, 5))

        self.status2_var = tk.StringVar(value="Idle")
        status_value = ttk.Label(parent, textvariable=self.status2_var, font=("Arial", 10, "bold"))
        status_value.grid(row=start_row+7, column=column, sticky=tk.W, pady=5)

    def apply_interval1(self):
        try:
            interval_value = float(self.interval1_var.get())
            if interval_value <= 0:
                raise ValueError("Interval must be positive")
            self.clicker1_interval = interval_value
            messagebox.showinfo("Success", f"Clicker 1 interval updated to {interval_value}s")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid interval: {e}")

    def apply_interval2(self):
        try:
            interval_value = float(self.interval2_var.get())
            if interval_value <= 0:
                raise ValueError("Interval must be positive")
            self.clicker2_interval = interval_value
            messagebox.showinfo("Success", f"Clicker 2 interval updated to {interval_value}s")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid interval: {e}")

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

        # Restart the main keyboard listener
        self.start_keyboard_listener()

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
        try:
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
        if not self.clicker1_clicking:
            self.clicker1_clicking = True
            self.status1_var.set("Clicking...")
            self.clicker1_thread = threading.Thread(target=self._click_loop1, daemon=True)
            self.clicker1_thread.start()

    def stop_clicker1(self):
        if self.clicker1_clicking:
            self.clicker1_clicking = False
            self.status1_var.set("Idle")

    def start_clicker2(self):
        if not self.clicker2_clicking:
            self.clicker2_clicking = True
            self.status2_var.set("Clicking...")
            self.clicker2_thread = threading.Thread(target=self._click_loop2, daemon=True)
            self.clicker2_thread.start()

    def stop_clicker2(self):
        if self.clicker2_clicking:
            self.clicker2_clicking = False
            self.status2_var.set("Idle")

    def _click_loop1(self):
        while self.clicker1_clicking:
            self.mouse_controller.click(mouse.Button.left, 1)
            time.sleep(self.clicker1_interval)

    def _click_loop2(self):
        while self.clicker2_clicking:
            self.mouse_controller.click(mouse.Button.left, 1)
            time.sleep(self.clicker2_interval)

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
        self.window.destroy()

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    app = DualAutoClicker()
    app.run()

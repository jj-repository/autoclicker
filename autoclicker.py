#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from pynput import mouse, keyboard
from pynput.keyboard import Key, KeyCode


class ClickerInstance:
    """Represents a single autoclicker instance"""
    def __init__(self, name, default_hotkey, default_hotkey_display, default_interval):
        self.name = name
        self.hotkey = default_hotkey
        self.hotkey_display = default_hotkey_display
        self.interval = default_interval
        self.clicking = False
        self.click_thread = None
        self.mouse_controller = mouse.Controller()

        # Callback to be called when this clicker starts
        self.on_start_callback = None

    def start_clicking(self):
        if not self.clicking:
            # Notify that we're starting (this will stop the other clicker)
            if self.on_start_callback:
                self.on_start_callback(self)

            self.clicking = True
            self.click_thread = threading.Thread(target=self._click_loop, daemon=True)
            self.click_thread.start()

    def stop_clicking(self):
        if self.clicking:
            self.clicking = False

    def toggle_clicking(self):
        if self.clicking:
            self.stop_clicking()
        else:
            self.start_clicking()

    def _click_loop(self):
        while self.clicking:
            self.mouse_controller.click(mouse.Button.left, 1)
            time.sleep(self.interval)


class DualAutoClicker:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Dual AutoClicker")
        self.window.geometry("700x380")
        self.window.resizable(False, False)

        # Create two clicker instances
        self.clicker1 = ClickerInstance("Clicker 1", Key.f6, "F6", 0.1)
        self.clicker2 = ClickerInstance("Clicker 2", Key.f7, "F7", 0.5)

        # Set callbacks so starting one stops the other
        self.clicker1.on_start_callback = self._on_clicker_start
        self.clicker2.on_start_callback = self._on_clicker_start

        self.keyboard_listener = None
        self.hotkey_capture_listener = None
        self.listening_for_hotkey = False
        self.hotkey_target_clicker = None  # Which clicker is being configured

        # UI elements (will be set in setup_ui)
        self.interval1_var = None
        self.interval2_var = None
        self.hotkey1_button = None
        self.hotkey2_button = None
        self.status1_var = None
        self.status2_var = None

        self.setup_ui()
        self.start_keyboard_listener()

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _on_clicker_start(self, starting_clicker):
        """Called when a clicker starts - stops the other one"""
        if starting_clicker == self.clicker1:
            self.clicker2.stop_clicking()
            self.status2_var.set("Idle")
        else:
            self.clicker1.stop_clicking()
            self.status1_var.set("Idle")

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
        self._setup_clicker_ui(main_frame, self.clicker1, 0, 1)

        # ----- CLICKER 2 -----
        self._setup_clicker_ui(main_frame, self.clicker2, 2, 1)

        # Instructions at bottom
        instructions = ttk.Label(
            main_frame,
            text="Starting one autoclicker will automatically stop the other",
            wraplength=650,
            justify=tk.CENTER,
            font=("Arial", 9, "italic")
        )
        instructions.grid(row=7, column=0, columnspan=3, pady=(20, 0))

    def _setup_clicker_ui(self, parent, clicker, column, start_row):
        """Setup UI for a single clicker"""
        # Title
        title = ttk.Label(parent, text=clicker.name, font=("Arial", 14, "bold"))
        title.grid(row=start_row, column=column, pady=(0, 15))

        # Interval
        interval_label = ttk.Label(parent, text="Interval (seconds):")
        interval_label.grid(row=start_row+1, column=column, sticky=tk.W, pady=5)

        interval_var = tk.StringVar(value=str(clicker.interval))
        interval_entry = ttk.Entry(parent, textvariable=interval_var, width=20)
        interval_entry.grid(row=start_row+2, column=column, sticky=tk.W, pady=5)

        # Apply interval button
        apply_button = ttk.Button(
            parent,
            text="Apply Interval",
            command=lambda: self.apply_interval(clicker, interval_var)
        )
        apply_button.grid(row=start_row+3, column=column, pady=5)

        # Hotkey
        hotkey_label = ttk.Label(parent, text="Toggle Hotkey:")
        hotkey_label.grid(row=start_row+4, column=column, sticky=tk.W, pady=(10, 5))

        hotkey_button = ttk.Button(
            parent,
            text=f"Current: {clicker.hotkey_display}",
            command=lambda: self.start_hotkey_capture(clicker, hotkey_button),
            width=20
        )
        hotkey_button.grid(row=start_row+5, column=column, sticky=tk.W, pady=5)

        # Status
        status_label = ttk.Label(parent, text="Status:")
        status_label.grid(row=start_row+6, column=column, sticky=tk.W, pady=(10, 5))

        status_var = tk.StringVar(value="Idle")
        status_value = ttk.Label(parent, textvariable=status_var, font=("Arial", 10, "bold"))
        status_value.grid(row=start_row+7, column=column, sticky=tk.W, pady=5)

        # Store references
        if clicker == self.clicker1:
            self.interval1_var = interval_var
            self.hotkey1_button = hotkey_button
            self.status1_var = status_var
        else:
            self.interval2_var = interval_var
            self.hotkey2_button = hotkey_button
            self.status2_var = status_var

    def apply_interval(self, clicker, interval_var):
        try:
            interval_value = float(interval_var.get())
            if interval_value <= 0:
                raise ValueError("Interval must be positive")
            clicker.interval = interval_value
            messagebox.showinfo("Success", f"{clicker.name} interval updated to {interval_value}s")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid interval: {e}")

    def start_hotkey_capture(self, clicker, button):
        if self.listening_for_hotkey:
            return

        self.listening_for_hotkey = True
        self.hotkey_target_clicker = clicker
        button.config(text="Press a key...")

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

        # Set the new hotkey for the target clicker
        clicker = self.hotkey_target_clicker
        clicker.hotkey = key
        clicker.hotkey_display = self.get_key_display_name(key)

        # Update the appropriate button
        if clicker == self.clicker1:
            self.hotkey1_button.config(text=f"Current: {clicker.hotkey_display}")
        else:
            self.hotkey2_button.config(text=f"Current: {clicker.hotkey_display}")

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
            # Check if it matches clicker 1's hotkey
            if key == self.clicker1.hotkey:
                self.clicker1.toggle_clicking()
                if self.clicker1.clicking:
                    self.status1_var.set("Clicking...")
                else:
                    self.status1_var.set("Idle")

            # Check if it matches clicker 2's hotkey
            elif key == self.clicker2.hotkey:
                self.clicker2.toggle_clicking()
                if self.clicker2.clicking:
                    self.status2_var.set("Clicking...")
                else:
                    self.status2_var.set("Idle")
        except AttributeError:
            pass

    def start_keyboard_listener(self):
        self.keyboard_listener = keyboard.Listener(on_press=self.on_hotkey_press)
        self.keyboard_listener.start()

    def stop_keyboard_listener(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()

    def on_closing(self):
        self.clicker1.stop_clicking()
        self.clicker2.stop_clicking()
        self.stop_keyboard_listener()
        if self.hotkey_capture_listener:
            self.hotkey_capture_listener.stop()
        self.window.destroy()

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    app = DualAutoClicker()
    app.run()

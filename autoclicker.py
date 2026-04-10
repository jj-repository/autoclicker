#!/usr/bin/env python3
"""
Dual AutoClicker + Key Presser — Cross-Platform Version (pynput)
================================================================
PyQt6 GUI using JJ GUI-Template style.

Uses pynput for mouse control, keyboard key pressing, and hotkey detection.
Works on Windows, macOS, and Linux (X11).

For Linux with Wayland or games that don't detect pynput input,
use autoclicker_evdev.py instead (requires root/uinput permissions).
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal, QObject
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QIcon,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pynput import keyboard, mouse
from pynput.keyboard import Key, KeyCode

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

# ── App identity ──────────────────────────────────────────────────────
APP_NAME = "AutoClicker"
__version__ = "1.12"
WINDOW_SIZE = (560, 820)

# ── Color palette ─────────────────────────────────────────────────────
GREEN = ("#2e7d32", "#388e3c")
BLUE = ("#1565c0", "#1976d2")
YELLOW = ("#f9a825", "#fbc02d")
RED = ("#c62828", "#e53935")

# ── Status colors ────────────────────────────────────────────────────
STATUS_IDLE_COLOR = "#4ec9b0"
STATUS_ACTIVE_COLOR = "#f44747"
STATUS_ERROR_COLOR = "#ce9178"

# ── Update Constants ──────────────────────────────────────────────────
GITHUB_REPO = "jj-repository/autoclicker"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}"

MAX_DOWNLOAD_SIZE = 5 * 1024 * 1024
MAX_API_RESPONSE_SIZE = 1 * 1024 * 1024
MAX_METADATA_RESPONSE_SIZE = 512 * 1024


# ── Stylesheets ───────────────────────────────────────────────────────

_LIGHT_STYLE = """
QWidget { background-color: #f0f0f0; color: #1e1e1e; }
QGroupBox { border: 1px solid #bbb; border-radius: 4px; margin-top: 8px; padding-top: 14px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #1e1e1e; }
QTabWidget::pane { border: 1px solid #bbb; }
QTabBar::tab { background: #e0e0e0; padding: 6px 14px; border: 1px solid #bbb;
               border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background: #f0f0f0; }
QTabBar::tab:!selected { margin-top: 2px; }
QTabBar::tab:disabled { background: transparent; border: none; min-width: 40px; max-width: 40px; }
QLineEdit { background: #ffffff; color: #1e1e1e;
            border: 1px solid #bbb; border-radius: 3px; padding: 2px; }
QScrollArea { border: none; }
QPushButton { background: #e0e0e0; color: #1e1e1e; border: 1px solid #bbb;
              border-radius: 3px; padding: 5px 12px; }
QPushButton:hover { background: #d0d0d0; }
QCheckBox { color: #1e1e1e; }
QCheckBox::indicator { width: 14px; height: 14px; border: 2px solid #888;
                       border-radius: 3px; background: #ffffff; }
QCheckBox::indicator:checked { background: #2e7d32; border-color: #2e7d32; }
QCheckBox::indicator:unchecked:hover { border-color: #555; }
QLabel { color: #1e1e1e; }
QMessageBox { background-color: #f0f0f0; }
QToolTip { background: #ffffcc; color: #1e1e1e; border: 1px solid #bbb; }
"""


def _make_checkbox_images() -> tuple[str, str]:
    """Generate dark-mode checked/unchecked checkbox PNGs."""
    d = tempfile.mkdtemp(prefix=f"{APP_NAME.lower()}_")
    atexit.register(shutil.rmtree, d, ignore_errors=True)
    size = 18

    unchecked = QPixmap(size, size)
    unchecked.fill(QColor(0, 0, 0, 0))
    p = QPainter(unchecked)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(136, 136, 136), 2))
    p.setBrush(QColor(45, 45, 45))
    p.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)
    p.end()
    unchecked_path = os.path.join(d, "cb_unchecked.png")
    unchecked.save(unchecked_path)

    checked = QPixmap(size, size)
    checked.fill(QColor(0, 0, 0, 0))
    p = QPainter(checked)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(46, 125, 50))
    p.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)
    pen = QPen(QColor(255, 255, 255), 2.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(4, 9)
    path.lineTo(7.5, 13)
    path.lineTo(14, 5)
    p.drawPath(path)
    p.end()
    checked_path = os.path.join(d, "cb_checked.png")
    checked.save(checked_path)

    return checked_path, unchecked_path


def _build_dark_style() -> str:
    """Build dark stylesheet with generated checkbox images."""
    checked, unchecked = _make_checkbox_images()
    checked = checked.replace("\\", "/")
    unchecked = unchecked.replace("\\", "/")
    return f"""
QWidget {{ background-color: #1e1e1e; color: #dcdcdc; }}
QGroupBox {{ border: 1px solid #444; border-radius: 4px; margin-top: 8px; padding-top: 14px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #dcdcdc; }}
QTabWidget::pane {{ border: 1px solid #444; }}
QTabBar::tab {{ background: #2d2d2d; padding: 6px 14px; border: 1px solid #444;
               border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }}
QTabBar::tab:selected {{ background: #1e1e1e; }}
QTabBar::tab:!selected {{ margin-top: 2px; }}
QTabBar::tab:disabled {{ background: transparent; border: none; min-width: 40px; max-width: 40px; }}
QLineEdit {{ background: #2d2d2d; color: #dcdcdc;
            border: 1px solid #555; border-radius: 3px; padding: 2px; }}
QScrollArea {{ border: none; }}
QPushButton {{ background: #333; color: #dcdcdc; border: 1px solid #555;
              border-radius: 3px; padding: 5px 12px; }}
QPushButton:hover {{ background: #444; }}
QCheckBox {{ color: #dcdcdc; spacing: 6px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; }}
QCheckBox::indicator:unchecked {{ image: url({unchecked}); }}
QCheckBox::indicator:checked {{ image: url({checked}); }}
QLabel {{ color: #dcdcdc; }}
QMessageBox {{ background-color: #1e1e1e; }}
QToolTip {{ background: #2d2d2d; color: #dcdcdc; border: 1px solid #555; }}
"""


# ── App settings persistence (dark mode) ─────────────────────────────

_settings_cache: dict | None = None
_DARK_STYLE_CACHE: str | None = None


def _settings_path() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME.lower() / "settings.json"


def _load_settings() -> dict:
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache
    p = _settings_path()
    if p.is_file():
        try:
            _settings_cache = json.loads(p.read_text())
            return _settings_cache
        except (json.JSONDecodeError, OSError):
            pass
    _settings_cache = {}
    return _settings_cache


def _save_settings(data: dict):
    global _settings_cache
    _settings_cache = data
    p = _settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


# ── Window icon ───────────────────────────────────────────────────────


def _make_icon() -> QIcon:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    for name in ("icon.ico", "icon.png"):
        p = base_dir / name
        if p.exists():
            return QIcon(str(p))
    px = QPixmap(64, 64)
    px.fill(QColor(46, 125, 50))
    p = QPainter(px)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255))
    p.drawRoundedRect(16, 16, 32, 32, 6, 6)
    p.end()
    return QIcon(px)


# ── Colored button helper ─────────────────────────────────────────────


def _colored_btn(
    text: str, colors: tuple[str, str], bold: bool = True, text_color: str = "white"
) -> QPushButton:
    btn = QPushButton(text)
    weight = "bold" if bold else "normal"
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {colors[0]}; color: {text_color};"
        f" font-weight: {weight}; }}"
        f"QPushButton:hover {{ background-color: {colors[1]}; }}"
    )
    return btn


# ── Thread-safe UI updater ────────────────────────────────────────────


class _UiUpdater(QObject):
    """Emit from any thread; slot runs on main thread."""

    requested = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.requested.connect(self._run)

    @staticmethod
    def _run(fn):
        try:
            fn()
        except RuntimeError:
            pass  # Widget already deleted


# ── Key capture dialog (for selecting key-presser target) ─────────────


class KeyCaptureDialog(QDialog):
    """Modal dialog that captures a single key press."""

    _SPECIAL_MAP: dict = {
        Qt.Key.Key_Space: (Key.space, "Space"),
        Qt.Key.Key_Return: (Key.enter, "Enter"),
        Qt.Key.Key_Enter: (Key.enter, "Enter"),
        Qt.Key.Key_Tab: (Key.tab, "Tab"),
        Qt.Key.Key_Escape: (Key.esc, "Escape"),
        Qt.Key.Key_Backspace: (Key.backspace, "Backspace"),
        Qt.Key.Key_Delete: (Key.delete, "Delete"),
        Qt.Key.Key_Up: (Key.up, "Up"),
        Qt.Key.Key_Down: (Key.down, "Down"),
        Qt.Key.Key_Left: (Key.left, "Left"),
        Qt.Key.Key_Right: (Key.right, "Right"),
        Qt.Key.Key_Home: (Key.home, "Home"),
        Qt.Key.Key_End: (Key.end, "End"),
        Qt.Key.Key_PageUp: (Key.page_up, "PageUp"),
        Qt.Key.Key_PageDown: (Key.page_down, "PageDown"),
        Qt.Key.Key_Insert: (Key.insert, "Insert"),
        Qt.Key.Key_Shift: (Key.shift_l, "Shift"),
        Qt.Key.Key_Control: (Key.ctrl_l, "Ctrl"),
        Qt.Key.Key_Alt: (Key.alt_l, "Alt"),
    }
    for _i in range(1, 13):
        _SPECIAL_MAP[getattr(Qt.Key, f"Key_F{_i}")] = (getattr(Key, f"f{_i}"), f"F{_i}")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Key to Press")
        self.setFixedSize(300, 150)
        self.setModal(True)
        self.captured_key = None
        self.captured_display = None

        layout = QVBoxLayout(self)
        layout.addStretch()
        lbl = QLabel("Press any key...")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 14px;")
        layout.addWidget(lbl)
        layout.addStretch()

    def keyPressEvent(self, event: QKeyEvent):
        qt_key = event.key()
        text = event.text()

        if qt_key in self._SPECIAL_MAP:
            self.captured_key, self.captured_display = self._SPECIAL_MAP[qt_key]
            self.accept()
            return

        if text and len(text) == 1:
            try:
                self.captured_key = KeyCode.from_char(text.lower())
                self.captured_display = text.upper()
                self.accept()
                return
            except (ValueError, TypeError):
                pass

        QMessageBox.warning(
            self,
            "Unsupported Key",
            "This key is not supported.\n\n"
            "Please choose a letter, number, function key, "
            "or a recognized special key.",
        )
        self.reject()


# ═══════════════════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════════════════


class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.setWindowIcon(_make_icon())
        self.resize(*WINDOW_SIZE)
        self.setMinimumSize(480, 500)

        # Thread-safe UI updater
        self._ui_updater = _UiUpdater()

        # ── Autoclicker state ─────────────────────────────────
        self.clicker1_lock = threading.Lock()
        self.clicker2_lock = threading.Lock()
        self.keypresser_lock = threading.Lock()
        self.hotkey_capture_lock = threading.Lock()

        self.clicker1_hotkey = Key.f6
        self.clicker1_hotkey_display = "F6"
        self.clicker1_interval = DEFAULT_CLICKER1_INTERVAL
        self.clicker1_clicking = False
        self.clicker1_thread = None
        self.clicker1_stop = threading.Event()
        self.clicker1_stop.set()

        self.clicker2_hotkey = Key.f7
        self.clicker2_hotkey_display = "F7"
        self.clicker2_interval = DEFAULT_CLICKER2_INTERVAL
        self.clicker2_clicking = False
        self.clicker2_thread = None
        self.clicker2_stop = threading.Event()
        self.clicker2_stop.set()

        # Key Presser
        self.keypresser_hotkey = Key.f8
        self.keypresser_hotkey_display = "F8"
        self.keypresser_interval = DEFAULT_KEYPRESSER_INTERVAL
        self.keypresser_target_key = Key.space
        self.keypresser_target_key_display = "Space"
        self.keypresser_pressing = False
        self.keypresser_thread = None
        self.keypresser_stop = threading.Event()
        self.keypresser_stop.set()

        # Emergency Stop
        self.emergency_stop_hotkey = Key.f9
        self.emergency_stop_hotkey_display = "F9"

        # Controllers
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()
        self.keyboard_listener = None
        self.listening_for_hotkey = False
        self.hotkey_target = None

        # Rate limiting
        self.last_hotkey_time: dict = {}
        self.hotkey_timing_lock = threading.Lock()
        self.hotkey_cooldown = 0.2

        # Update settings
        self.auto_check_updates = True

        # Load saved config (populates state from disk before building UI)
        self._load_config()

        # ── Build UI ──────────────────────────────────────────
        central = QWidget()
        outer = QVBoxLayout(central)

        self._tabs = QTabWidget()
        self._build_main_tab()

        # Spacer tab (visual gap before Settings / Help)
        self._tabs.addTab(QWidget(), "")
        spacer_idx = self._tabs.count() - 1
        self._tabs.setTabEnabled(spacer_idx, False)
        bar = self._tabs.tabBar()
        bar.setTabButton(spacer_idx, bar.ButtonPosition.LeftSide, None)
        bar.setTabButton(spacer_idx, bar.ButtonPosition.RightSide, None)

        self._build_settings_tab()
        self._build_help_tab()

        outer.addWidget(self._tabs)
        self.setCentralWidget(central)

        # Apply theme (needs _dark_mode_cb created by _build_settings_tab)
        self._apply_theme()

        self.start_keyboard_listener()

        # Auto-check updates on startup
        if self.auto_check_updates:
            QTimer.singleShot(
                2000,
                lambda: threading.Thread(
                    target=self._check_for_updates, args=(True,), daemon=True
                ).start(),
            )

    # ── Thread-safe UI scheduling ─────────────────────────────

    def _safe_after(self, delay_ms, callback):
        """Schedule callback on the main thread (thread-safe)."""
        try:
            if delay_ms <= 0:
                self._ui_updater.requested.emit(callback)
            else:
                self._ui_updater.requested.emit(lambda: QTimer.singleShot(delay_ms, callback))
        except RuntimeError:
            pass

    # ── Scrollable tab helper ─────────────────────────────────

    @staticmethod
    def _scroll_tab(page: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidget(page)
        sa.setWidgetResizable(True)
        sa.setFrameShape(QScrollArea.Shape.NoFrame)
        return sa

    # ══════════════════════════════════════════════════════════════
    #  Main Tab
    # ══════════════════════════════════════════════════════════════

    def _build_main_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        # ── Clickers side by side ─────────────────────────────
        clickers_row = QHBoxLayout()

        c1_group = QGroupBox("Clicker 1")
        c1 = QVBoxLayout()
        c1.addWidget(QLabel("Interval (seconds):"))
        c1_int = QHBoxLayout()
        self._interval1_edit = QLineEdit(str(self.clicker1_interval))
        self._interval1_edit.setFixedWidth(100)
        c1_int.addWidget(self._interval1_edit)
        c1_apply = QPushButton("Apply")
        c1_apply.clicked.connect(self._apply_interval1)
        c1_int.addWidget(c1_apply)
        c1_int.addStretch()
        c1.addLayout(c1_int)
        c1.addSpacing(8)
        c1.addWidget(QLabel("Toggle Hotkey:"))
        self._hotkey1_btn = QPushButton(f"Current: {self.clicker1_hotkey_display}")
        self._hotkey1_btn.clicked.connect(lambda: self.start_hotkey_capture("clicker1"))
        c1.addWidget(self._hotkey1_btn)
        c1.addSpacing(8)
        c1.addWidget(QLabel("Status:"))
        self._status1_label = QLabel("Idle")
        self._status1_label.setStyleSheet("font-weight: bold; color: #4ec9b0;")
        c1.addWidget(self._status1_label)
        c1.addStretch()
        c1_group.setLayout(c1)
        clickers_row.addWidget(c1_group)

        c2_group = QGroupBox("Clicker 2")
        c2 = QVBoxLayout()
        c2.addWidget(QLabel("Interval (seconds):"))
        c2_int = QHBoxLayout()
        self._interval2_edit = QLineEdit(str(self.clicker2_interval))
        self._interval2_edit.setFixedWidth(100)
        c2_int.addWidget(self._interval2_edit)
        c2_apply = QPushButton("Apply")
        c2_apply.clicked.connect(self._apply_interval2)
        c2_int.addWidget(c2_apply)
        c2_int.addStretch()
        c2.addLayout(c2_int)
        c2.addSpacing(8)
        c2.addWidget(QLabel("Toggle Hotkey:"))
        self._hotkey2_btn = QPushButton(f"Current: {self.clicker2_hotkey_display}")
        self._hotkey2_btn.clicked.connect(lambda: self.start_hotkey_capture("clicker2"))
        c2.addWidget(self._hotkey2_btn)
        c2.addSpacing(8)
        c2.addWidget(QLabel("Status:"))
        self._status2_label = QLabel("Idle")
        self._status2_label.setStyleSheet("font-weight: bold; color: #4ec9b0;")
        c2.addWidget(self._status2_label)
        c2.addStretch()
        c2_group.setLayout(c2)
        clickers_row.addWidget(c2_group)

        layout.addLayout(clickers_row)

        # ── Emergency Stop ────────────────────────────────────
        emerg_group = QGroupBox("Emergency Stop All")
        emerg_group.setStyleSheet(
            "QGroupBox { border-color: #c62828; }"
            "QGroupBox::title { color: #e53935; font-weight: bold; }"
        )
        emerg = QHBoxLayout()
        emerg.addWidget(QLabel("Hotkey:"))
        self._emergency_stop_btn = QPushButton(f"Current: {self.emergency_stop_hotkey_display}")
        self._emergency_stop_btn.clicked.connect(
            lambda: self.start_hotkey_capture("emergency_stop")
        )
        emerg.addWidget(self._emergency_stop_btn)
        emerg.addStretch()
        emerg_group.setLayout(emerg)
        layout.addWidget(emerg_group)

        # ── Keyboard Key Presser ──────────────────────────────
        kp_group = QGroupBox("Keyboard Key Presser")
        kp_cols = QHBoxLayout()

        kp_left = QVBoxLayout()
        kp_left.addWidget(QLabel("Key to Press:"))
        self._kp_target_btn = QPushButton(f"Current: {self.keypresser_target_key_display}")
        self._kp_target_btn.clicked.connect(self._select_target_key)
        kp_left.addWidget(self._kp_target_btn)
        kp_left.addSpacing(8)
        kp_left.addWidget(QLabel("Interval (seconds):"))
        kp_int = QHBoxLayout()
        self._kp_interval_edit = QLineEdit(str(self.keypresser_interval))
        self._kp_interval_edit.setFixedWidth(100)
        kp_int.addWidget(self._kp_interval_edit)
        kp_apply = QPushButton("Apply")
        kp_apply.clicked.connect(self._apply_keypresser_interval)
        kp_int.addWidget(kp_apply)
        kp_int.addStretch()
        kp_left.addLayout(kp_int)
        kp_left.addStretch()
        kp_cols.addLayout(kp_left)

        kp_right = QVBoxLayout()
        kp_right.addWidget(QLabel("Toggle Hotkey:"))
        self._kp_hotkey_btn = QPushButton(f"Current: {self.keypresser_hotkey_display}")
        self._kp_hotkey_btn.clicked.connect(lambda: self.start_hotkey_capture("keypresser"))
        kp_right.addWidget(self._kp_hotkey_btn)
        kp_right.addSpacing(8)
        kp_right.addWidget(QLabel("Status:"))
        self._kp_status_label = QLabel("Idle")
        self._kp_status_label.setStyleSheet("font-weight: bold; color: #4ec9b0;")
        kp_right.addWidget(self._kp_status_label)
        kp_right.addStretch()
        kp_cols.addLayout(kp_right)

        kp_group.setLayout(kp_cols)
        layout.addWidget(kp_group)

        # ── Instructions ──────────────────────────────────────
        instructions = QLabel(
            "Mouse clickers stop each other when started. "
            "Keyboard presser is independent.\n"
            "Emergency Stop will stop everything at once."
        )
        instructions.setWordWrap(True)
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions.setStyleSheet("color: gray; font-style: italic; font-size: 11px;")
        layout.addWidget(instructions)

        layout.addStretch()
        self._tabs.addTab(self._scroll_tab(page), "AutoClicker")

    # ══════════════════════════════════════════════════════════════
    #  Settings Tab
    # ══════════════════════════════════════════════════════════════

    def _build_settings_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        repo_label = QLabel(
            f'<a href="https://github.com/{GITHUB_REPO}">github.com/{GITHUB_REPO}</a>'
        )
        repo_label.setOpenExternalLinks(True)
        repo_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(repo_label)
        layout.addSpacing(12)

        update_btn = QPushButton("Check for Updates")
        update_btn.setToolTip("Check GitHub for a new version")
        update_btn.clicked.connect(self._check_for_updates_clicked)
        layout.addWidget(update_btn)
        layout.addSpacing(8)

        self._auto_update_cb = QCheckBox("Check for Updates on Startup")
        self._auto_update_cb.setChecked(self.auto_check_updates)
        self._auto_update_cb.stateChanged.connect(self._toggle_auto_check_updates)
        layout.addWidget(self._auto_update_cb)
        layout.addSpacing(12)

        self._dark_mode_cb = QCheckBox("Dark Mode")
        self._dark_mode_cb.setChecked(_load_settings().get("dark_mode", True))
        self._dark_mode_cb.stateChanged.connect(self._on_dark_mode_toggled)
        layout.addWidget(self._dark_mode_cb)

        # Mascot
        layout.addSpacing(16)
        base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
        tako_path = base_dir / "takodachi.png"
        if tako_path.exists():
            tako_pix = QPixmap(str(tako_path))
            if not tako_pix.isNull():
                if tako_pix.width() > 120 or tako_pix.height() > 120:
                    tako_pix = tako_pix.scaled(
                        120,
                        120,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                tako_label = QLabel()
                tako_label.setPixmap(tako_pix)
                tako_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(tako_label)

        by_label = QLabel("by JJ")
        by_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        by_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(by_label)

        layout.addStretch()
        self._tabs.addTab(self._scroll_tab(page), "Settings")

    # ══════════════════════════════════════════════════════════════
    #  Help Tab
    # ══════════════════════════════════════════════════════════════

    def _build_help_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel(f"{APP_NAME} Help")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        layout.addSpacing(8)

        btns = QHBoxLayout()
        readme_btn = _colored_btn("Readme", BLUE)
        readme_btn.setToolTip("Open documentation on GitHub")
        readme_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(f"https://github.com/{GITHUB_REPO}#readme"))
        )
        btns.addWidget(readme_btn)

        report_btn = _colored_btn("Report Bug", YELLOW, text_color="#1e1e1e")
        report_btn.setToolTip("Report an issue on GitHub")
        report_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(f"https://github.com/{GITHUB_REPO}/issues/new"))
        )
        btns.addWidget(report_btn)

        btns.addStretch()
        layout.addLayout(btns)
        layout.addSpacing(12)

        # Separator
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #444;")
        layout.addWidget(sep)
        layout.addSpacing(8)

        help_sections = [
            (
                "Getting Started",
                "AutoClicker provides two independent mouse clickers and a "
                "keyboard key presser. Each can be toggled on/off via "
                "configurable global hotkeys.",
            ),
            (
                "Mouse Clickers",
                "Clicker 1 and Clicker 2 click the left mouse button at the "
                "configured interval. Starting one automatically stops the other. "
                "Set the interval in seconds and click Apply, or change the "
                "toggle hotkey.",
            ),
            (
                "Keyboard Key Presser",
                "Automatically presses a selected keyboard key at the configured "
                "interval. Click the 'Key to Press' button and press the desired "
                "key. The presser runs independently from the mouse clickers.",
            ),
            (
                "Emergency Stop",
                "Press the Emergency Stop hotkey to immediately stop all "
                "clickers and the key presser.",
            ),
            (
                "Hotkeys",
                "Default hotkeys:\n"
                "  F6 — Toggle Clicker 1\n"
                "  F7 — Toggle Clicker 2\n"
                "  F8 — Toggle Key Presser\n"
                "  F9 — Emergency Stop All\n\n"
                "Click any hotkey button in the main tab and press a new key "
                "to rebind.",
            ),
            (
                "Settings",
                "Toggle dark/light mode, enable or disable automatic update "
                "checks on startup, and check for updates manually.",
            ),
        ]
        for sec_title, sec_desc in help_sections:
            t_lbl = QLabel(sec_title)
            t_lbl.setStyleSheet("font-size: 13px; font-weight: bold;")
            layout.addWidget(t_lbl)
            d_lbl = QLabel(sec_desc)
            d_lbl.setWordWrap(True)
            d_lbl.setStyleSheet("color: gray; font-size: 11px; margin-left: 8px;")
            layout.addWidget(d_lbl)
            layout.addSpacing(6)

        layout.addStretch()
        self._tabs.addTab(self._scroll_tab(page), "Help")

    # ══════════════════════════════════════════════════════════════
    #  Theme
    # ══════════════════════════════════════════════════════════════

    def _on_dark_mode_toggled(self, _state):
        data = _load_settings()
        data["dark_mode"] = self._dark_mode_cb.isChecked()
        _save_settings(data)
        self._apply_theme()

    def _apply_theme(self):
        if self._dark_mode_cb.isChecked():
            global _DARK_STYLE_CACHE
            if _DARK_STYLE_CACHE is None:
                _DARK_STYLE_CACHE = _build_dark_style()
            QApplication.instance().setStyleSheet(_DARK_STYLE_CACHE)
        else:
            QApplication.instance().setStyleSheet(_LIGHT_STYLE)

    # ══════════════════════════════════════════════════════════════
    #  Config load / save
    # ══════════════════════════════════════════════════════════════

    @property
    def _config_path(self) -> Path:
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", str(Path.home()))
            return Path(appdata) / "autoclicker" / "config.json"
        return Path.home() / ".config" / "autoclicker" / "config.json"

    def _load_config(self):
        """Load saved configuration from JSON file."""
        if not self._config_path.exists():
            return
        try:
            config = json.loads(self._config_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error loading config: {e}")
            return

        self.clicker1_interval = self._validate_interval(
            config.get("clicker1_interval"), DEFAULT_CLICKER1_INTERVAL
        )
        self.clicker2_interval = self._validate_interval(
            config.get("clicker2_interval"), DEFAULT_CLICKER2_INTERVAL
        )

        if "clicker1_hotkey" in config:
            self.clicker1_hotkey = self._deserialize_key(config["clicker1_hotkey"])
            d = config.get("clicker1_hotkey_display", "F6")
            self.clicker1_hotkey_display = d if isinstance(d, str) else "F6"
        if "clicker2_hotkey" in config:
            self.clicker2_hotkey = self._deserialize_key(config["clicker2_hotkey"])
            d = config.get("clicker2_hotkey_display", "F7")
            self.clicker2_hotkey_display = d if isinstance(d, str) else "F7"

        self.keypresser_interval = self._validate_interval(
            config.get("keypresser_interval"), DEFAULT_KEYPRESSER_INTERVAL
        )
        if "keypresser_hotkey" in config:
            self.keypresser_hotkey = self._deserialize_key(config["keypresser_hotkey"])
            self.keypresser_hotkey_display = config.get("keypresser_hotkey_display", "F8")
        if "keypresser_target_key_pynput" in config:
            self.keypresser_target_key = self._deserialize_key(
                config["keypresser_target_key_pynput"]
            )
            self.keypresser_target_key_display = config.get(
                "keypresser_target_key_display", "Space"
            )

        if "emergency_stop_hotkey" in config:
            self.emergency_stop_hotkey = self._deserialize_key(config["emergency_stop_hotkey"])
            self.emergency_stop_hotkey_display = config.get("emergency_stop_hotkey_display", "F9")

        if "auto_check_updates" in config:
            self.auto_check_updates = bool(config.get("auto_check_updates", True))

        # Restore window geometry (supports old tkinter format + new dict)
        geo = config.get("window_geometry")

        def _clamp(val, lo, hi):
            return max(lo, min(hi, val))

        if isinstance(geo, str) and "x" in geo:
            parts = geo.replace("+", "x").split("x")
            try:
                if len(parts) >= 2:
                    self.resize(
                        _clamp(int(parts[0]), 200, 4000),
                        _clamp(int(parts[1]), 200, 4000),
                    )
                if len(parts) >= 4:
                    self.move(
                        _clamp(int(parts[2]), -2000, 8000),
                        _clamp(int(parts[3]), -2000, 8000),
                    )
            except (ValueError, IndexError):
                pass
        elif isinstance(geo, dict):
            self.resize(
                _clamp(geo.get("w", WINDOW_SIZE[0]), 200, 4000),
                _clamp(geo.get("h", WINDOW_SIZE[1]), 200, 4000),
            )
            if "x" in geo and "y" in geo:
                self.move(
                    _clamp(geo["x"], -2000, 8000),
                    _clamp(geo["y"], -2000, 8000),
                )

    def _save_config(self):
        """Save current configuration to JSON file, merging with existing."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            existing: dict = {}
            if self._config_path.exists():
                try:
                    existing = json.loads(self._config_path.read_text())
                except (json.JSONDecodeError, OSError):
                    pass

            geo = self.geometry()
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
                "keypresser_target_key_pynput": self._serialize_key(self.keypresser_target_key),
                "keypresser_target_key_display": self.keypresser_target_key_display,
                "emergency_stop_hotkey": self._serialize_key(self.emergency_stop_hotkey),
                "emergency_stop_hotkey_display": self.emergency_stop_hotkey_display,
                "auto_check_updates": self.auto_check_updates,
                "window_geometry": {
                    "w": geo.width(),
                    "h": geo.height(),
                    "x": geo.x(),
                    "y": geo.y(),
                },
            }
            existing.update(config)
            tmp = self._config_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(existing, indent=2))
            os.replace(str(tmp), str(self._config_path))
        except (OSError, ValueError, TypeError) as e:
            print(f"Error saving config: {e}")

    _serialize_key = staticmethod(serialize_key)
    _deserialize_key = staticmethod(deserialize_key)
    _validate_interval = staticmethod(validate_interval)

    # ══════════════════════════════════════════════════════════════
    #  Interval application
    # ══════════════════════════════════════════════════════════════

    def _apply_interval(self, edit: QLineEdit, target_attr: str, name: str):
        try:
            val = float(edit.text())
            if val < MIN_INTERVAL:
                raise ValueError(
                    f"Interval must be at least {MIN_INTERVAL}s (prevents system overload)"
                )
            if val > MAX_INTERVAL:
                raise ValueError(f"Interval must be at most {MAX_INTERVAL}s")
            lock_map = {
                "clicker1_interval": self.clicker1_lock,
                "clicker2_interval": self.clicker2_lock,
                "keypresser_interval": self.keypresser_lock,
            }
            lock = lock_map.get(target_attr)
            if lock:
                with lock:
                    setattr(self, target_attr, val)
            else:
                setattr(self, target_attr, val)
            self._save_config()
            QMessageBox.information(self, "Success", f"{name} interval updated to {val}s")
        except ValueError as e:
            QMessageBox.critical(self, "Error", f"Invalid interval: {e}")

    def _apply_interval1(self):
        self._apply_interval(self._interval1_edit, "clicker1_interval", "Clicker 1")

    def _apply_interval2(self):
        self._apply_interval(self._interval2_edit, "clicker2_interval", "Clicker 2")

    def _apply_keypresser_interval(self):
        self._apply_interval(self._kp_interval_edit, "keypresser_interval", "Key Presser")

    # ══════════════════════════════════════════════════════════════
    #  Target key selection
    # ══════════════════════════════════════════════════════════════

    def _select_target_key(self):
        dlg = KeyCaptureDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.captured_key:
            self.keypresser_target_key = dlg.captured_key
            self.keypresser_target_key_display = dlg.captured_display
            self._kp_target_btn.setText(f"Current: {dlg.captured_display}")
            self._save_config()

    # ══════════════════════════════════════════════════════════════
    #  Hotkey capture (pynput-based)
    # ══════════════════════════════════════════════════════════════

    def start_hotkey_capture(self, target):
        with self.hotkey_capture_lock:
            if self.listening_for_hotkey:
                return
            self.listening_for_hotkey = True
            self.hotkey_target = target

        btn_map = {
            "clicker1": self._hotkey1_btn,
            "clicker2": self._hotkey2_btn,
            "keypresser": self._kp_hotkey_btn,
            "emergency_stop": self._emergency_stop_btn,
        }
        btn = btn_map.get(target)
        if btn:
            btn.setText("Press a key...")

    def _on_key_press(self, key):
        """Unified key press handler: capture mode or normal hotkey dispatch."""
        if self.listening_for_hotkey:
            with self.hotkey_capture_lock:
                if not self.listening_for_hotkey:
                    self.on_hotkey_press(key)
                    return
                self.listening_for_hotkey = False
                target = self.hotkey_target
                # Process capture inline
                key_display = self.get_key_display_name(key)
                attr_map = {
                    "clicker1": (
                        "clicker1_hotkey",
                        "clicker1_hotkey_display",
                        "_hotkey1_btn",
                    ),
                    "clicker2": (
                        "clicker2_hotkey",
                        "clicker2_hotkey_display",
                        "_hotkey2_btn",
                    ),
                    "keypresser": (
                        "keypresser_hotkey",
                        "keypresser_hotkey_display",
                        "_kp_hotkey_btn",
                    ),
                    "emergency_stop": (
                        "emergency_stop_hotkey",
                        "emergency_stop_hotkey_display",
                        "_emergency_stop_btn",
                    ),
                }
                if target in attr_map:
                    key_attr, display_attr, btn_attr = attr_map[target]
                    setattr(self, key_attr, key)
                    setattr(self, display_attr, key_display)
                    btn = getattr(self, btn_attr)
                    self._safe_after(
                        0,
                        lambda b=btn, d=key_display: b.setText(f"Current: {d}"),
                    )
                self._save_config()
                return
        # Normal hotkey dispatch
        self.on_hotkey_press(key)

    get_key_display_name = staticmethod(_core_get_key_display_name)

    # ══════════════════════════════════════════════════════════════
    #  Clicking / Key pressing logic
    # ══════════════════════════════════════════════════════════════

    def perform_click(self):
        self.mouse_controller.click(mouse.Button.left, 1)

    def perform_keypress(self, target_key):
        self.keyboard_controller.press(target_key)
        self.keyboard_controller.release(target_key)

    def on_hotkey_press(self, key):
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

    def _set_status(self, label, text, color):
        self._safe_after(
            0,
            lambda: (
                label.setText(text),
                label.setStyleSheet(f"font-weight: bold; color: {color};"),
            ),
        )

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
            self._set_status(self._status1_label, "Clicking...", STATUS_ACTIVE_COLOR)

            def on_error(e):
                print(f"Error in clicker 1: {e}")
                with self.clicker1_lock:
                    self.clicker1_clicking = False
                self._set_status(self._status1_label, "Error", STATUS_ERROR_COLOR)

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
            self._set_status(self._status1_label, "Idle", STATUS_IDLE_COLOR)

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
            self._set_status(self._status2_label, "Clicking...", STATUS_ACTIVE_COLOR)

            def on_error(e):
                print(f"Error in clicker 2: {e}")
                with self.clicker2_lock:
                    self.clicker2_clicking = False
                self._set_status(self._status2_label, "Error", STATUS_ERROR_COLOR)

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
            self._set_status(self._status2_label, "Idle", STATUS_IDLE_COLOR)

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
            self._set_status(self._kp_status_label, "Pressing...", STATUS_ACTIVE_COLOR)

            def on_error(e):
                print(f"Error in key presser: {e}")
                with self.keypresser_lock:
                    self.keypresser_pressing = False
                self._set_status(self._kp_status_label, "Error", STATUS_ERROR_COLOR)

            self.keypresser_thread = threading.Thread(
                target=action_loop,
                args=(
                    self.keypresser_stop,
                    lambda: self.keypresser_interval,
                    lambda: self.perform_keypress(self.keypresser_target_key),
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
            self._set_status(self._kp_status_label, "Idle", STATUS_IDLE_COLOR)

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

    # ── Settings callbacks ────────────────────────────────────

    def _toggle_auto_check_updates(self):
        self.auto_check_updates = self._auto_update_cb.isChecked()
        self._save_config()

    # ══════════════════════════════════════════════════════════════
    #  Update feature
    # ══════════════════════════════════════════════════════════════

    def _check_for_updates_clicked(self):
        threading.Thread(target=self._check_for_updates, args=(False,), daemon=True).start()

    def _check_for_updates(self, silent=True):
        try:
            request = urllib.request.Request(
                GITHUB_API_LATEST,
                headers={"User-Agent": f"{APP_NAME}/{__version__}"},
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read(MAX_API_RESPONSE_SIZE + 1)
                if len(raw) > MAX_API_RESPONSE_SIZE:
                    raise ValueError("API response too large")
                data = json.loads(raw.decode())

            latest_version = data.get("tag_name", "").lstrip("v")
            if not latest_version:
                raise ValueError("No version tag found in release")

            if self._version_newer(latest_version, __version__):
                self._safe_after(
                    0,
                    lambda: self._show_update_dialog(latest_version, data),
                )
            elif not silent:
                self._safe_after(
                    0,
                    lambda: QMessageBox.information(
                        self,
                        "Up to Date",
                        f"You are running the latest version (v{__version__}).",
                    ),
                )
        except Exception as e:
            if not silent:
                self._safe_after(
                    0,
                    lambda _e=e: QMessageBox.critical(
                        self,
                        "Update Error",
                        f"Failed to check for updates:\n{_e}",
                    ),
                )

    def _show_update_dialog(self, latest_version, release_data):
        msg = (
            f"A new version is available!\n\n"
            f"Current: v{__version__}\nLatest: v{latest_version}\n\n"
            f"Would you like to update?"
        )
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Update Available")
        dlg.setText(msg)
        update_btn = dlg.addButton("Update Now", QMessageBox.ButtonRole.AcceptRole)
        releases_btn = dlg.addButton("Open Releases", QMessageBox.ButtonRole.ActionRole)
        dlg.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        dlg.exec()

        clicked = dlg.clickedButton()
        if clicked == update_btn:
            threading.Thread(
                target=self._apply_update,
                args=(release_data,),
                daemon=True,
            ).start()
        elif clicked == releases_btn:
            webbrowser.open(GITHUB_RELEASES_URL)

    @staticmethod
    def _version_newer(latest, current):
        def parse_version(vs):
            if not vs or not isinstance(vs, str):
                return (0, 0, 0, False, 0)
            vs = vs.lstrip("v")
            if "-" in vs:
                main_part, pre = vs.split("-", 1)
            else:
                main_part, pre = vs, ""
            parts = []
            for p in main_part.split("."):
                if not p.isdigit():
                    return (0, 0, 0, False, 0)
                parts.append(int(p))
            while len(parts) < 3:
                parts.append(0)
            pre_num = 0
            if pre:
                d = "".join(c for c in pre if c.isdigit())
                pre_num = int(d) if d else 0
            return (parts[0], parts[1], parts[2], pre == "", pre_num)

        try:
            return parse_version(latest) > parse_version(current)
        except Exception:
            return False

    def _compute_git_blob_sha(self, content):
        header = f"blob {len(content)}\0".encode()
        return hashlib.sha1(header + content).hexdigest()

    def _get_expected_sha256(self, release_data, asset_name, headers):
        """Fetch SHA256SUMS from release and return expected hash for asset_name."""
        tag_name = release_data.get("tag_name", "")
        if not hasattr(self, "_sha256sums_cache"):
            self._sha256sums_cache = {}
        if tag_name not in self._sha256sums_cache:
            sha_url = f"https://github.com/{GITHUB_REPO}/releases/download/{tag_name}/SHA256SUMS"
            try:
                req = urllib.request.Request(sha_url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    self._sha256sums_cache[tag_name] = response.read().decode("utf-8")
            except Exception as e:
                print(f"Warning: Could not fetch SHA256SUMS: {e}")
                return None
        sha256sums = self._sha256sums_cache.get(tag_name, "")
        for line in sha256sums.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == asset_name:
                h = parts[0].lower()
                if re.fullmatch(r"[0-9a-f]{64}", h):
                    return h
                return None
        return None

    def _verify_file_against_github(self, tag_name, filename, content, headers, release_data=None):
        # NOTE: Both payload and SHA come from GitHub over HTTPS. This verifies
        # transport integrity, not authenticity. A MITM on the TLS connection
        # could spoof both. For stronger guarantees, add GPG/minisign signature
        # verification with a pinned public key.
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}?ref={tag_name}"
        request = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(MAX_METADATA_RESPONSE_SIZE + 1)
            if len(raw) > MAX_METADATA_RESPONSE_SIZE:
                raise ValueError("API response too large")
            file_info = json.loads(raw.decode())
        expected_sha = file_info.get("sha", "")
        actual_sha = self._compute_git_blob_sha(content)
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"Integrity check failed for {filename}!\n"
                f"Expected SHA: {expected_sha[:16]}...\n"
                f"Got SHA: {actual_sha[:16]}..."
            )

        # SHA-256 verification (mandatory if SHA256SUMS available)
        actual_sha256 = hashlib.sha256(content).hexdigest().lower()
        if release_data:
            expected_sha256 = self._get_expected_sha256(release_data, filename, headers)
            if expected_sha256:
                if actual_sha256 != expected_sha256:
                    raise RuntimeError(
                        f"SHA-256 verification failed for {filename}!\n"
                        f"Expected: {expected_sha256[:16]}...\n"
                        f"Got: {actual_sha256[:16]}..."
                    )
                print(
                    f"Integrity verified for {filename}: sha256={actual_sha256[:16]}... (enforced)"
                )
                return
        print(
            f"Integrity verified for {filename}: "
            f"git-sha1={actual_sha[:16]}... sha256={actual_sha256[:16]}..."
        )

    def _apply_update(self, release_data):
        tmp_path = None
        progress_state: dict = {"dlg": None, "lbl": None, "bar": None}

        def _create_progress():
            dlg = QDialog(self)
            dlg.setWindowTitle("Downloading Update")
            dlg.setFixedSize(360, 90)
            dlg.setModal(True)
            lay = QVBoxLayout(dlg)
            lbl = QLabel("Downloading update...")
            lay.addWidget(lbl)
            bar = QProgressBar()
            bar.setRange(0, 100)
            lay.addWidget(bar)
            dlg.closeEvent = lambda e: e.ignore()
            progress_state.update(dlg=dlg, lbl=lbl, bar=bar)
            dlg.show()
            # Safety timeout: auto-close if download hangs
            QTimer.singleShot(120_000, _close_progress)

        def _update_progress(pct, mb, total_mb):
            if progress_state["lbl"]:
                progress_state["lbl"].setText(
                    f"Downloading update... {mb:.1f}/{total_mb:.1f} MB ({pct}%)"
                )
            if progress_state["bar"]:
                progress_state["bar"].setValue(pct)

        def _close_progress():
            if progress_state["dlg"]:
                try:
                    progress_state["dlg"].close()
                except RuntimeError:
                    pass
                progress_state["dlg"] = None

        self._safe_after(0, _create_progress)

        try:
            tag_name = release_data.get("tag_name", "main")
            if not re.match(r"^v?\d+\.\d+(\.\d+)?(-[\w.]+)?$", tag_name):
                raise ValueError(f"Invalid tag format: {tag_name}")

            if getattr(sys, "frozen", False):

                def _frozen_notice():
                    _close_progress()
                    QMessageBox.information(
                        self,
                        "Update Available",
                        f"A new version ({tag_name}) is available.\n\n"
                        "Frozen binaries cannot self-update.\n"
                        "Please download the latest release from GitHub.",
                    )
                    QDesktopServices.openUrl(QUrl(GITHUB_RELEASES_URL))

                self._safe_after(0, _frozen_notice)
                return

            download_url = f"{GITHUB_RAW_URL}/{tag_name}/autoclicker.py"
            headers = {"User-Agent": f"{APP_NAME}/{__version__}"}

            request = urllib.request.Request(download_url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                content_length = response.headers.get("Content-Length")
                total_bytes = 0
                if content_length:
                    try:
                        total_bytes = int(content_length)
                        if total_bytes > MAX_DOWNLOAD_SIZE:
                            self._safe_after(0, _close_progress)
                            self._safe_after(
                                0,
                                lambda: QMessageBox.critical(
                                    self,
                                    "Update Failed",
                                    f"Update file too large "
                                    f"({total_bytes / 1024 / 1024:.1f}MB).\n"
                                    f"Max: "
                                    f"{MAX_DOWNLOAD_SIZE / 1024 / 1024:.1f}MB",
                                ),
                            )
                            return
                    except ValueError:
                        pass

                chunks = []
                downloaded = 0
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if downloaded > MAX_DOWNLOAD_SIZE:
                        self._safe_after(0, _close_progress)
                        self._safe_after(
                            0,
                            lambda: QMessageBox.critical(
                                self,
                                "Update Failed",
                                "Update file exceeds maximum size.",
                            ),
                        )
                        return
                    if total_bytes > 0:
                        pct = int(downloaded / total_bytes * 100)
                        mb = downloaded / (1024 * 1024)
                        tmb = total_bytes / (1024 * 1024)
                        self._safe_after(
                            0,
                            lambda p=pct, m=mb, t=tmb: _update_progress(p, m, t),
                        )
                content = b"".join(chunks)

            # Verify integrity via git blob SHA
            self._verify_file_against_github(
                tag_name,
                "autoclicker.py",
                content,
                headers,
                release_data=release_data,
            )

            current_script = Path(__file__).resolve()
            script_dir = current_script.parent
            backup_path = current_script.with_suffix(".py.backup")
            fd, tmp_str = tempfile.mkstemp(
                dir=str(script_dir),
                prefix=".autoclicker_update_",
                suffix=".tmp",
            )
            tmp_path = Path(tmp_str)

            # Write verified content to temp file
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
            except (IOError, OSError) as e:
                self._safe_after(
                    0,
                    lambda _e=e: QMessageBox.critical(
                        self,
                        "Update Failed",
                        "Failed to write update file.\nCheck disk space and permissions.",
                    ),
                )
                return

            # Backup current script
            try:
                shutil.copy2(current_script, backup_path)
            except (IOError, OSError) as e:
                self._safe_after(
                    0,
                    lambda _e=e: QMessageBox.critical(
                        self,
                        "Update Failed",
                        "Failed to create backup.\nCheck disk space and permissions.",
                    ),
                )
                return

            # Replace current script with update
            try:
                if sys.platform == "win32":
                    old_path = current_script.with_suffix(".py.old")
                    try:
                        if old_path.exists():
                            old_path.unlink()
                        os.rename(str(current_script), str(old_path))
                    except OSError as e:
                        self._safe_after(
                            0,
                            lambda _e=e: QMessageBox.critical(
                                self,
                                "Update Failed",
                                "Failed to rename current script.\n\n"
                                "A backup was created in the app directory.",
                            ),
                        )
                        return
                    try:
                        os.rename(str(tmp_path), str(current_script))
                        tmp_path = None
                    except OSError as e:
                        try:
                            os.rename(str(old_path), str(current_script))
                        except OSError:
                            pass
                        self._safe_after(
                            0,
                            lambda _e=e: QMessageBox.critical(
                                self,
                                "Update Failed",
                                "Failed to move update file.\n\n"
                                "A backup was created in the app directory.",
                            ),
                        )
                        return
                else:
                    os.replace(str(tmp_path), str(current_script))
                    tmp_path = None
            except (IOError, OSError) as e:
                self._safe_after(
                    0,
                    lambda _e=e: QMessageBox.critical(
                        self,
                        "Update Failed",
                        "Failed to apply update.\n\nA backup was created in the app directory.",
                    ),
                )
                return

            # Clean up stale files
            for stale in [backup_path, current_script.with_suffix(".py.old")]:
                try:
                    if stale.exists():
                        stale.unlink()
                except OSError:
                    pass

            def _on_complete():
                _close_progress()
                QMessageBox.information(
                    self,
                    "Update Applied",
                    "AutoClicker has been updated successfully!\n\n"
                    "Please relaunch AutoClicker to run the new version.",
                )
                self.close()

            self._safe_after(0, _on_complete)

        except Exception as e:
            self._safe_after(
                0,
                lambda _e=e: QMessageBox.critical(
                    self,
                    "Update Failed",
                    f"Unexpected error:\n{type(_e).__name__}: {_e}",
                ),
            )
        finally:
            self._safe_after(0, _close_progress)
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink()
                except OSError as cleanup_error:
                    print(f"Warning: Failed to clean up temp file {tmp_path}: {cleanup_error}")

    # ── Window close ──────────────────────────────────────────

    def closeEvent(self, event):
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
        self._save_config()
        event.accept()


# ═══════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(_make_icon())
    win = AppWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

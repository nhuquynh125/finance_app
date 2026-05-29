# app/core/theme_engine.py
"""
Theme engine cho Finance AI — PyQt6.
Bảng màu lấy cảm hứng từ logo: Navy xanh đậm + Mint xanh nhạt + Cam accent.
"""

from __future__ import annotations

import sys
from typing import Optional

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import QSettings

from app.core.event_bus import bus


# ── Color tokens ──────────────────────────────────────────────────────────────

LIGHT = {
    "bg_primary":      "#FFFFFF",
    "bg_secondary":    "#F0F6FF",       # Xanh rất nhạt (từ màu mint logo)
    "bg_sidebar":      "#0B2A4A",       # Navy đậm từ logo
    "bg_toolbar":      "#FFFFFF",
    "bg_card":         "#FFFFFF",
    "bg_input":        "#F5F9FF",
    "bg_hover":        "#E8F2FF",

    "border":          "#D0E4F7",
    "border_focus":    "{accent}",

    "text_primary":    "#0B2A4A",       # Navy đậm
    "text_secondary":  "#3A6B9A",       # Navy trung
    "text_muted":      "#8BAEC8",
    "text_on_accent":  "#FFFFFF",
    "text_sidebar":    "#FFFFFF",
    "text_sidebar_muted": "rgba(255,255,255,0.6)",

    "income":          "#1D9E75",
    "income_bg":       "#E8F5EE",
    "expense":         "#E85020",       # Cam đỏ từ logo
    "expense_bg":      "#FEF0EB",
    "warning":         "#E8921A",       # Cam vàng từ logo
    "warning_bg":      "#FEF5E7",

    "scrollbar":       "#C5DDF5",
    "scrollbar_hover": "#8BAEC8",

    # Gradient sidebar
    "sidebar_gradient_top":    "#0B2A4A",
    "sidebar_gradient_bottom": "#0D4A6B",
}

DARK = {
    "bg_primary":      "#0D1B2A",       # Navy rất đậm
    "bg_secondary":    "#122336",
    "bg_sidebar":      "#061422",       # Navy gần đen
    "bg_toolbar":      "#0D1B2A",
    "bg_card":         "#122336",
    "bg_input":        "#162B40",
    "bg_hover":        "#1A3550",

    "border":          "#1E3D5C",
    "border_focus":    "{accent}",

    "text_primary":    "#D6EAFF",
    "text_secondary":  "#7AAFD4",
    "text_muted":      "#3A6B9A",
    "text_on_accent":  "#FFFFFF",
    "text_sidebar":    "#FFFFFF",
    "text_sidebar_muted": "rgba(255,255,255,0.55)",

    "income":          "#2DBD8F",
    "income_bg":       "#0A2E1E",
    "expense":         "#E85020",
    "expense_bg":      "#2E1508",
    "warning":         "#E8921A",
    "warning_bg":      "#2E1F08",

    "scrollbar":       "#1E3D5C",
    "scrollbar_hover": "#2A5580",

    "sidebar_gradient_top":    "#061422",
    "sidebar_gradient_bottom": "#0B2A4A",
}


def _build_qss(tokens: dict, accent: str) -> str:
    t = {k: v.replace("{accent}", accent) for k, v in tokens.items()}
    t["accent"] = accent

    def hex_blend(hex1: str, hex2: str, ratio: float) -> str:
        c1 = QColor(hex1)
        c2 = QColor(hex2)
        r = int(c1.red()   * (1 - ratio) + c2.red()   * ratio)
        g = int(c1.green() * (1 - ratio) + c2.green() * ratio)
        b = int(c1.blue()  * (1 - ratio) + c2.blue()  * ratio)
        return f"#{r:02X}{g:02X}{b:02X}"

    accent_light = hex_blend(accent, t["bg_primary"], 0.88)
    accent_hover = hex_blend(accent, t["bg_primary"], 0.75)

    return f"""
/* ── Base ─────────────────────────────────────────── */
QWidget {{
    background: {t['bg_primary']};
    color: {t['text_primary']};
    font-family: 'Segoe UI', 'Be Vietnam Pro', 'Arial', sans-serif;
    font-size: 12px;
    selection-background-color: {accent_light};
    selection-color: {t['text_primary']};
}}

QMainWindow, QDialog {{
    background: {t['bg_secondary']};
}}

/* ── Cards / Frames ─────────────────────────────── */
QFrame {{
    background: {t['bg_card']};
    border: 1px solid {t['border']};
    border-radius: 12px;
}}

QFrame[frameShape="4"],
QFrame[frameShape="5"] {{
    background: {t['border']};
    border: none;
    border-radius: 0;
}}

/* ── Sidebar ─────────────────────────────────────── */
QWidget#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {t['sidebar_gradient_top']},
        stop:1 {t['sidebar_gradient_bottom']});
    border-right: none;
    border-radius: 0;
}}

/* ── Toolbar ─────────────────────────────────────── */
QWidget#toolbar {{
    background: {t['bg_toolbar']};
    border-bottom: 1px solid {t['border']};
    border-radius: 0;
}}

/* ── Scroll areas ────────────────────────────────── */
QScrollArea {{
    border: none;
    background: {t['bg_secondary']};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t['scrollbar']};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t['scrollbar_hover']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
}}
QScrollBar::handle:horizontal {{
    background: {t['scrollbar']};
    border-radius: 3px;
    min-width: 30px;
}}

/* ── Inputs ──────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {t['bg_input']};
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 7px 12px;
    selection-background-color: {accent_light};
}}
QLineEdit:focus, QTextEdit:focus {{
    border-color: {accent};
    background: {t['bg_card']};
}}
QLineEdit:hover, QTextEdit:hover {{
    border-color: {hex_blend(accent, t['border'], 0.4)};
}}

/* ── ComboBox ────────────────────────────────────── */
QComboBox {{
    background: {t['bg_input']};
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 5px 10px;
}}
QComboBox:hover {{ border-color: {hex_blend(accent, t['border'], 0.4)}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    selection-background-color: {accent_light};
    selection-color: {t['text_primary']};
    outline: none;
    padding: 4px;
}}

/* ── Buttons ─────────────────────────────────────── */
QPushButton {{
    background: {t['bg_card']};
    color: {t['text_secondary']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 12px;
}}
QPushButton:hover  {{ background: {t['bg_hover']}; border-color: {hex_blend(accent, t['border'], 0.3)}; }}
QPushButton:pressed {{ background: {accent_hover}; }}
QPushButton:disabled {{ color: {t['text_muted']}; border-color: {t['border']}; }}

QPushButton[class="primary"] {{
    background: {accent_light};
    color: {accent};
    border: 1.5px solid {hex_blend(accent, t['bg_primary'], 0.5)};
    font-weight: 600;
}}
QPushButton[class="primary"]:hover  {{ background: {accent_hover}; }}
QPushButton[class="danger"] {{
    color: {t['expense']};
    border-color: {t['expense']};
}}
QPushButton[class="danger"]:hover {{ background: {t['expense_bg']}; }}

/* ── Table ───────────────────────────────────────── */
QTableWidget {{
    background: {t['bg_card']};
    border: 1px solid {t['border']};
    border-radius: 12px;
    gridline-color: {t['border']};
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 8px 14px;
    color: {t['text_primary']};
    border: none;
}}
QTableWidget::item:selected {{
    background: {accent_light};
    color: {t['text_primary']};
}}
QTableWidget::item:alternate {{
    background: {t['bg_secondary']};
}}
QHeaderView::section {{
    background: {t['bg_secondary']};
    color: {t['text_muted']};
    border: none;
    border-bottom: 2px solid {t['border']};
    padding: 8px 14px;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

/* ── CheckBox ────────────────────────────────────── */
QCheckBox {{
    color: {t['text_primary']};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 1.5px solid {t['border']};
    border-radius: 5px;
    background: {t['bg_input']};
}}
QCheckBox::indicator:checked {{
    background: {accent};
    border-color: {accent};
}}

/* ── ProgressBar ─────────────────────────────────── */
QProgressBar {{
    background: {t['bg_hover']};
    border: none;
    border-radius: 5px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {accent}, stop:1 {hex_blend(accent, '#1D9E75', 0.4)});
    border-radius: 5px;
}}

/* ── Tooltip ─────────────────────────────────────── */
QToolTip {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 11px;
}}

/* ── Menu ────────────────────────────────────────── */
QMenu {{
    background: {t['bg_card']};
    color: {t['text_primary']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    padding: 5px;
}}
QMenu::item {{
    padding: 7px 18px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {accent_light};
    color: {t['text_primary']};
}}
QMenu::separator {{
    height: 1px;
    background: {t['border']};
    margin: 4px 10px;
}}

/* ── Sidebar buttons ─────────────────────────────── */
QPushButton[class="sidebar-btn"] {{
    background: transparent;
    color: rgba(255,255,255,0.75);
    border: none;
    border-radius: 8px;
    text-align: left;
    padding: 9px 14px;
    font-size: 13px;
}}
QPushButton[class="sidebar-btn"]:hover {{
    background: rgba(255,255,255,0.12);
    color: #FFFFFF;
}}
QPushButton[class="sidebar-btn-active"] {{
    background: rgba(255,255,255,0.18);
    color: #FFFFFF;
    border: none;
    border-left: 3px solid {accent};
    border-radius: 8px;
    text-align: left;
    padding: 9px 14px 9px 11px;
    font-size: 13px;
    font-weight: 600;
}}

/* ── SpinBox & DateEdit ──────────────────────────── */
QDoubleSpinBox, QSpinBox, QDateEdit {{
    background: {t['bg_input']};
    color: {t['text_primary']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 6px 10px;
}}
QDoubleSpinBox:focus, QSpinBox:focus, QDateEdit:focus {{
    border-color: {accent};
}}

/* ── Tab widget ──────────────────────────────────── */
QTabBar::tab {{
    background: transparent;
    color: {t['text_secondary']};
    padding: 9px 18px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {accent};
    border-bottom: 2px solid {accent};
    font-weight: 600;
}}
"""


# ── Theme Engine ──────────────────────────────────────────────────────────────

class ThemeEngine:
    # Accent màu cam từ logo làm mặc định
    DEFAULT_ACCENT = "#1A6BAF"   # Xanh dương đậm từ logo

    ACCENTS = {
        "Xanh logo (mặc định)": "#1A6BAF",
        "Cam logo":              "#E8921A",
        "Xanh mint":             "#1D9E75",
        "Tím":                   "#7F77DD",
        "Hồng":                  "#D4537E",
        "Đỏ cam":                "#E85020",
    }

    def __init__(self):
        self._app: Optional[QApplication] = None
        self._mode: str = "light"
        self._accent: str = self.DEFAULT_ACCENT
        self._load_prefs()

    def _load_prefs(self) -> None:
        s = QSettings("FinanceAI", "Theme")
        self._mode   = s.value("mode",   "light", type=str)
        self._accent = s.value("accent", self.DEFAULT_ACCENT, type=str)

    def _save_prefs(self) -> None:
        s = QSettings("FinanceAI", "Theme")
        s.setValue("mode",   self._mode)
        s.setValue("accent", self._accent)

    def _is_system_dark(self) -> bool:
        try:
            if sys.platform == "win32":
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return val == 0
            elif sys.platform == "darwin":
                import subprocess
                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True, text=True
                )
                return result.stdout.strip().lower() == "dark"
        except Exception:
            pass
        return False

    @property
    def is_dark(self) -> bool:
        if self._mode == "dark":  return True
        if self._mode == "auto":  return self._is_system_dark()
        return False

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def accent(self) -> str:
        return self._accent

    def apply(self, app: QApplication) -> None:
        self._app = app
        self._apply_qss()

    def set_mode(self, mode: str) -> None:
        assert mode in ("light", "dark", "auto")
        self._mode = mode
        self._save_prefs()
        self._apply_qss()
        bus.theme_changed.emit(mode)

    def set_accent(self, color_hex: str) -> None:
        self._accent = color_hex
        self._save_prefs()
        self._apply_qss()
        bus.theme_changed.emit(self._mode)

    def _apply_qss(self) -> None:
        if self._app is None:
            return
        tokens = DARK if self.is_dark else LIGHT
        qss = _build_qss(tokens, self._accent)
        self._app.setStyleSheet(qss)

    def get_color(self, key: str) -> str:
        tokens = DARK if self.is_dark else LIGHT
        val = tokens.get(key, "#000000")
        return val.replace("{accent}", self._accent)

    def income_color(self)  -> str: return self.get_color("income")
    def expense_color(self) -> str: return self.get_color("expense")
    def accent_color(self)  -> str: return self._accent
    def border_color(self)  -> str: return self.get_color("border")
    def bg_card(self)       -> str: return self.get_color("bg_card")
    def sidebar_bg(self)    -> str: return self.get_color("bg_sidebar")


# Singleton
theme_engine = ThemeEngine()

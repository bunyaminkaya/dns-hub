"""Açık/koyu tema: renk jetonları ve QSS."""
from __future__ import annotations

from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication

PALETTES = {
    "light": dict(bg="#F3F3F3", card="#FFFFFF", bd="#E2E2E2", bd2="#D6D6D6", tx="#1A1A1A", mu="#5C5C5C",
                  ac="#0F6CBD", ac_h="#0C5A9E", acx="#FFFFFF", acs="#E3EFFB", ok="#0F7B0F", oks="#E1F3E1",
                  wn="#8A5100", wns="#FFF1DB", er="#B3261E", hv="#E8E8E8", inp="#FFFFFF"),
    "dark": dict(bg="#202020", card="#2B2B2B", bd="#3C3C3C", bd2="#4A4A4A", tx="#F5F5F5", mu="#ADADAD",
                 ac="#60CDFF", ac_h="#7AD7FF", acx="#00263D", acs="#1C3A4F", ok="#6CCB5F", oks="#1F3A1F",
                 wn="#FCB75A", wns="#4A3514", er="#FF8A80", hv="#333333", inp="#2B2B2B"),
}

P: dict = dict(PALETTES["light"])
MODE = "light"

QSS = Template("""
* { font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", sans-serif; font-size: 14px; }
QWidget { color: $tx; }
QMainWindow, QWidget#root, QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget { background: $bg; }
QDialog { background: $bg; }
QLabel { background: transparent; }
QScrollArea#scrollArea, QScrollArea#scrollArea > QWidget > QWidget#scrollInner, QWidget#scrollInner { background: transparent; }
QLabel[cls="h1"] { font-size: 26px; font-weight: 600; }
QLabel[cls="h2"] { font-size: 24px; font-weight: 600; }
QLabel[cls="big"] { font-size: 34px; font-weight: 600; }
QLabel[cls="sec"] { font-size: 15px; font-weight: 600; }
QLabel[cls="muted"] { color: $mu; font-size: 13px; }
QLabel[cls="small"] { color: $mu; font-size: 12px; }
QLabel[cls="strong"] { font-weight: 600; }
QLabel[cls="ok"] { color: $ok; font-weight: 600; }
QLabel[cls="warn"] { color: $wn; font-weight: 500; }
QLabel[cls="err"] { color: $er; font-size: 12px; }
QLabel[cls="pill"] { background: $hv; border-radius: 14px; padding: 4px 12px; font-size: 13px; font-weight: 500; }
QLabel[cls="pill_ok"] { background: $oks; color: $ok; border-radius: 14px; padding: 4px 12px; font-size: 13px; font-weight: 500; }
QLabel[cls="tag_ok"] { background: $oks; color: $ok; border-radius: 10px; padding: 2px 8px; font-size: 12px; font-weight: 600; }
QFrame#card { background: $card; border: 1px solid $bd; border-radius: 12px; }
QFrame#cardacc { background: $acs; border: 1px solid $bd; border-radius: 12px; }
QFrame#sep { background: $bd; max-height: 1px; min-height: 1px; border: 0; }
QWidget#nav { background: $bg; }
QWidget#seg { background: $hv; border-radius: 8px; }

QPushButton { background: $card; border: 1px solid $bd; border-radius: 6px; padding: 0 16px; min-height: 36px; font-weight: 500; }
QPushButton:hover { background: $hv; }
QPushButton:disabled { color: $mu; }
QPushButton[cls="primary"] { background: $ac; color: $acx; border: 0; font-weight: 600; }
QPushButton[cls="primary"]:hover { background: $ac_h; }
QPushButton[cls="primary"]:disabled { background: $hv; color: $mu; }
QPushButton[cls="big"] { min-height: 56px; font-size: 16px; border-radius: 8px; }
QPushButton[cls="outline"] { background: transparent; border: 1px solid $ac; color: $ac; font-weight: 600; }
QPushButton[cls="outline"]:hover { background: $acs; }
QPushButton[cls="ghost"] { background: transparent; border: 0; }
QPushButton[cls="ghost"]:hover { background: $hv; }
QPushButton[cls="nav"] { text-align: left; border: 0; background: transparent; min-height: 44px; padding: 0 12px; font-weight: 500; }
QPushButton[cls="nav"]:hover { background: $hv; }
QPushButton[cls="nav"]:checked { background: $hv; font-weight: 600; }
QPushButton[cls="chip"] { border-radius: 16px; min-height: 30px; padding: 0 14px; font-size: 13px; font-weight: 400; }
QPushButton[cls="chip"]:checked { background: $acs; border: 1px solid $ac; color: $ac; font-weight: 600; }
QPushButton[cls="seg"] { background: transparent; border: 0; border-radius: 6px; min-height: 32px; padding: 0 18px; font-size: 13px; }
QPushButton[cls="seg"]:hover { background: $bd; }
QPushButton[cls="seg"]:checked { background: $acs; color: $ac; font-weight: 600; }
QPushButton[cls="theme"] { border: 2px solid $bd; border-radius: 8px; padding: 0; min-height: 64px; background: transparent; }
QPushButton[cls="theme"]:checked { border: 2px solid $ac; }
QPushButton[cls="select"] { text-align: left; padding: 0; min-height: 36px; }
QPushButton[cls="radio"] { text-align: left; border: 0; border-top: 1px solid $bd; border-radius: 0; background: transparent; min-height: 48px; padding: 0 4px; }

QLineEdit { background: $inp; border: 1px solid $bd2; border-radius: 6px; padding: 0 12px; min-height: 38px; selection-background-color: $ac; selection-color: $acx; }
QLineEdit:focus { border: 1px solid $ac; }
QLineEdit[state="ok"] { border: 1px solid $ok; }
QLineEdit[state="bad"] { border: 1px solid $er; }
QComboBox { background: $card; border: 1px solid $bd; border-radius: 6px; padding: 0 12px; min-height: 36px; }
QComboBox QAbstractItemView { background: $card; border: 1px solid $bd; selection-background-color: $acs; selection-color: $tx; }
QRadioButton { spacing: 12px; min-height: 44px; padding: 0 4px; border-top: 1px solid $bd; }
QRadioButton::indicator { width: 16px; height: 16px; border-radius: 10px; border: 2px solid $mu; background: transparent; }
QRadioButton::indicator:checked { border: 2px solid $ac; background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 $ac, stop:0.5 $ac, stop:0.55 transparent, stop:1 transparent); }
QCheckBox { spacing: 10px; }
QCheckBox::indicator { width: 20px; height: 20px; border-radius: 4px; border: 1.5px solid $mu; background: transparent; }
QCheckBox::indicator:checked { background: $ac; border: 1.5px solid $ac; }

QTableWidget { background: $card; border: 1px solid $bd; border-radius: 12px; gridline-color: transparent; outline: 0; }
QTableWidget::item { border-bottom: 1px solid $bd; padding: 0 6px; }
QTableWidget::item:selected { background: $acs; color: $tx; }
QHeaderView::section { background: $card; color: $mu; border: 0; border-bottom: 1px solid $bd; padding: 8px 6px; font-size: 12px; font-weight: 500; }
QTableCornerButton::section { background: $card; border: 0; }
QProgressBar { background: $hv; border: 0; border-radius: 3px; max-height: 6px; min-height: 6px; text-align: center; color: transparent; }
QProgressBar::chunk { background: $ac; border-radius: 3px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $bd2; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QToolTip { background: $card; color: $tx; border: 1px solid $bd; padding: 4px 8px; }
QMenu { background: $card; color: $tx; border: 1px solid $bd; padding: 4px; }
QMenu::item { background: transparent; color: $tx; padding: 8px 28px 8px 14px; border-radius: 4px; margin: 1px 2px; }
QMenu::item:selected { background: $hv; color: $tx; }
QMenu::item:disabled { color: $mu; }
QMenu::separator { height: 1px; background: $bd; margin: 4px 8px; }
QLabel#toast { background: $tx; color: $bg; border-radius: 8px; padding: 10px 18px; font-weight: 500; }
QMessageBox { background: $bg; }
""")


def system_mode() -> str:
    try:
        scheme = QGuiApplication.styleHints().colorScheme()
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"
    except Exception:  # noqa: BLE001
        return "light"


def resolve(setting: str) -> str:
    return system_mode() if setting not in ("light", "dark") else setting


def apply_theme(app, setting: str) -> str:
    global MODE
    MODE = resolve(setting)
    P.clear()
    P.update(PALETTES[MODE])
    font = QFont()
    font.setPointSizeF(10)
    app.setFont(font)
    app.setStyleSheet(QSS.substitute(P))
    return MODE

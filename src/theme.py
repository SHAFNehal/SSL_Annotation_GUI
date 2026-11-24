"""Lightweight Qt styling for SSL Annotation Studio."""

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from pathlib import Path


COLORS = {
    "page": "#f7f8f6", "surface": "#ffffff", "text": "#242a2f",
    "muted": "#68727d", "line": "#dde3e6", "accent": "#147c82",
    "accent_dark": "#0d5f66", "accent_soft": "#e8f4f3", "warning": "#b34038",
}

STYLESHEET = """
QMainWindow { background: #f7f8f6; }
QWidget { color: #242a2f; }
QDialog, QMessageBox, QInputDialog, QColorDialog { background: #f7f8f6; color: #242a2f; }
QDialog QLabel { color: #242a2f; }
QTextEdit, QPlainTextEdit, QTextBrowser { background: #ffffff; color: #242a2f; border: 1px solid #dde3e6; border-radius: 6px; selection-background-color: #147c82; selection-color: #ffffff; }
QLabel { background: transparent; }
QFrame#appHeader { background: #ffffff; border-bottom: 1px solid #dde3e6; }
QFrame#panel, QFrame#workspace { background: #ffffff; border: 1px solid #dde3e6; border-radius: 10px; }
QLabel#brandLogo { background: transparent; border: none; }
QLabel#appTitle { font-size: 21px; font-weight: bold; }
QLabel#sectionTitle { font-size: 15px; font-weight: bold; }
QLabel#muted, QLabel#imageMeta { color: #68727d; font-size: 12px; }
QLabel#eyebrow { color: #147c82; font-size: 10px; font-weight: bold; }
QLabel#emptyTitle { font-size: 25px; font-weight: bold; }
QLabel#saveBadge { color: #0d5f66; background: #e8f4f3; border-radius: 12px; padding: 6px 12px; font-size: 11px; }
QLabel#saveBadge[state="unsaved"] { color: #87611e; background: #fff4dc; }
QLabel#saveBadge[state="error"] { color: #b34038; background: #faeae8; }
QPushButton { background: #ffffff; border: 1px solid #dde3e6; border-radius: 6px; padding: 7px 11px; min-height: 20px; font-weight: 600; }
QPushButton:hover { border-color: #147c82; background: #f3f9f8; }
QPushButton:pressed { background: #e8f4f3; }
QPushButton:focus { border: 1px solid #147c82; }
QPushButton:disabled { color: #9ca5ac; background: #f7f8f6; border-color: #e7ebed; }
QPushButton#primary { color: #ffffff; background: #147c82; border-color: #147c82; }
QPushButton#primary:hover { background: #0d5f66; border-color: #0d5f66; }
QPushButton#primary:disabled { background: #a8c8c8; border-color: #a8c8c8; color: #ffffff; }
QPushButton#tool { border-color: transparent; background: transparent; padding: 6px 12px; }
QPushButton#tool:checked { color: #0d5f66; background: #e8f4f3; border-color: #b8d9d8; }
QPushButton#danger { color: #b34038; }
QPushButton#danger:disabled { color: #aeb5ba; }
QPushButton#danger:hover { background: #faeae8; border-color: #e6bfbb; }
QFrame#toolGroup { background: #f7f8f6; border-radius: 7px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #ffffff; border: 1px solid #dde3e6; border-radius: 6px; padding: 8px; selection-background-color: #147c82; selection-color: white; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #147c82; }
QComboBox { padding-right: 22px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #e8f4f3; selection-color: #0d5f66; border: 1px solid #dde3e6; }
QListWidget { background: #ffffff; border: none; outline: none; font-size: 12px; }
QListWidget::item { padding: 9px 6px; margin: 2px 0; border-left: 3px solid transparent; border-radius: 4px; }
QListWidget::item:hover { background: #f7f8f6; }
QListWidget::item:selected { background: #e8f4f3; color: #0d5f66; border-left-color: #147c82; }
QGroupBox { background: #ffffff; border: 1px solid #dde3e6; border-radius: 7px; margin-top: 20px; padding: 18px 10px 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #68727d; }
QGraphicsView { border: none; background: #eff3f2; }
QScrollArea#labelsScroll { background: transparent; border: none; }
QProgressBar { background: #edf0ef; border: none; border-radius: 3px; max-height: 5px; min-height: 5px; }
QProgressBar::chunk { background: #147c82; border-radius: 3px; }
QProgressBar#aiProgress { min-height: 20px; max-height: 20px; text-align: center; color: #242a2f; }
QSplitter::handle { background: #f7f8f6; width: 14px; }
QStatusBar { background: white; border-top: 1px solid #dde3e6; color: #68727d; font-size: 11px; }
QStatusBar::item { border: none; }
QMenuBar { background: #ffffff; border-bottom: 1px solid #dde3e6; padding: 4px 14px; }
QMenuBar::item { padding: 5px 10px; background: transparent; }
QMenuBar::item:selected { background: #e8f4f3; color: #0d5f66; }
QMenu { background: white; border: 1px solid #dde3e6; padding: 5px; }
QMenu::item { padding: 7px 24px; }
QMenu::item:selected { background: #e8f4f3; color: #0d5f66; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #c5ced1; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { color: #ffffff; background: #242a2f; border: none; padding: 6px; }
"""


def apply_theme(window):
    """Use one complete light theme, including application-owned dialogs.

    A window-only text stylesheet mixed with inherited dark OS background roles
    produces dark-on-dark warning dialogs. Set both globally instead.
    """
    app = QApplication.instance()
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Light)
    families = QFontDatabase.families()
    family = "Noto Sans" if "Noto Sans" in families else "DejaVu Sans"
    font = QFont(family, 10)
    if app.font() != font:
        app.setFont(font)
    palette = QPalette()
    for role, color in [(QPalette.Window, COLORS["page"]), (QPalette.Base, COLORS["surface"]),
                        (QPalette.AlternateBase, COLORS["page"]), (QPalette.Button, COLORS["surface"]),
                        (QPalette.WindowText, COLORS["text"]), (QPalette.Text, COLORS["text"]),
                        (QPalette.ButtonText, COLORS["text"]), (QPalette.Highlight, COLORS["accent_soft"]),
                        (QPalette.HighlightedText, COLORS["accent_dark"]),
                        (QPalette.ToolTipBase, COLORS["text"]), (QPalette.ToolTipText, "#ffffff"),
                        (QPalette.PlaceholderText, COLORS["muted"]), (QPalette.BrightText, "#ffffff"),
                        (QPalette.Link, COLORS["accent"]), (QPalette.LinkVisited, COLORS["accent_dark"]),
                        (QPalette.Light, "#ffffff"), (QPalette.Midlight, COLORS["page"]),
                        (QPalette.Mid, COLORS["line"]), (QPalette.Dark, COLORS["muted"]),
                        (QPalette.Shadow, COLORS["text"])]:
        palette.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(COLORS["muted"]))
    if app.palette() != palette:
        app.setPalette(palette)
    icons = (Path(__file__).parent / "icons").as_posix()
    stylesheet = STYLESHEET + """
QComboBox::down-arrow { image: url("%s/chevron-down.svg"); width: 12px; height: 8px; }
QAbstractSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 20px; border: none; }
QAbstractSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 20px; border: none; }
QAbstractSpinBox::up-arrow { image: url("%s/chevron-up.svg"); width: 10px; height: 7px; }
QAbstractSpinBox::down-arrow { image: url("%s/chevron-down.svg"); width: 10px; height: 7px; }
""" % (icons, icons, icons)
    if app.styleSheet() != stylesheet:
        app.setStyleSheet(stylesheet)

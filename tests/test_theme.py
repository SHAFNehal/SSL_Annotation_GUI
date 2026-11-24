"""Reproduce dark desktop colors without changing the actual OS settings."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog, QPlainTextEdit, QLabel

from src.main_window import MainWindow
from src.models import Project, ClassDefinition
from src.ai_assist import AIAssistDialog

APP = QApplication.instance() or QApplication([])


def contrast(first, second):
    def luminance(color):
        components = [color.redF(), color.greenF(), color.blueF()]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in components]
        return sum(a * b for a, b in zip(linear, [0.2126, 0.7152, 0.0722]))
    a, b = sorted([luminance(first), luminance(second)])
    return (b + 0.05) / (a + 0.05)


class ThemeTests(unittest.TestCase):
    def setUp(self):
        old_palette, old_sheet = APP.palette(), APP.styleSheet()
        self.addCleanup(lambda: APP.setPalette(old_palette))
        self.addCleanup(lambda: APP.setStyleSheet(old_sheet))
        APP.setStyleSheet("")
        dark = QPalette()
        for role in (QPalette.Window, QPalette.Base, QPalette.Button, QPalette.AlternateBase):
            dark.setColor(role, QColor("#202124"))
        for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
            dark.setColor(role, QColor("#eeeeee"))
        APP.setPalette(dark)
        self.window = MainWindow()
        self.addCleanup(self.window.close)

    def assert_readable(self, widget, foreground, background, background_widget=None):
        widget.ensurePolished()
        for group in (QPalette.Active, QPalette.Inactive):
            palette = widget.palette()
            backdrop = (background_widget or widget).palette().color(group, background)
            self.assertGreaterEqual(contrast(palette.color(group, foreground), backdrop), 4.5)

    def test_warning_dialog_labels_buttons_and_details_are_readable(self):
        warning = QMessageBox(QMessageBox.Warning, "Review Not Saved", "An empty draft cannot be approved.",
                              QMessageBox.Ok | QMessageBox.Cancel, self.window)
        warning.setInformativeText("Draw a box or reject this image.")
        warning.setDetailedText("Source images have not been changed.")
        warning.show()
        APP.processEvents()
        self.addCleanup(warning.close)
        self.assert_readable(warning, QPalette.WindowText, QPalette.Window)
        for label in warning.findChildren(QLabel):
            if label.text():
                self.assert_readable(label, QPalette.WindowText, QPalette.Window, warning)
        for button in warning.buttons():
            self.assert_readable(button, QPalette.ButtonText, QPalette.Button)

    def test_parentless_input_dialog_also_uses_application_light_palette(self):
        dialog = QInputDialog()
        dialog.setLabelText("Rename label:")
        dialog.setTextValue("Adult moth")
        dialog.ensurePolished()
        self.assert_readable(dialog, QPalette.WindowText, QPalette.Window)
        self.assert_readable(dialog, QPalette.Text, QPalette.Base)
        dialog.close()

    def test_ai_dialog_log_has_light_background_and_dark_text(self):
        self.window.project_manager.project = Project(classes=[ClassDefinition(0, "moth")])
        self.addCleanup(setattr, self.window.project_manager, "project", None)
        dialog = AIAssistDialog(self.window)
        dialog.ensurePolished()
        self.assert_readable(dialog, QPalette.WindowText, QPalette.Window)
        self.assert_readable(dialog.log, QPalette.Text, QPalette.Base)
        self.assertEqual(dialog.log.palette().color(QPalette.Base).name(), "#ffffff")
        dialog.close()


if __name__ == "__main__":
    unittest.main()

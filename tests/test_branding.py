import os
from pathlib import Path
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
from src.about_dialog import AboutDialog
from src.branding import APP_NAME, LOGO_PATH, ORGANIZATION, FUNDING_PI, WEBSITE
from src.main_window import MainWindow

APP = QApplication.instance() or QApplication([])


class BrandingTests(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.close)

    def test_window_displays_offline_lab_logo_and_public_name(self):
        self.assertIn(APP_NAME, self.window.windowTitle())
        self.assertFalse(self.window.windowIcon().isNull())
        self.assertTrue(LOGO_PATH.is_file())
        original = QPixmap(str(LOGO_PATH))
        shown = self.window.brand_logo.pixmap()
        self.assertFalse(shown.isNull())
        self.assertAlmostEqual(original.width() / original.height(), shown.width() / shown.height(), delta=0.1)
        self.assertEqual(self.window.brand_logo.text(), "")
        self.assertIn(ORGANIZATION, self.window.brand_logo.accessibleName())

    def test_about_includes_funding_pi_and_clickable_website_without_design_credit(self):
        about = AboutDialog(self.window)
        about.show()
        APP.processEvents()
        text = about.credits.text()
        for value in (ORGANIZATION, "USDA", FUNDING_PI, WEBSITE):
            self.assertIn(value, text)
        self.assertTrue(about.credits.openExternalLinks())
        self.assertNotIn("inspired", text.lower())
        self.assertGreaterEqual(about.credits.height(), 280)
        self.assertFalse(about.logo.pixmap().isNull())
        about.close()

    def test_both_guides_credit_ssl_and_funding_pi(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("README.md", "QUICKSTART.md"):
            text = (root / name).read_text(encoding="utf-8")
            for value in (APP_NAME, ORGANIZATION, "USDA", FUNDING_PI, WEBSITE):
                self.assertIn(value, text)
            self.assertNotIn("visual theme inspired", text.lower())

"""Quick GUI startup check callable from a frozen, windowed executable."""

import argparse
import importlib.util
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-check", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expect-ai", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from .main_window import MainWindow
    from .branding import APP_NAME, LOGO_PATH

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.processEvents()
    ai = all(importlib.util.find_spec(name) is not None for name in ("torch", "torchvision", "transformers"))
    icons = all((Path(__file__).parent / "icons" / name).is_file() for name in ("chevron-down.svg", "chevron-up.svg"))
    logo = LOGO_PATH.is_file() and not window.brand_logo.pixmap().isNull() and not window.windowIcon().isNull()
    branded = APP_NAME in window.windowTitle()
    ok = icons and logo and branded and ai == args.expect_ai
    args.report.write_text(json.dumps(dict(ok=ok, ai=ai, icons=icons, logo=logo, branded=branded)), encoding="utf-8")
    window.close()
    return 0 if ok else 1

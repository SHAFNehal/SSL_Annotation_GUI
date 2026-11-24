"""Main entry point for SSL Annotation Studio."""
import sys
import multiprocessing


def main():
    """Main application entry point"""
    multiprocessing.freeze_support()
    if "--ai-worker" in sys.argv:
        sys.argv.remove("--ai-worker")
        from src.ai_worker import main as worker_main
        sys.exit(worker_main())
    if "--bundle-check" in sys.argv:
        from src.bundle_check import main as check_main
        sys.exit(check_main())
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from src.main_window import MainWindow
    from src.branding import APP_NAME, ORGANIZATION, LOGO_PATH
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    app.setWindowIcon(QIcon(str(LOGO_PATH)))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

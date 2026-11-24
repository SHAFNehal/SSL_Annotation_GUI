"""Public development and funding credits for SSL Annotation Studio."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox

from .branding import APP_NAME, LOGO_PATH, ORGANIZATION, FUNDING_ACKNOWLEDGEMENT, FUNDING_PI, WEBSITE


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About " + APP_NAME)
        self.setMinimumWidth(440)
        self.resize(520, 570)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(16)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignLeft)
        self.logo.setAccessibleName(ORGANIZATION + " logo")
        self.logo.setPixmap(QPixmap(str(LOGO_PATH)).scaled(300, 94, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.logo)
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        layout.addWidget(title)
        self.credits = QLabel(
            "<p>Manual and AI-assisted bounding box annotation.</p>"
            f"<p><b>Developed by</b><br>{ORGANIZATION} (SSL)</p>"
            f"<p><b>Funding</b><br>{FUNDING_ACKNOWLEDGEMENT}</p>"
            f"<p><b>Funding PI</b><br>{FUNDING_PI}</p>"
            f'<p><b>Website</b><br><a href="{WEBSITE}">www.shafnehal.com</a></p>')
        self.credits.setTextFormat(Qt.RichText)
        self.credits.setWordWrap(True)
        self.credits.setMinimumHeight(280)
        self.credits.setOpenExternalLinks(True)
        self.credits.setTextInteractionFlags(Qt.TextBrowserInteraction)
        layout.addWidget(self.credits)
        layout.addStretch()
        actions = QDialogButtonBox(QDialogButtonBox.Close)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)

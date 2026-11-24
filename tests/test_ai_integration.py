"""Opt-in, real-model GUI smoke test; no source image is modified.

AI_SMOKE_IMAGE=/absolute/path/photo.jpg uv run --extra ai python -m unittest discover -s tests -p test_ai_integration.py -v
"""

import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog
from src.ai_assist import AIAssistDialog, set_review_decision
from src.exporters import ExportManager
from src.main_window import MainWindow

APP = QApplication.instance() or QApplication([])


@unittest.skipUnless(os.environ.get("AI_SMOKE_IMAGE"), "Set AI_SMOKE_IMAGE to run real-model inference")
class RealModelTests(unittest.TestCase):
    def test_generate_edit_approve_export_in_standalone_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = Path(os.environ["AI_SMOKE_IMAGE"]).resolve()
            shutil.copy2(source, folder / source.name)
            window = MainWindow()
            window.project_manager.create_project(str(folder))
            window.load_project_ui()
            window.project_manager.project.classes[0].name = "Maruca vitrata"
            window.update_class_list()
            window.show()
            dialog = AIAssistDialog(window)
            dialog.prompt.setText("a moth; an adult moth")
            dialog.show()
            APP.processEvents()
            dialog.grab().save("/tmp/annotation-ai-dialog.png")
            dialog.start()
            deadline = time.monotonic() + 180
            try:
                while dialog.process and dialog.process.state() != QProcess.NotRunning and time.monotonic() < deadline:
                    QTest.qWait(100)
                log = dialog.log.toPlainText()
                self.assertIsNotNone(dialog.process, log)
                self.assertEqual(dialog.process.state(), QProcess.NotRunning, log)
                self.assertTrue(dialog.received_complete, log)
                self.assertEqual(dialog.imported, 1, log)
                self.assertTrue(dialog.finalized, log)
                self.assertEqual(dialog.result(), QDialog.Accepted, log)
                self.assertFalse(dialog.cancelled, log)
                image = window.project_manager.get_current_image()
                self.assertEqual(image.review_decision(), "pending")
                self.assertGreater(len(image.annotations), 0, log)
                dialog.close()
                APP.processEvents()
                window.grab().save("/tmp/annotation-ai-review.png")
                set_review_decision(image, "approved")
                window.schedule_autosave()
                self.assertTrue(window.save_current_annotations())
                self.assertTrue(ExportManager.export_all(window.project_manager.project, folder / "project.json"))
                self.assertTrue((folder / "exports/voc/Annotations" / (source.stem + ".xml")).exists())
                print(f"Real-model smoke test: {len(image.annotations)} boxes; approved VOC export verified.")
            finally:
                if dialog.process and dialog.process.state() != QProcess.NotRunning:
                    dialog.process.kill()
                    dialog.process.waitForFinished(5000)
                dialog.close()
                window.close()

"""AI behavior tests run without downloading weights or installing PyTorch."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import sys
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtTest import QTest

from src.ai_assist import AIAssistDialog, make_draft, set_review_decision
from src.ai_backend import sanitize_boxes
from src.ai_worker import process, PREFIX
from src import ai_worker
from src.exporters import ExportManager
from src.main_window import MainWindow
from src.models import Annotation, ImageData
from src.project_manager import ProjectManager

APP = QApplication.instance() or QApplication([])
CONFIG = dict(prompts=["an adult moth"], box_threshold=0.35, text_threshold=0.25, nms_threshold=0.5)


class FakeDetector:
    revision = "test-revision"

    def __init__(self, config, device):
        pass

    def predict(self, image):
        return [dict(box=[-1, 4.4, 90.2, 120], score=0.9, prompt_label="moth")]


class AITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        Image.new("RGB", (100, 100)).save(self.folder / "a.jpg")
        self.window = MainWindow()
        self.window.project_manager.create_project(str(self.folder))
        self.window.load_project_ui()
        self.window.save_current_annotations()
        self.addCleanup(self.window.close)
        self.image = self.window.project_manager.get_current_image()
        self.cls = self.window.project_manager.project.classes[0]
        self.result = dict(filepath=self.image.filepath, width=100, height=100,
            source_sha256=hashlib.sha256(Path(self.image.filepath).read_bytes()).hexdigest(),
            boxes=[dict(box=[10, 20, 50, 60], score=0.8, prompt_label="moth")], model_revision="test")

    def draft(self):
        command = make_draft(self.image, self.result, self.cls, CONFIG)
        self.window.command_history.execute_command(command)
        self.window.set_current_image(0)
        self.window.schedule_autosave()
        return command

    def exported(self):
        self.assertTrue(ExportManager.export_all(self.window.project_manager.project,
                                                self.window.project_manager.project_path))
        return json.loads((self.folder / "exports/coco/annotations.json").read_text())

    def test_ai_drafts_require_approval_in_all_export_formats(self):
        self.draft()
        coco = self.exported()
        self.assertEqual(coco["images"], [])
        self.assertFalse((self.folder / "exports/voc/Annotations/a.xml").exists())
        self.assertFalse((self.folder / "exports/yolo/labels/a.txt").exists())
        set_review_decision(self.image, "approved")
        coco = self.exported()
        self.assertEqual(len(coco["annotations"]), 1)
        self.assertTrue((self.folder / "exports/voc/Annotations/a.xml").exists())
        self.assertTrue((self.folder / "exports/yolo/labels/a.txt").exists())

    def test_edits_invalidate_approval_and_remove_stale_exports(self):
        self.draft()
        set_review_decision(self.image, "approved")
        self.exported()
        self.image.annotations[0].x_min += 1
        self.assertEqual(self.image.review_decision(), "pending")
        self.assertEqual(self.exported()["images"], [])
        self.assertFalse((self.folder / "exports/voc/Annotations/a.xml").exists())
        self.assertFalse((self.folder / "exports/yolo/labels/a.txt").exists())

    def test_rejection_is_nondestructive_and_edits_reopen_review(self):
        self.draft()
        set_review_decision(self.image, "rejected")
        self.assertEqual(len(self.image.annotations), 1)
        self.assertFalse(self.image.can_export())
        self.assertTrue(Path(self.image.filepath).exists())
        self.image.annotations[0].class_name = "different label"
        self.assertEqual(self.image.review_decision(), "pending")

    def test_source_change_blocks_approval_and_export(self):
        self.draft()
        set_review_decision(self.image, "approved")
        Image.new("RGB", (100, 100), "red").save(self.image.filepath)
        self.assertEqual(self.exported()["images"], [])
        with self.assertRaisesRegex(ValueError, "source image changed"):
            set_review_decision(self.image, "approved")

    def test_empty_draft_is_not_a_verified_negative(self):
        self.result["boxes"] = []
        self.draft()
        self.assertFalse(self.image.can_export())
        with self.assertRaisesRegex(ValueError, "empty or invalid"):
            set_review_decision(self.image, "approved")

    def test_existing_manual_boxes_are_never_replaced(self):
        self.image.annotations.append(Annotation(x_min=1, y_min=1, x_max=20, y_max=20))
        with self.assertRaisesRegex(ValueError, "Existing annotations"):
            make_draft(self.image, self.result, self.cls, CONFIG)
        self.assertEqual(len(self.image.annotations), 1)

    def test_invalid_result_is_rejected_before_state_changes(self):
        self.result["boxes"].append(dict(box=[0, 0, 200, 20], score=0.9))
        with self.assertRaisesRegex(ValueError, "invalid box"):
            make_draft(self.image, self.result, self.cls, CONFIG)
        self.assertEqual(self.image.annotations, [])
        self.assertEqual(self.image.ai_review, {})

    def test_draft_application_undo_and_redo_restore_review_state(self):
        self.draft()
        self.window.undo()
        self.assertEqual(self.image.annotations, [])
        self.assertEqual(self.image.ai_review, {})
        self.window.redo()
        self.assertEqual(len(self.image.annotations), 1)
        self.assertEqual(self.image.review_decision(), "pending")

    def test_decisions_and_model_provenance_survive_reload(self):
        self.draft()
        set_review_decision(self.image, "approved")
        self.window.schedule_autosave()
        self.window.save_current_annotations()
        manager = ProjectManager()
        self.assertTrue(manager.load_project(str(self.folder / "project.json")))
        self.assertEqual(manager.project.images[0].review_decision(), "approved")
        self.assertEqual(manager.project.images[0].ai_review["model_revision"], "test")

    def test_legacy_projects_remain_manual_and_exportable(self):
        image = ImageData.from_dict(dict(filename="old.jpg", annotations=[]))
        self.assertEqual(image.review_decision(), "manual")
        self.assertTrue(image.can_export())

    def test_review_filters_match_effective_decisions(self):
        self.draft()
        self.window.image_filter.setCurrentIndex(3)
        self.assertFalse(self.window.image_list.item(0).isHidden())
        set_review_decision(self.image, "approved")
        self.window.update_status()
        self.assertTrue(self.window.image_list.item(0).isHidden())
        self.window.image_filter.setCurrentIndex(4)
        self.assertFalse(self.window.image_list.item(0).isHidden())

    def test_renaming_label_reopens_ai_approval(self):
        self.draft()
        set_review_decision(self.image, "approved")
        with patch("src.main_window.QInputDialog.getText", return_value=("Adult moth", True)):
            self.window.rename_selected_class()
        self.assertEqual(self.image.review_decision(), "pending")
        self.assertEqual(self.image.annotations[0].class_name, "Adult moth")
        self.assertFalse(self.image.can_export())

    def test_worker_reuses_one_model_and_reports_individual_errors(self):
        request = dict(config=CONFIG, device="cpu", images=[self.image.filepath, str(self.folder / "missing.jpg")])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            process(request, FakeDetector)
        events = [json.loads(line[len(PREFIX):]) for line in output.getvalue().splitlines()]
        self.assertEqual([e["event"] for e in events], ["status", "result", "image_error", "complete"])
        self.assertEqual(events[1]["boxes"][0]["box"], [0, 4, 91, 100])
        self.assertEqual(events[1]["source_sha256"], self.result["source_sha256"])

    def test_sanitizer_rejects_noise_and_suppresses_duplicate_boxes(self):
        boxes = [dict(box=[1, 2, 20, 30], score=0.9), dict(box=[1, 2, 20, 30], score=0.8),
                 dict(box=[1, 2, 20, 30], score=float("nan")), dict(box=[1, 1, 1, 1], score=0.9)]
        self.assertEqual(len(sanitize_boxes(boxes, 100, 100, 0.35, 0.5)), 1)

    def test_stopped_dialog_keeps_completed_drafts_and_enables_close(self):
        dialog = AIAssistDialog(self.window)
        dialog.targets = {str(Path(self.image.filepath).resolve()): self.image}
        dialog.class_definition = self.cls
        dialog.config = CONFIG
        dialog.handle_event(dict(self.result, event="result", completed=1))
        dialog.cancelled = True
        dialog.process = QProcess(dialog)
        dialog.close_button.setEnabled(False)
        dialog.on_worker_finished(15, QProcess.CrashExit)
        self.assertEqual(len(self.image.annotations), 1)
        self.assertTrue(dialog.close_button.isEnabled())
        self.assertIn("Stopped", dialog.log.toPlainText())
        dialog.close()

    def worker_dialog(self, events, linger=0):
        dialog = AIAssistDialog(self.window)
        self.addCleanup(dialog.close)
        dialog.targets = {str(Path(self.image.filepath).resolve()): self.image}
        dialog.class_definition = self.cls
        dialog.config = CONFIG
        dialog.progress.setRange(0, 1)
        dialog.close_button.setText("Stop")
        dialog.process = QProcess(dialog)
        dialog.process.readyReadStandardOutput.connect(dialog.read_output)
        dialog.process.readyReadStandardError.connect(dialog.read_errors)
        dialog.process.finished.connect(dialog.on_worker_finished)
        script = "import time\n" + "\n".join(
            f"print({(PREFIX + json.dumps(event))!r}, flush=True)" for event in events)
        script += f"\ntime.sleep({linger})\n"
        dialog.process.start(sys.executable, ["-u", "-c", script])
        self.assertTrue(dialog.process.waitForStarted(3000))
        self.addCleanup(self.stop_worker, dialog)
        return dialog

    @staticmethod
    def stop_worker(dialog):
        if dialog.process.state() != QProcess.NotRunning:
            dialog.process.kill()
            dialog.process.waitForFinished(3000)

    def wait_until_finished(self, dialog):
        deadline = time.monotonic() + 8
        while not dialog.finalized and time.monotonic() < deadline:
            QTest.qWait(25)
        self.assertTrue(dialog.finalized, dialog.log.toPlainText())

    def test_success_automatically_returns_to_review_without_stop(self):
        dialog = self.worker_dialog([dict(self.result, event="result", completed=1), dict(event="complete")])
        self.wait_until_finished(dialog)
        self.assertEqual(dialog.result(), QDialog.Accepted)
        self.assertFalse(dialog.cancelled)
        self.assertIn("Generation completed", dialog.status_label.text())
        self.assertEqual(self.image.review_decision(), "pending")
        self.assertEqual(dialog.progress.value(), 1)

    def test_completed_inference_does_not_wait_for_stalled_framework_exit(self):
        dialog = self.worker_dialog([dict(self.result, event="result", completed=1), dict(event="complete")], linger=30)
        deadline = time.monotonic() + 3
        while not dialog.received_complete and time.monotonic() < deadline:
            QTest.qWait(25)
        self.assertTrue(dialog.received_complete)
        self.assertEqual(dialog.close_button.text(), "Review Drafts")
        self.assertIn("Generation completed", dialog.status_label.text())
        self.wait_until_finished(dialog)
        self.assertEqual(dialog.result(), QDialog.Accepted)
        self.assertTrue(dialog.cleanup_requested)
        self.assertFalse(dialog.cancelled)
        self.assertNotIn("Stopped", dialog.log.toPlainText())

    def test_one_result_does_not_complete_a_still_running_batch(self):
        dialog = self.worker_dialog([dict(self.result, event="result", completed=1)], linger=30)
        deadline = time.monotonic() + 3
        while not dialog.imported and time.monotonic() < deadline:
            QTest.qWait(25)
        self.assertEqual(dialog.imported, 1)
        self.assertFalse(dialog.received_complete)
        self.assertEqual(dialog.close_button.text(), "Stop")
        self.assertFalse(dialog.cleanup_timer.isActive())
        dialog.reject()
        self.wait_until_finished(dialog)
        self.assertTrue(dialog.cancelled)

    def test_completion_with_errors_stays_open_for_inspection(self):
        dialog = self.worker_dialog([dict(event="image_error", message="Unreadable image", completed=1), dict(event="complete")])
        self.wait_until_finished(dialog)
        self.assertNotEqual(dialog.result(), QDialog.Accepted)
        self.assertEqual(dialog.close_button.text(), "Close")
        self.assertIn("1 error(s)", dialog.status_label.text())

    def test_failed_save_does_not_hide_completion_dialog(self):
        dialog = AIAssistDialog(self.window)
        dialog.handle_event(dict(event="complete"))
        with patch.object(self.window, "save_current_annotations", return_value=False):
            dialog.on_worker_finished(0, QProcess.NormalExit)
        self.assertNotEqual(dialog.result(), QDialog.Accepted)
        self.assertIn("could not be saved", dialog.status_label.text())
        dialog.close()

    def test_windowed_worker_emits_events_without_stdout_or_stderr(self):
        request = self.folder / "request.json"
        request.write_text(json.dumps({}))
        events, log = self.folder / "events.jsonl", self.folder / "worker.log"

        def fake_process(config):
            print("Model loading log")
            ai_worker.emit("status", message="Loading")
            ai_worker.emit("complete")

        with patch("sys.argv", ["worker", "--request", str(request), "--events", str(events), "--log-file", str(log)]), \
             patch("sys.stdout", None), patch("sys.stderr", None), patch("src.ai_worker.process", side_effect=fake_process):
            code = ai_worker.main()
        self.assertEqual(code, 0)
        rows = [json.loads(line[len(PREFIX):]) for line in events.read_text().splitlines()]
        self.assertEqual([row["event"] for row in rows], ["status", "complete"])
        self.assertIn("Model loading log", log.read_text())

    def test_manual_executable_explains_how_to_get_ai_edition(self):
        dialog = AIAssistDialog(self.window)
        with patch("src.ai_assist.importlib.util.find_spec", return_value=None), \
             patch("src.ai_assist.sys.frozen", True, create=True), \
             patch("src.ai_assist.QMessageBox.information") as message:
            dialog.start()
        self.assertIn("AI edition", message.call_args.args[2])
        self.assertIsNone(dialog.process)
        dialog.close()

    def test_file_event_channel_handles_partial_lines_without_duplicate_drafts(self):
        events = self.folder / "events.jsonl"
        payload = PREFIX + json.dumps(dict(self.result, event="result", completed=1)) + "\n"
        dialog = AIAssistDialog(self.window)
        dialog.targets = {str(Path(self.image.filepath).resolve()): self.image}
        dialog.config, dialog.class_definition = CONFIG, self.cls
        dialog.event_files = {events: 0}
        events.write_text(payload[:20])
        dialog.read_event_files()
        self.assertEqual(dialog.imported, 0)
        with events.open("a") as output:
            output.write(payload[20:])
        dialog.read_event_files()
        dialog.read_event_files()
        self.assertEqual(dialog.imported, 1)
        self.assertEqual(dialog.errors, 0)
        dialog.close()


if __name__ == "__main__":
    unittest.main()

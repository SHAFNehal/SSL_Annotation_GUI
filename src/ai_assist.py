"""AI draft configuration, asynchronous execution, and safe result import."""

from copy import deepcopy
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QLineEdit, QDoubleSpinBox, QLabel, QPushButton, QHBoxLayout, QProgressBar,
    QPlainTextEdit, QMessageBox)

from .ai_backend import MODEL
from .commands import ApplyAIDraftCommand
from .models import Annotation
from .branding import EXECUTABLE_NAME


def make_draft(image, result, class_definition, config):
    """Validate the entire response before touching an image's working state."""
    if image.annotations:
        raise ValueError("Existing annotations were preserved; AI only fills empty images.")
    if Path(image.filepath).resolve() != Path(result["filepath"]).resolve():
        raise ValueError("AI result belongs to a different image.")
    if (result["width"], result["height"]) != (image.width, image.height):
        raise ValueError("Image dimensions changed; draft discarded.")
    digest = hashlib.sha256(Path(image.filepath).read_bytes()).hexdigest()
    if digest != result["source_sha256"]:
        raise ValueError("Source image changed; draft discarded.")
    annotations = []
    for item in result["boxes"]:
        box = item["box"]
        if (len(box) != 4 or any(type(v) is not int for v in box)
                or not (0 <= box[0] < box[2] <= image.width and 0 <= box[1] < box[3] <= image.height)
                or not math.isfinite(item["score"]) or not 0 <= item["score"] <= 1):
            raise ValueError("AI returned invalid box coordinates or confidence.")
        annotations.append(Annotation(class_id=class_definition.id, class_name=class_definition.name,
                                      x_min=box[0], y_min=box[1], x_max=box[2], y_max=box[3]))
    review = dict(decision="pending", model=MODEL, model_revision=result.get("model_revision"),
                  source_sha256=digest, config=deepcopy(config), proposals=deepcopy(result["boxes"]),
                  exif_orientation=result.get("exif_orientation", 1),
                  generated_at=datetime.utcnow().isoformat() + "Z")
    return ApplyAIDraftCommand(image, annotations, review)


def set_review_decision(image, decision):
    if not image or not image.ai_review or decision not in {"approved", "rejected", "pending"}:
        raise ValueError("Select an AI-assisted image first.")
    if decision == "approved":
        if not image.annotations or not all(ann.is_valid() and 0 <= ann.x_min < ann.x_max <= image.width
                and 0 <= ann.y_min < ann.y_max <= image.height for ann in image.annotations):
            raise ValueError("An empty or invalid draft cannot be approved. Draw or correct its boxes first.")
        if hashlib.sha256(Path(image.filepath).read_bytes()).hexdigest() != image.ai_review.get("source_sha256"):
            raise ValueError("The source image changed since inference; generate a new draft before approving.")
    image.ai_review.update(decision=decision, reviewed_fingerprint=image.annotation_fingerprint(),
                           reviewed_at=datetime.utcnow().isoformat() + "Z")


class AIAssistDialog(QDialog):
    """Modal controls prevent simultaneous edits; QProcess keeps Qt responsive."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("AI Assist")
        self.resize(580, 580)
        self.process = None
        self.temp = None
        self.stdout = bytearray()
        self.cancelled = False
        self.received_complete = False
        self.failed = False
        self.imported = 0
        self.errors = 0
        self.targets = {}
        self.finalized = False
        self.cleanup_requested = False
        self.review_requested = False
        self.event_files = {}
        self.events_timer = QTimer(self)
        self.events_timer.setInterval(100)
        self.events_timer.timeout.connect(self.read_event_files)
        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.setSingleShot(True)
        self.cleanup_timer.setInterval(1500)
        self.cleanup_timer.timeout.connect(self.cleanup_completed_worker)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        title = QLabel("Let AI draft. You review.")
        title.setObjectName("appTitle")
        layout.addWidget(title)
        note = QLabel("Grounding DINO proposes boxes from your description. It does not verify species. "
                      "Existing labels are never replaced. Review, correct, then approve each image before export. "
                      "First use downloads model weights; images stay on this computer.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.scope = QComboBox()
        self.scope.addItems(["Current image", "All unannotated, unprocessed images"])
        form.addRow("Images", self.scope)
        self.label_choice = QComboBox()
        for cls in window.project_manager.project.classes:
            self.label_choice.addItem(cls.name, cls.id)
        self.label_choice.setCurrentIndex(max(0, self.label_choice.findData(window.class_combo.currentData())))
        form.addRow("Species label", self.label_choice)
        self.prompt = QLineEdit("an adult insect")
        self.prompt.setPlaceholderText("e.g. a moth; an adult moth")
        form.addRow("Visual description", self.prompt)
        self.device = QComboBox()
        self.device.addItems(["auto", "cpu", "cuda:0", "cuda:1"])
        form.addRow("Device", self.device)
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.05, 0.95)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(0.35)
        form.addRow("Box confidence", self.threshold)
        layout.addLayout(form)
        self.status_label = QLabel("Ready to generate drafts.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setObjectName("aiProgress")
        self.progress.setTextVisible(True)
        self.progress.setRange(0, 1)
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(150)
        layout.addWidget(self.log, 1)
        actions = QHBoxLayout()
        self.run_button = QPushButton("Generate Drafts")
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(self.start)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        actions.addStretch()
        actions.addWidget(self.close_button)
        actions.addWidget(self.run_button)
        layout.addLayout(actions)

    def start(self):
        if any(importlib.util.find_spec(name) is None for name in ("torch", "torchvision", "transformers")):
            if getattr(sys, "frozen", False):
                QMessageBox.information(self, "AI Edition Required", "This executable does not include AI libraries. "
                    f"Download the AI edition ({EXECUTABLE_NAME}-ai-...) from the GitHub Actions artifacts, "
                    f"extract its complete archive, and launch {EXECUTABLE_NAME}-AI.")
                return
            QMessageBox.information(self, "Install AI Support", "From the Annotation_GUI_Tool folder run:\n\n"
                "uv sync --extra ai\nuv run --extra ai python main.py\n\nManual annotation does not require these optional dependencies.")
            return
        cls = self.window.project_manager.get_class(self.label_choice.currentData())
        prompts = [value.strip() for value in self.prompt.text().split(";") if value.strip()]
        if not cls or not prompts:
            QMessageBox.warning(self, "Missing Settings", "Choose a species label and enter a visual description.")
            return
        project = self.window.project_manager.project
        if self.scope.currentIndex() == 0:
            current = self.window.project_manager.get_current_image()
            images = [current] if current and not current.annotations else []
        else:
            images = [image for image in project.images if not image.annotations and not image.ai_review]
        if not images:
            QMessageBox.information(self, "No Eligible Images", "There are no empty images in this selection. "
                                    "AI Assist never replaces existing boxes.")
            return
        if images[0].ai_review and self.scope.currentIndex() == 0:
            if QMessageBox.question(self, "Replace Empty Draft", "Replace this image's previous AI review with a new draft?",
                                    QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
                return
        if not self.window.save_current_annotations():
            QMessageBox.warning(self, "Save Failed", "Save the project before generating drafts.")
            return
        self.class_definition = deepcopy(cls)
        self.config = dict(prompts=prompts, box_threshold=self.threshold.value(), text_threshold=0.25, nms_threshold=0.5)
        self.targets = {str(Path(image.filepath).resolve()): image for image in images}
        request = dict(config=self.config, device=self.device.currentText(), images=list(self.targets))
        self.temp = tempfile.TemporaryDirectory(prefix="annotation-ai-")
        request_path = Path(self.temp.name) / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        self.progress.setRange(0, len(images))
        self.progress.setValue(0)
        self.run_button.setEnabled(False)
        for control in (self.scope, self.label_choice, self.prompt, self.device, self.threshold):
            control.setEnabled(False)
        self.close_button.setText("Stop")
        self.status_label.setText("Generating drafts...")
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(Path(__file__).resolve().parents[1]))
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_errors)
        self.process.finished.connect(self.on_worker_finished)
        self.process.errorOccurred.connect(self.process_error)
        if getattr(sys, "frozen", False):
            events = Path(self.temp.name) / "events.jsonl"
            log_file = Path(self.temp.name) / "worker.log"
            self.event_files = {events: 0, log_file: 0}
            arguments = ["--ai-worker", "--request", str(request_path), "--events", str(events), "--log-file", str(log_file)]
            self.events_timer.start()
        else:
            arguments = ["-u", "-m", "src.ai_worker", "--request", str(request_path)]
        self.process.start(sys.executable, arguments)
        self.log.appendPlainText(f"Preparing {len(images)} image(s). Completed drafts will be autosaved as pending review.")

    def read_output(self):
        if not self.process or not self.process.isOpen():
            return
        self.stdout.extend(bytes(self.process.readAllStandardOutput()))
        self.consume_events()

    def consume_events(self):
        while b"\n" in self.stdout:
            line, _, self.stdout = self.stdout.partition(b"\n")
            text = line.decode("utf-8", errors="replace")
            if not text.startswith("ANNOTATION_AI "):
                continue
            try:
                self.handle_event(json.loads(text[len("ANNOTATION_AI "):]))
            except (ValueError, TypeError, KeyError, OSError) as exc:
                self.errors += 1
                self.log.appendPlainText("Draft not applied: " + str(exc))

    def read_event_files(self):
        """Windowed PyInstaller applications may have no Python stdout/stderr."""
        for path, offset in list(self.event_files.items()):
            if not path.exists():
                continue
            with path.open("rb") as handle:
                handle.seek(offset)
                data = handle.read()
                self.event_files[path] = handle.tell()
            if path.suffix == ".jsonl":
                self.stdout.extend(data)
                self.consume_events()
            elif data:
                self.log.appendPlainText(data.decode("utf-8", errors="replace").strip())

    def handle_event(self, event):
        if "completed" in event:
            self.progress.setValue(event["completed"])
        kind = event["event"]
        if kind == "result":
            image = self.targets[str(Path(event["filepath"]).resolve())]
            command = make_draft(image, event, self.class_definition, self.config)
            if image is self.window.project_manager.get_current_image():
                self.window.command_history.execute_command(command)
                self.window.set_current_image(self.window.project_manager.current_image_index)
            else:
                command.execute()
            self.window.schedule_autosave()
            self.imported += 1
            self.log.appendPlainText(f"{image.filename}: {len(image.annotations)} boxes; review required.")
            if event.get("exif_orientation", 1) not in (None, 1):
                self.log.appendPlainText("Check orientation: boxes use original decoded pixel coordinates.")
        elif kind in {"status", "image_error", "fatal"}:
            if kind != "status":
                self.errors += 1
            if kind == "fatal":
                self.failed = True
            self.log.appendPlainText(event.get("filepath", "") + " " + event["message"])
        elif kind == "complete":
            if self.received_complete:
                return
            self.received_complete = True
            self.progress.setValue(self.progress.maximum())
            message = f"Generation completed: {self.imported} draft(s), {self.errors} error(s). Ready for review."
            self.status_label.setText(message)
            self.log.appendPlainText(message)
            self.close_button.setText("Review Drafts" if self.imported else "Close")
            self.close_button.setEnabled(True)
            self.window.statusBar().showMessage(message, 8000)
            # Inference is done. Framework shutdown must not leave the UI on Stop.
            if self.process and self.process.state() != QProcess.NotRunning:
                self.cleanup_timer.start()

    def read_errors(self):
        if not self.process or not self.process.isOpen():
            return
        message = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        if message.strip():
            self.log.appendPlainText(message.strip())

    def process_error(self, error):
        if error == QProcess.FailedToStart:
            self.failed = True
            self.log.appendPlainText("Could not start AI worker: " + self.process.errorString())
            self.on_worker_finished(-1, QProcess.CrashExit)

    def on_worker_finished(self, code, status):
        """Handle worker exit without shadowing QDialog's own finished signal."""
        if self.finalized:
            return
        self.read_output()
        self.read_errors()
        self.read_event_files()
        self.finalized = True
        self.events_timer.stop()
        self.cleanup_timer.stop()
        completed = self.received_complete and not self.failed and not self.cancelled and (code == 0 or self.cleanup_requested)
        if self.cancelled:
            message = "Stopped. Completed drafts are retained; unfinished images were not changed."
        elif not completed:
            message = "AI Assist did not finish. See the log above; completed drafts are retained."
        else:
            message = f"Generation completed: {self.imported} draft(s), {self.errors} error(s). Review and approve the boxes."
        self.log.appendPlainText(message)
        self.status_label.setText(message)
        saved = self.window.save_current_annotations()
        if not saved:
            self.log.appendPlainText("Project save failed. Drafts remain in memory; save the project before closing the app.")
            self.status_label.setText("Drafts generated, but the project could not be saved. See the log.")
        self.close_button.setText("Review Drafts" if self.imported else "Close")
        self.close_button.setEnabled(True)
        if self.temp:
            self.temp.cleanup()
            self.temp = None
        if completed and saved and (self.errors == 0 or self.review_requested):
            self.window.statusBar().showMessage(message, 8000)
            self.accept()

    def cleanup_completed_worker(self):
        """Bound framework teardown after its explicit inference-complete message."""
        if self.received_complete and self.process and self.process.state() != QProcess.NotRunning:
            self.cleanup_requested = True
            self.process.terminate()
            QTimer.singleShot(1000, self.kill_if_running)

    def reject(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            if self.received_complete:
                self.review_requested = True
                self.cleanup_completed_worker()
                return
            self.cancelled = True
            self.close_button.setEnabled(False)
            self.log.appendPlainText("Stopping AI worker...")
            self.process.terminate()
            QTimer.singleShot(3000, self.kill_if_running)
            return
        super().reject()

    def kill_if_running(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.kill()

    def closeEvent(self, event):
        if self.process and self.process.state() != QProcess.NotRunning:
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)

"""Main application window"""
from PySide6.QtCore import Qt, QTimer, QSignalBlocker
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QComboBox,
    QMessageBox, QFileDialog, QMenu, QInputDialog, QColorDialog
)
from pathlib import Path
from typing import Optional

from .project_manager import ProjectManager
from .annotation_scene import AnnotationScene
from .image_viewer import ImageViewer
from .commands import CommandHistory, CreateBoxCommand, DeleteBoxCommand, DeleteBoxesCommand, ResizeBoxCommand, ChangeClassCommand
from .exporters import ExportManager
from .models import Annotation
from . import workspace_ui
from .theme import apply_theme
from .branding import APP_NAME, LOGO_PATH


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME + "[*]")
        self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.setMinimumSize(900, 600)
        self.resize(1280, 800)
        
        # Core components
        self.project_manager = ProjectManager()
        self.command_history = CommandHistory()
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(1000)
        self.autosave_timer.timeout.connect(self.save_current_annotations)
        self.scene: Optional[AnnotationScene] = None
        self.viewer: Optional[ImageViewer] = None
        
        # UI components
        self.image_list: Optional[QListWidget] = None
        self.class_list: Optional[QListWidget] = None
        self.class_combo: Optional[QComboBox] = None
        self.status_label: Optional[QLabel] = None
        
        self.setup_ui()
        self.setup_shortcuts()
        apply_theme(self)
        self.update_status()
        
    def setup_ui(self):
        """Setup user interface"""
        # Menu bar
        self.create_menu_bar()
        
        # Status bar
        self.create_status_bar()
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(workspace_ui.header(self))
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.addWidget(content, 1)
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        content_layout.addWidget(splitter)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        
        # Left sidebar
        left_panel = workspace_ui.image_panel(self)
        splitter.addWidget(left_panel)
        splitter.setStretchFactor(0, 0)
        
        # Center canvas
        center_panel = workspace_ui.canvas_panel(self)
        splitter.addWidget(center_panel)
        splitter.setStretchFactor(1, 1)
        
        # Right panel
        right_panel = workspace_ui.labels_panel(self)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(2, 0)
        
        # Set splitter sizes
        splitter.setSizes([235, 780, 245])
        
    def create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction("&Open Folder...", self.open_folder, QKeySequence.Open)
        file_menu.addAction("&Save Project", self.save_project, QKeySequence.Save)
        file_menu.addAction("&Export Annotations...", self.export_annotations, "Ctrl+Shift+E")
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close, QKeySequence.Quit)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction("&Undo", self.undo, QKeySequence.Undo)
        edit_menu.addAction("&Redo", self.redo, QKeySequence.Redo)
        edit_menu.addSeparator()
        edit_menu.addAction("Select &All", self.select_all_boxes, QKeySequence.SelectAll)
        edit_menu.addAction("&Delete Selected", self.delete_selected_boxes, QKeySequence.Delete)
        ai_menu = menubar.addMenu("&AI")
        ai_menu.addAction("Generate &Drafts...", self.open_ai_assist)
        ai_menu.addAction("&Approve Current Draft", lambda: self.review_ai_image("approved"))
        ai_menu.addAction("&Reject Current Draft", lambda: self.review_ai_image("rejected"))
        ai_menu.addAction("Reset Current &Review", lambda: self.review_ai_image("pending"))
        
        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction("Fit to &Window", self.fit_to_window, "Ctrl+0")
        view_menu.addAction("&100% Zoom", self.zoom_100, "Ctrl+1")
        view_menu.addAction("Zoom &In", self.zoom_in, "Ctrl++")
        view_menu.addAction("Zoom &Out", self.zoom_out, "Ctrl+-")
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About", self.show_about)
        help_menu.addAction("Keyboard &Shortcuts", self.show_shortcuts)
        
        
    def create_status_bar(self):
        """Create status bar"""
        self.statusBar().showMessage("Ready")
        self.status_label = QLabel("No project loaded")
        self.statusBar().addPermanentWidget(self.status_label)
        
        
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Tool shortcuts
        QShortcut("S", self, lambda: self.set_tool("select"))
        QShortcut("B", self, lambda: self.set_tool("box"))
        QShortcut("H", self, lambda: self.set_tool("pan"))
        
        # Navigation
        QShortcut("Left", self, self.previous_image)
        QShortcut("Right", self, self.next_image)
        QShortcut("A", self, self.previous_image)
        QShortcut("D", self, self.next_image)
        QShortcut("Home", self, lambda: self.set_current_image(0))
        QShortcut("End", self, lambda: self.set_current_image(len(self.project_manager.project.images) - 1 if self.project_manager.project else 0))
        
        # Number keys for classes
        for i in range(10):
            QShortcut(str(i), self, lambda idx=i: self.assign_class_by_index(idx))
            
        # Box operations
        QShortcut("Escape", self, self.deselect_all_boxes)
        
    def open_folder(self):
        """Open image folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if not folder:
            return
        if not self.save_current_annotations():
            QMessageBox.warning(self, "Save Failed", "The current project could not be saved. The folder was not changed.")
            return

        folder_path = Path(folder)
        try:
            project_path = self.project_manager.project_path_for_folder(folder_path)
        except ValueError as exc:
            QMessageBox.warning(self, "Project Not Opened", str(exc))
            return

        if project_path.exists():
            # Load existing project for this folder, then sync additions/deletions
            if self.project_manager.load_project(str(project_path)):
                new_count, removed_count = self.project_manager.sync_new_images()
                self.load_project_ui()
                msg = f"Loaded existing project with {len(self.project_manager.project.images)} images."
                if new_count > 0:
                    msg += f"\n{new_count} new image(s) added to the project."
                if removed_count > 0:
                    msg += f"\n{removed_count} deleted image(s) and their annotations removed."
                self.statusBar().showMessage(msg.replace("\n", " "), 8000)
            else:
                QMessageBox.warning(self, "Error", "Failed to load existing project.")
        else:
            # Different folder or no project.json yet — create a fresh project
            if self.project_manager.create_project(folder, str(project_path)):
                self.load_project_ui()
                total_annotations = sum(len(img.annotations) for img in self.project_manager.project.images)
                if total_annotations > 0:
                    self.statusBar().showMessage(f"Imported {total_annotations} existing annotations.", 8000)
            else:
                QMessageBox.warning(self, "Error", "Failed to load images from folder")

    def open_ai_assist(self):
        if not self.project_manager.project or not self.project_manager.project.images:
            QMessageBox.information(self, "Open Images First", "Open an image folder before using AI Assist.")
            return
        from .ai_assist import AIAssistDialog
        dialog = AIAssistDialog(self)
        dialog.exec()
        self.update_status()
        self.update_box_properties()

    def review_ai_image(self, decision):
        from .ai_assist import set_review_decision
        try:
            set_review_decision(self.project_manager.get_current_image(), decision)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Review Not Saved", str(exc))
            return
        self.schedule_autosave()
        self.update_status()
            
    def load_project_ui(self):
        """Load project UI"""
        if not self.project_manager.project:
            return
        self.command_history.clear()
            
        # Load image list
        self.image_list.clear()
        for i, img_data in enumerate(self.project_manager.project.images):
            item = QListWidgetItem(img_data.filename)
            item.setData(Qt.UserRole, i)
            item.setToolTip(img_data.filename)
            self.image_list.addItem(item)
            
        # Load class list
        self.update_class_list()
        
        # Load first image
        if self.project_manager.project.images:
            self.set_current_image(0)
            
        self.update_status()
        if self.project_manager.is_dirty:
            self.schedule_autosave()
        
    def update_class_list(self):
        """Update class list widget"""
        active_id = self.class_combo.currentData()
        selected = self.class_list.currentItem()
        selected_id = selected.data(Qt.UserRole) if selected else None
        blocker = QSignalBlocker(self.class_combo)
        self.class_list.clear()
        self.class_combo.clear()
        
        if not self.project_manager.project:
            return
            
        for i, cls in enumerate(self.project_manager.project.classes):
            # List widget
            item = QListWidgetItem(f"{i}: {cls.name}")
            item.setData(Qt.UserRole, cls.id)
            color = QColor(cls.color)
            item.setForeground(color)
            self.class_list.addItem(item)
            
            # Combo box
            self.class_combo.addItem(cls.name, cls.id)
            if cls.id == selected_id:
                self.class_list.setCurrentItem(item)
        active_index = self.class_combo.findData(active_id)
        if active_index >= 0:
            self.class_combo.setCurrentIndex(active_index)
            
    def set_current_image(self, index: int):
        """Set current image"""
        project = self.project_manager.project
        if not project or not 0 <= index < len(project.images):
            return
        if index != self.project_manager.current_image_index:
            if not self.save_current_annotations():
                self.image_list.setCurrentRow(self.project_manager.current_image_index)
                self.update_status()
                return
            self.command_history.clear()
        if not self.project_manager.set_current_image(index):
            return
            
        image_data = self.project_manager.get_current_image()
        if not image_data:
            return
            
        # Load image in scene
        if not self.scene.load_image(image_data):
            self.canvas_stack.setCurrentIndex(0)
            self.statusBar().showMessage(f"Could not load image: {image_data.filepath}")
            return
        self.canvas_stack.setCurrentIndex(1)
        if self.image_list.item(index).isHidden():
            self.image_search.clear()
            self.image_filter.setCurrentIndex(0)
        self.viewer.fit_to_window()
        
        # Update image list selection
        self.image_list.setCurrentRow(index)
                
        self.update_status()
        self.update_box_properties()
        
    def next_image(self):
        """Navigate to next image"""
        if not self.project_manager.project:
            return
        current = self.project_manager.current_image_index
        for index in range(current + 1, self.image_list.count()):
            if not self.image_list.item(index).isHidden():
                self.set_current_image(index)
                break
            
    def previous_image(self):
        """Navigate to previous image"""
        if not self.project_manager.project:
            return
        current = self.project_manager.current_image_index
        for index in range(current - 1, -1, -1):
            if not self.image_list.item(index).isHidden():
                self.set_current_image(index)
                break
            
    def save_current_annotations(self):
        """Save current image annotations"""
        self.autosave_timer.stop()
        if not self.project_manager.project:
            return True
        
        # Ensure current image annotations are synced from scene
        if self.scene and self.scene.current_image_data:
            image_data = self.project_manager.get_current_image()
            if image_data is self.scene.current_image_data:
                # Sync annotations from scene to project (they should already be the same reference)
                # But ensure all boxes in scene are in the annotations list
                scene_annotations = [box_item.annotation for box_item in self.scene.box_items]
                # Update the annotations list to match scene
                if image_data.annotations != scene_annotations:
                    image_data.annotations = scene_annotations
                    self.project_manager.mark_dirty()
        
        was_dirty = self.project_manager.is_dirty
        if not self.project_manager.save_project():
            self.set_save_badge("Save failed", "error")
            self.statusBar().showMessage("Save failed: " + self.project_manager.last_error)
            return False
        self.setWindowModified(False)
        self.set_save_badge("Saved")
        if was_dirty:
            self.statusBar().showMessage("Project saved. Export annotations when ready.", 4000)
        return True

    def schedule_autosave(self):
        if self.project_manager.project:
            self.project_manager.mark_dirty()
            self.setWindowModified(True)
            self.set_save_badge("Unsaved changes", "unsaved")
            self.autosave_timer.start()
            self.update_status()

    def set_save_badge(self, text, state=""):
        self.save_badge.setText(text)
        self.save_badge.setProperty("state", state)
        self.save_badge.style().unpolish(self.save_badge)
        self.save_badge.style().polish(self.save_badge)

    def export_annotations(self):
        if not self.project_manager.project:
            return
        if not self.save_current_annotations():
            QMessageBox.warning(self, "Export Failed", "Save the project successfully before exporting.")
            return
        if ExportManager.export_all(self.project_manager.project, self.project_manager.project_path):
            destination = self.project_manager.project_path.parent / "exports"
            skipped = sum(not image.can_export() for image in self.project_manager.project.images)
            self.statusBar().showMessage(f"Annotations exported to {destination}. {skipped} unapproved AI image(s) excluded.", 8000)
        else:
            QMessageBox.warning(self, "Export Failed", "Annotations could not be exported. Your project remains saved.")
                
    def set_tool(self, tool: str):
        """Set current tool"""
        self.viewer.set_tool(tool)
        self.select_tool_btn.setChecked(tool == "select")
        self.box_tool_btn.setChecked(tool == "box")
        self.pan_tool_btn.setChecked(tool == "pan")
        self.tool_hint.setText({
            "select": "Select a box to move it, resize its corners, or change its label.",
            "box": "Drag around an object to draw a box. Choose its label on the right.",
            "pan": "Drag to explore the image. Use Ctrl + mouse wheel to zoom."
        }[tool])
        
    def on_image_list_double_click(self, item: QListWidgetItem):
        """Open the clicked image; restore selection if saving blocks navigation."""
        index = item.data(Qt.UserRole)
        self.set_current_image(index)
        self.image_list.setCurrentRow(self.project_manager.current_image_index)
        
    def on_box_created(self, annotation: Annotation):
        """Handle box creation"""
        # Create command
        image_data = self.project_manager.get_current_image()
        if image_data:
            cls = self.project_manager.get_class(self.class_combo.currentData())
            if cls:
                annotation.class_id, annotation.class_name = cls.id, cls.name
            cmd = CreateBoxCommand(image_data, annotation)
            self.command_history.execute_command(cmd)
            self.scene.update_box_colors()
            self.scene.clearSelection()
            for item in self.scene.box_items:
                if item.annotation is annotation:
                    item.setSelected(True)
            
            # Force view update to show the new box
            if self.viewer:
                self.viewer.viewport().update()
                self.viewer.update()
            if self.scene:
                self.scene.update()
                
            self.update_status()
            self.update_box_properties()
            
    def select_all_boxes(self):
        """Select all boxes"""
        if self.scene:
            self.scene.select_all_boxes()
            self.update_box_properties()

    def on_box_edited(self, annotation, before):
        image = self.project_manager.get_current_image()
        if image is None:
            return
        command = ResizeBoxCommand(annotation, annotation.x_min, annotation.y_min,
                                   annotation.x_max, annotation.y_max, image.width, image.height)
        command.old_x_min, command.old_y_min, command.old_x_max, command.old_y_max = before
        self.command_history.execute_command(command)
        self.schedule_autosave()
        self.update_box_properties()
            
    def deselect_all_boxes(self):
        """Deselect all boxes"""
        if self.scene:
            self.scene.deselect_all_boxes()
            self.update_box_properties()
            
    def delete_selected_boxes(self):
        """Delete selected boxes"""
        if not self.scene:
            return
        selected = self.scene.get_selected_boxes()
        if not selected:
            return
            
        image_data = self.project_manager.get_current_image()
        if not image_data:
            return
            
        # Create command
        if len(selected) == 1:
            cmd = DeleteBoxCommand(image_data, selected[0])
        else:
            cmd = DeleteBoxesCommand(image_data, selected)
        self.command_history.execute_command(cmd)
        
        # Remove from scene
        for box_item in self.scene.box_items[:]:
            if box_item.annotation in selected:
                self.scene.remove_box_item(box_item)
                
        self.update_status()
        self.update_box_properties()
        self.schedule_autosave()
        
    def on_class_double_click(self, item: QListWidgetItem):
        """Handle class double click - assign to selected boxes"""
        class_id = item.data(Qt.UserRole)
        self.assign_class(class_id)
        
    def assign_class_by_index(self, index: int):
        """Assign class by index (0-9)"""
        if not self.project_manager.project:
            return
        if 0 <= index < len(self.project_manager.project.classes):
            class_id = self.project_manager.project.classes[index].id
            self.assign_class(class_id)
            
    def assign_class(self, class_id: int):
        """Assign class to selected boxes"""
        if not self.scene or not self.project_manager.project:
            return
        selected = self.scene.get_selected_boxes()
        # Get class name
        cls = self.project_manager.get_class(class_id)
        if not cls:
            return
        with QSignalBlocker(self.class_combo):
            self.class_combo.setCurrentIndex(self.class_combo.findData(class_id))
        if not selected:
            return
            
        # Create command
        cmd = ChangeClassCommand(selected, class_id, cls.name)
        self.command_history.execute_command(cmd)
        
        # Update scene
        self.scene.update_box_colors()
        self.update_box_properties()
        self.schedule_autosave()
        
    def on_class_changed(self, index: int):
        """Handle class combo box change"""
        if index < 0:
            return
        class_id = self.class_combo.itemData(index)
        if class_id is not None:
            self.assign_class(class_id)
            
    def update_box_properties(self):
        """Update box properties panel"""
        if not self.scene:
            self.box_info_label.setText("No box selected")
            return
            
        selected = self.scene.get_selected_boxes()
        self.delete_box_btn.setEnabled(bool(selected))
        if not selected:
            self.box_info_label.setText("Select a box to edit, or draw a new box.")
            return
            
        if len(selected) == 1:
            ann = selected[0]
            self.box_info_label.setText(
                f"Class: {ann.class_name}\n"
                f"x_min: {ann.x_min}, y_min: {ann.y_min}\n"
                f"x_max: {ann.x_max}, y_max: {ann.y_max}"
            )
            # Set combo to current class
            for i in range(self.class_combo.count()):
                if self.class_combo.itemData(i) == ann.class_id:
                    blocker = QSignalBlocker(self.class_combo)
                    self.class_combo.setCurrentIndex(i)
                    break
        else:
            self.box_info_label.setText(f"{len(selected)} boxes selected")
            
    def add_class(self):
        """Add a new class"""
        if not self.project_manager.project:
            return
        name, ok = QInputDialog.getText(self, "Add Class", "Class name:")
        if not ok or not name:
            return
        color = QColorDialog.getColor(QColor("#FF0000"), self, "Select Color")
        if not color.isValid():
            return
        class_id = self.project_manager.add_class(name, color.name())
        self.update_class_list()
        self.schedule_autosave()
        
    def show_class_context_menu(self, pos):
        """Show class context menu"""
        item = self.class_list.itemAt(pos)
        if not item:
            return
        class_id = item.data(Qt.UserRole)
        
        menu = QMenu(self)
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")
        action = menu.exec_(self.class_list.mapToGlobal(pos))
        
        if action == edit_action:
            self.edit_class(class_id)
        elif action == delete_action:
            self.delete_class(class_id)
            
    def edit_class(self, class_id: int):
        """Edit a class"""
        cls = self.project_manager.get_class(class_id)
        if not cls:
            return
        name, ok = QInputDialog.getText(self, "Edit Class", "Class name:", text=cls.name)
        if ok and name:
            cls.name = name
            for image in self.project_manager.project.images:
                for annotation in image.annotations:
                    if annotation.class_id == class_id:
                        annotation.class_name = name
            color = QColorDialog.getColor(QColor(cls.color), self, "Select Color")
            if color.isValid():
                cls.color = color.name()
            self.update_class_list()
            self.scene.update_box_colors()
            self.command_history.clear()
            self.schedule_autosave()

    def rename_selected_class(self):
        """Rename a label project-wide, without requiring a color change."""
        if not self.project_manager.project:
            return
        selected = self.class_list.currentItem()
        class_id = selected.data(Qt.UserRole) if selected else self.class_combo.currentData()
        cls = self.project_manager.get_class(class_id)
        if not cls:
            QMessageBox.information(self, "Select a Label", "Select a label to rename first.")
            return
        name, ok = QInputDialog.getText(self, "Rename Label",
            "New name (updates this label on every image):", text=cls.name)
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Invalid Label", "The label name cannot be empty.")
            return
        if name == cls.name:
            return
        if any(other.id != class_id and other.name.casefold() == name.casefold()
               for other in self.project_manager.project.classes):
            QMessageBox.warning(self, "Label Already Exists", "Choose a unique name. To change a box to an existing label, use the Active label dropdown.")
            return
        cls.name = name
        for image in self.project_manager.project.images:
            for annotation in image.annotations:
                if annotation.class_id == class_id:
                    annotation.class_name = name
        self.update_class_list()
        self.scene.update_box_colors()
        self.update_box_properties()
        self.command_history.clear()
        self.schedule_autosave()
        self.statusBar().showMessage(f'Label renamed to "{name}" across the project. Export again to update training files.', 8000)
            
    def delete_selected_class(self):
        """Delete the selected class from the class list"""
        if not self.project_manager.project:
            return
        
        # Get selected item from class list
        selected_items = self.class_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a class to delete.")
            return
        
        item = selected_items[0]
        class_id = item.data(Qt.UserRole)
        self.delete_class(class_id)
        
    def delete_class(self, class_id: int):
        """Delete a class, offering reassign or delete-annotations options when in use"""
        project = self.project_manager.project
        if not project:
            return

        cls_to_delete = self.project_manager.get_class(class_id)
        if not cls_to_delete:
            return

        # Count affected annotations
        affected_images = []
        affected_count = 0
        for img_data in project.images:
            anns = [a for a in img_data.annotations if a.class_id == class_id]
            if anns:
                affected_images.append((img_data, anns))
                affected_count += len(anns)

        if affected_count > 0:
            other_classes = [c for c in project.classes if c.id != class_id]

            if other_classes:
                # Build choice dialog: Reassign / Delete annotations / Cancel
                msg = QMessageBox(self)
                msg.setWindowTitle("Class In Use")
                msg.setText(
                    f'Class "{cls_to_delete.name}" is used by {affected_count} annotation(s).\n'
                    "What would you like to do?"
                )
                reassign_btn = msg.addButton("Reassign to another class…", QMessageBox.ActionRole)
                delete_anns_btn = msg.addButton("Delete annotations too", QMessageBox.DestructiveRole)
                msg.addButton(QMessageBox.Cancel)
                msg.exec_()
                clicked = msg.clickedButton()

                if clicked == reassign_btn:
                    # Ask which class to reassign to
                    class_names = [f"{c.id}: {c.name}" for c in other_classes]
                    choice, ok = QInputDialog.getItem(
                        self, "Reassign Class",
                        "Select class to reassign annotations to:",
                        class_names, 0, False
                    )
                    if not ok:
                        return
                    target_cls = other_classes[class_names.index(choice)]
                    for img_data, anns in affected_images:
                        for ann in anns:
                            ann.class_id = target_cls.id
                            ann.class_name = target_cls.name

                elif clicked == delete_anns_btn:
                    # Remove affected annotations
                    for img_data, anns in affected_images:
                        for ann in anns:
                            img_data.annotations.remove(ann)
                    # Reload current image in scene to reflect removals
                    self.set_current_image(self.project_manager.current_image_index)
                else:
                    return  # Cancel

            else:
                # No other classes to reassign to — only option is to delete annotations
                reply = QMessageBox.question(
                    self, "Class In Use",
                    f'Class "{cls_to_delete.name}" is used by {affected_count} annotation(s) '
                    "and there are no other classes to reassign to.\n\n"
                    "Delete the class and all its annotations?",
                    QMessageBox.Yes | QMessageBox.Cancel
                )
                if reply != QMessageBox.Yes:
                    return
                for img_data, anns in affected_images:
                    for ann in anns:
                        img_data.annotations.remove(ann)
                self.set_current_image(self.project_manager.current_image_index)

        # Remove class and reindex
        project.classes = [c for c in project.classes if c.id != class_id]
        for i, cls in enumerate(project.classes):
            cls.id = i
        # Fix any annotation class_ids that shifted due to reindex
        for img_data in project.images:
            for ann in img_data.annotations:
                for cls in project.classes:
                    if cls.name == ann.class_name:
                        ann.class_id = cls.id
                        break
        self.update_class_list()
        if self.scene:
            self.scene.update_box_colors()
        self.command_history.clear()
        self.schedule_autosave()
        
    def undo(self):
        """Undo last command"""
        if self.command_history.undo():
            # Reload current image to reflect changes
            self.set_current_image(self.project_manager.current_image_index)
            self.schedule_autosave()
            
    def redo(self):
        """Redo last command"""
        if self.command_history.redo():
            # Reload current image to reflect changes
            self.set_current_image(self.project_manager.current_image_index)
            self.schedule_autosave()
            
    def save_project(self):
        """Save project"""
        if not self.save_current_annotations():
            QMessageBox.warning(self, "Save Failed", self.project_manager.last_error or "Project could not be saved.")
        
    def refresh_project(self):
        """Sync directory changes (new/deleted images) and refresh the current view"""
        if not self.project_manager.project:
            if self.viewer:
                self.viewer.fit_to_window()
            return

        # Remember current position
        current_index = self.project_manager.current_image_index
        current_filename = None
        current_img = self.project_manager.get_current_image()
        if current_img:
            current_filename = current_img.filename

        # Save annotations for the current image before syncing
        if not self.save_current_annotations():
            return

        # Sync directory
        new_count, removed_count = self.project_manager.sync_new_images()
        if new_count or removed_count:
            self.command_history.clear()

        # Rebuild image list
        self.image_list.clear()
        for i, img_data in enumerate(self.project_manager.project.images):
            item = QListWidgetItem(img_data.filename)
            item.setData(Qt.UserRole, i)
            item.setToolTip(img_data.filename)
            self.image_list.addItem(item)

        self.update_status()

        # Try to stay on the same file; fall back to clamped index
        if not self.project_manager.project.images:
            self.scene.clear_scene()
            self.canvas_stack.setCurrentIndex(0)
            self.viewer.resetTransform()
            self.schedule_autosave()
            self.statusBar().showMessage("No images remain in this folder.", 4000)
            return
        new_index = current_index
        if current_filename:
            for i, img_data in enumerate(self.project_manager.project.images):
                if img_data.filename == current_filename:
                    new_index = i
                    break
            else:
                new_index = min(current_index, len(self.project_manager.project.images) - 1)

        new_index = max(0, new_index)
        self.set_current_image(new_index)

        if self.viewer:
            self.viewer.fit_to_window()

        # Report changes in status bar
        parts = []
        if new_count:
            parts.append(f"{new_count} new image(s) added")
        if removed_count:
            parts.append(f"{removed_count} deleted image(s) removed")
        if parts:
            self.statusBar().showMessage("Refresh: " + ", ".join(parts), 4000)
        else:
            self.statusBar().showMessage("Refresh: directory up to date", 2000)
        if self.project_manager.is_dirty:
            self.schedule_autosave()

    def fit_to_window(self):
        """Fit image to window"""
        if self.viewer:
            self.viewer.fit_to_window()
            
    def zoom_100(self):
        """Zoom to 100%"""
        if self.viewer:
            self.viewer.zoom_100()
            
    def zoom_in(self):
        """Zoom in"""
        if self.viewer:
            self.viewer.zoom_in()
            
    def zoom_out(self):
        """Zoom out"""
        if self.viewer:
            self.viewer.zoom_out()
            
    def filter_image_list(self, *args):
        """Filter rows without changing their underlying project indices."""
        project = self.project_manager.project
        if not project or not self.image_list:
            return
        query = self.image_search.text().casefold().strip()
        mode = self.image_filter.currentIndex()
        shown = 0
        for index in range(self.image_list.count()):
            image = project.images[index]
            matches = query in image.filename.casefold()
            matches = matches and (mode == 0 or (mode == 1 and not image.annotations)
                                   or (mode == 2 and bool(image.annotations))
                                   or (mode == 3 and image.review_decision() == "pending")
                                   or (mode == 4 and image.review_decision() == "approved")
                                   or (mode == 5 and image.review_decision() == "rejected"))
            item = self.image_list.item(index)
            item.setHidden(not matches)
            item.setToolTip(f"{image.filename}\n{len(image.annotations)} boxes / {image.review_decision()}")
            shown += int(matches)
        self.filter_count.setText(f"{shown} of {len(project.images)} images shown")
        current = self.project_manager.current_image_index
        self.previous_button.setEnabled(any(not self.image_list.item(i).isHidden() for i in range(max(0, current))))
        self.next_button.setEnabled(any(not self.image_list.item(i).isHidden() for i in range(current + 1, self.image_list.count())))

    def update_status(self):
        """Keep workspace metadata and annotation progress in sync."""
        project = self.project_manager.project
        self.save_button.setEnabled(project is not None)
        self.export_button.setEnabled(project is not None)
        self.ai_button.setEnabled(bool(project and project.images))
        self.rename_label_button.setEnabled(bool(project and project.classes))
        image = self.project_manager.get_current_image()
        has_ai = bool(image and image.ai_review)
        self.ai_review_label.setVisible(has_ai)
        self.ai_review_actions.setVisible(has_ai)
        if has_ai:
            decision = image.review_decision()
            self.ai_review_label.setText({"pending": "Pending AI review / not exported",
                "approved": "AI approved / ready to export",
                "rejected": "AI rejected / not exported"}[decision])
            self.ai_review_label.setToolTip("Inspect every box and the species label before approval. "
                "Editing boxes or labels reopens review. Rejected images and boxes are retained, not deleted.")
            self.approve_ai_button.setEnabled(bool(image.annotations) and decision != "approved")
            self.reject_ai_button.setEnabled(decision != "rejected")
        if not project:
            self.status_label.setText("No project loaded")
            self.previous_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self.image_jump.setEnabled(False)
            self.delete_box_btn.setEnabled(False)
            return
        current = self.project_manager.current_image_index
        total = len(project.images)
        image_data = self.project_manager.get_current_image()
        box_count = len(image_data.annotations) if image_data else 0
        self.folder_label.setText(Path(project.image_folder).name)
        self.folder_label.setToolTip(project.image_folder)
        self.image_title.setText(image_data.filename if image_data else "Workspace")
        self.image_title.setToolTip(image_data.filename if image_data else "")
        self.image_meta.setText(f"{image_data.width} x {image_data.height}  /  {box_count} boxes" if image_data else "")
        self.position_label.setText(f"{current + 1} / {total}" if image_data else "No image selected")
        self.status_label.setText(f"{box_count} boxes in current image" if image_data else "No images loaded")
        with QSignalBlocker(self.image_jump):
            self.image_jump.setMaximum(max(1, total))
            self.image_jump.setValue(max(1, current + 1))
        self.image_jump.setEnabled(bool(total))
        annotated = sum(bool(img.annotations) for img in project.images)
        self.image_count_label.setText(f"{annotated} / {total} images have boxes")
        self.annotation_progress.setValue(round(100 * annotated / total) if total else 0)
        if not total:
            self.canvas_stack.setCurrentIndex(0)
        self.filter_image_list()
        
    def show_about(self):
        """Show about dialog"""
        from .about_dialog import AboutDialog
        AboutDialog(self).exec()
        
    def show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """
Keyboard Shortcuts:

Navigation:
  ← / → or A / D - Previous/Next image
  Home / End - First/Last image

Tools:
  S - Select tool
  B - Box (draw) tool
  H - Pan tool

Box Operations:
  Delete / Backspace - Delete selected box(es)
  Ctrl+A - Select all boxes
  Escape - Deselect all
  1-9, 0 - Assign class by number

Zoom:
  Ctrl + Mouse Wheel - Zoom in/out
  Ctrl+0 - Fit to window
  Ctrl+1 - 100% zoom
  Ctrl++ / Ctrl+- - Zoom in/out

General:
  Ctrl+Z - Undo
  Ctrl+Y - Redo
  Ctrl+S - Save
  Ctrl+Shift+E - Export VOC, YOLO, and COCO
  Ctrl+O - Open folder
        """
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)
        
    def closeEvent(self, event):
        """Handle close event"""
        if self.save_current_annotations():
            self.scene.blockSignals(True)
            event.accept()
        else:
            answer = QMessageBox.warning(self, "Unsaved Changes", "The project could not be saved. Close without saving?",
                                         QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
            if answer == QMessageBox.Discard:
                self.scene.blockSignals(True)
                event.accept()
            else:
                event.ignore()

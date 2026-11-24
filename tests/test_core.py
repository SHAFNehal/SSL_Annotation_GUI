import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.commands import CreateBoxCommand
from src.exporters import ExportManager
from src.main_window import MainWindow
from src.models import Annotation
from src.project_manager import ProjectManager


APP = QApplication.instance() or QApplication([])


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "moth"
        self.folder.mkdir()
        Image.new("RGB", (200, 150)).save(self.folder / "a.jpg")
        Image.new("RGB", (200, 150)).save(self.folder / "b.JpG")
        self.manager = ProjectManager()
        self.assertTrue(self.manager.create_project(str(self.folder)))

    def test_projects_are_local_and_mixed_case_images_are_discovered(self):
        self.assertEqual(self.manager.project_path, self.folder / "project.json")
        self.assertEqual(len(self.manager.project.images), 2)
        self.assertTrue(self.manager.save_project())
        other = self.folder.parent / "beetle"
        other.mkdir()
        Image.new("RGB", (50, 50)).save(other / "other.jpg")
        manager = ProjectManager()
        manager.create_project(str(other))
        manager.save_project()
        self.assertNotEqual(self.manager.project_path, manager.project_path)
        self.assertEqual(json.loads(self.manager.project_path.read_text())["image_folder"], str(self.folder))

    def test_clean_save_does_not_rewrite_or_backup_project(self):
        self.assertTrue(self.manager.save_project())
        with patch("src.project_manager.os.replace") as replace, patch("src.project_manager.shutil.copy2") as backup:
            self.assertTrue(self.manager.save_project())
        replace.assert_not_called()
        backup.assert_not_called()

    def test_deleted_annotations_do_not_return_from_stale_exports(self):
        self.manager.project.images[0].annotations.append(Annotation(class_name="object", x_min=1, y_min=2, x_max=40, y_max=60))
        self.manager.save_project()
        ExportManager.export_all(self.manager.project, self.manager.project_path)
        self.manager.project.images[0].annotations.clear()
        self.manager.mark_dirty()
        self.manager.save_project()
        loaded = ProjectManager()
        self.assertTrue(loaded.load_project(str(self.manager.project_path)))
        self.assertEqual(loaded.project.images[0].annotations, [])
        ExportManager.export_all(loaded.project, loaded.project_path)
        self.assertFalse((self.folder / "exports/voc/Annotations/a.xml").exists())
        self.assertFalse((self.folder / "exports/yolo/labels/a.txt").exists())

    def test_backup_recovery_preserves_the_valid_backup(self):
        self.manager.save_project()
        self.manager.mark_dirty()
        self.manager.save_project()
        backup = self.manager.project_path.with_suffix(".json.bak")
        valid = backup.read_bytes()
        self.manager.project_path.write_text("broken json")
        loaded = ProjectManager()
        self.assertTrue(loaded.load_project(str(self.manager.project_path)))
        self.assertTrue(loaded.save_project())
        self.assertEqual(backup.read_bytes(), valid)
        json.loads(loaded.project_path.read_text())

    def test_failed_save_keeps_dirty_state_and_original_data(self):
        self.manager.save_project()
        before = self.manager.project_path.read_bytes()
        self.manager.mark_dirty()
        with patch("src.project_manager.os.replace", side_effect=OSError("disk unavailable")):
            self.assertFalse(self.manager.save_project())
        self.assertTrue(self.manager.is_dirty)
        self.assertIn("disk unavailable", self.manager.last_error)
        self.assertEqual(self.manager.project_path.read_bytes(), before)

    def test_sidecar_voc_import_sets_the_species_as_default(self):
        (self.folder / "a.xml").write_text('<annotation><filename>a.jpg</filename><object><name>Maruca vitrata</name>'
            '<bndbox><xmin>1</xmin><ymin>2</ymin><xmax>40</xmax><ymax>60</ymax></bndbox></object></annotation>')
        manager = ProjectManager()
        self.assertTrue(manager.create_project(str(self.folder)))
        self.assertEqual([c.name for c in manager.project.classes], ["Maruca vitrata"])
        self.assertEqual(manager.project.images[0].annotations[0].class_id, 0)

    def test_folder_detection_recovers_corrupt_primary_and_rejects_wrong_owner(self):
        self.manager.save_project()
        self.manager.mark_dirty()
        self.manager.save_project()
        self.manager.project_path.write_text("broken")
        self.assertEqual(ProjectManager.project_path_for_folder(self.folder),self.manager.project_path)
        self.manager.project_path.write_text(json.dumps({"image_folder":str(self.folder.parent / 'other')}))
        with self.assertRaisesRegex(ValueError,"another image folder"):
            ProjectManager.project_path_for_folder(self.folder)

    def test_matching_legacy_parent_project_is_detected(self):
        legacy=self.folder.parent/'project.json'
        legacy.write_text(json.dumps(self.manager.project.to_dict()))
        self.assertEqual(ProjectManager.project_path_for_folder(self.folder),legacy)


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        for name in ["a.jpg", "b.jpg"]:
            Image.new("RGB", (200, 150)).save(self.folder / name)
        self.window = MainWindow()
        self.window.project_manager.create_project(str(self.folder))
        self.window.load_project_ui()
        self.window.save_current_annotations()
        self.addCleanup(self.window.close)

    def draw_box(self):
        self.window.scene.start_drawing_box(QPointF(10, 20))
        return self.window.scene.finish_drawing_box(QPointF(100, 100))

    def test_navigation_without_changes_has_no_disk_writes_or_exports(self):
        with patch("src.project_manager.os.replace") as write, patch("src.main_window.ExportManager.export_all") as export:
            self.window.next_image()
            self.window.previous_image()
        write.assert_not_called()
        export.assert_not_called()

    def test_box_is_inserted_once_and_undo_reuses_the_pixmap(self):
        image_item = self.window.scene.image_item
        ann = self.draw_box()
        image = self.window.project_manager.get_current_image()
        self.assertEqual(image.annotations, [ann])
        self.window.undo()
        self.assertEqual(image.annotations, [])
        self.assertIs(self.window.scene.image_item, image_item)
        self.window.redo()
        self.assertEqual(image.annotations, [ann])

    def test_idle_autosave_saves_box_without_exporting(self):
        self.draw_box()
        with patch("src.main_window.ExportManager.export_all") as export:
            QTest.qWait(1200)
        saved = json.loads((self.folder / "project.json").read_text())
        self.assertEqual(len(saved["images"][0]["annotations"]), 1)
        self.assertFalse(self.window.project_manager.is_dirty)
        export.assert_not_called()

    def test_moving_box_saves_scene_coordinates_and_can_be_undone(self):
        annotation = self.draw_box()
        box = self.window.scene.box_items[0]
        before = (annotation.x_min, annotation.y_min, annotation.x_max, annotation.y_max)
        box.setPos(20, 5)
        self.assertEqual((annotation.x_min, annotation.y_min, annotation.x_max, annotation.y_max), (30, 25, 120, 105))
        self.window.on_box_edited(annotation, before)
        self.window.undo()
        self.assertEqual((annotation.x_min, annotation.y_min, annotation.x_max, annotation.y_max), before)
        self.window.redo()
        self.assertEqual((annotation.x_min, annotation.y_min, annotation.x_max, annotation.y_max), (30, 25, 120, 105))

    def test_failed_save_blocks_navigation(self):
        self.draw_box()
        with patch.object(self.window.project_manager, "save_project", return_value=False):
            self.window.next_image()
        self.assertEqual(self.window.project_manager.current_image_index, 0)

    def test_click_without_drag_does_not_create_noise_box(self):
        self.window.scene.start_drawing_box(QPointF(20, 20))
        result = self.window.scene.finish_drawing_box(QPointF(20, 20))
        self.assertIsNone(result)
        self.assertEqual(self.window.project_manager.get_current_image().annotations, [])

    def test_undo_does_not_affect_a_previous_image_after_navigation(self):
        self.draw_box()
        self.window.next_image()
        self.window.undo()
        self.assertEqual(len(self.window.project_manager.project.images[0].annotations), 1)
        self.assertEqual(len(self.window.project_manager.project.images[1].annotations), 0)

    def test_renaming_a_class_updates_annotations_on_all_images(self):
        self.draw_box()
        self.window.project_manager.project.images[1].annotations.append(Annotation(class_id=0,class_name="object",x_min=1,y_min=2,x_max=30,y_max=40))
        with patch("src.main_window.QInputDialog.getText",return_value=("moth",True)), patch("src.main_window.QColorDialog.getColor",return_value=QColor("#006633")):
            self.window.edit_class(0)
        self.assertTrue(all(ann.class_name=="moth" for image in self.window.project_manager.project.images for ann in image.annotations))
        self.assertTrue(self.window.project_manager.is_dirty)

    def test_rename_label_button_updates_all_boxes_without_changing_color(self):
        self.draw_box()
        project = self.window.project_manager.project
        project.images[1].annotations.append(Annotation(class_id=0, class_name="object",
            x_min=1, y_min=2, x_max=30, y_max=40))
        original_color = project.classes[0].color
        self.window.class_list.setCurrentRow(0)
        with patch("src.main_window.QInputDialog.getText", return_value=("  Adult moth  ", True)), \
             patch("src.main_window.QColorDialog.getColor") as color_dialog:
            self.window.rename_label_button.click()
        self.assertEqual(project.classes[0].name, "Adult moth")
        self.assertTrue(all(ann.class_name == "Adult moth" for image in project.images for ann in image.annotations))
        self.assertEqual(project.classes[0].color, original_color)
        self.assertIn("Adult moth", self.window.scene.box_items[0].label_item.text())
        color_dialog.assert_not_called()
        self.window.save_current_annotations()
        saved = json.loads((self.folder / "project.json").read_text())
        self.assertEqual(saved["images"][1]["annotations"][0]["class_name"], "Adult moth")

    def test_rename_rejects_blank_or_duplicate_names_and_respects_cancel(self):
        self.window.project_manager.add_class("Moth", "#147c82")
        self.window.update_class_list()
        self.window.class_list.setCurrentRow(0)
        self.window.save_current_annotations()
        for value, ok in [("   ", True), ("moth", True), ("new label", False), ("object", True)]:
            with patch("src.main_window.QInputDialog.getText", return_value=(value, ok)), \
                 patch("src.main_window.QMessageBox.warning"):
                self.window.rename_selected_class()
            self.assertEqual(self.window.project_manager.project.classes[0].name, "object")
            self.assertFalse(self.window.project_manager.is_dirty)

    def test_rename_can_use_active_label_and_preserves_active_selection(self):
        other = self.window.project_manager.add_class("moth", "#147c82")
        self.window.update_class_list()
        self.window.class_combo.setCurrentIndex(self.window.class_combo.findData(other))
        with patch("src.main_window.QInputDialog.getText", return_value=("Adult moth", True)):
            self.window.rename_selected_class()
        self.assertEqual(self.window.project_manager.get_class(other).name, "Adult moth")
        self.assertEqual(self.window.class_combo.currentData(), other)

    def test_refresh_clears_the_canvas_when_all_images_are_removed(self):
        self.draw_box()
        for path in self.folder.glob("*.jpg"):
            path.unlink()
        self.window.refresh_project()
        self.assertIsNone(self.window.scene.current_image_data)
        self.assertIsNone(self.window.scene.image_item)
        self.assertEqual(self.window.project_manager.current_image_index,-1)

    def test_search_accepts_shortcut_letters_without_navigation(self):
        self.window.show()
        self.window.image_search.setFocus()
        QTest.keyClicks(self.window.image_search, "bad")
        self.assertEqual(self.window.image_search.text(), "bad")
        self.assertEqual(self.window.project_manager.current_image_index, 0)
        self.assertTrue(self.window.image_list.item(0).isHidden())

    def test_annotation_filters_and_navigation(self):
        self.draw_box()
        self.window.image_filter.setCurrentIndex(1)
        self.assertTrue(self.window.image_list.item(0).isHidden())
        self.assertFalse(self.window.image_list.item(1).isHidden())
        self.window.next_image()
        self.assertEqual(self.window.project_manager.current_image_index, 1)
        self.assertFalse(self.window.previous_button.isEnabled())
        self.window.image_jump.setValue(1)
        self.assertEqual(self.window.project_manager.current_image_index, 0)
        self.assertEqual(self.window.image_filter.currentIndex(), 0)

    def test_active_label_only_changes_selected_boxes(self):
        first = self.draw_box()
        self.window.deselect_all_boxes()
        other = self.window.project_manager.add_class("moth", "#147c82")
        self.window.update_class_list()
        self.window.assign_class(other)
        self.assertNotEqual(first.class_id, other)
        second = self.draw_box()
        self.assertEqual(second.class_id, other)
        self.assertEqual(self.window.scene.get_selected_boxes(), [second])

    def test_save_badge_tracks_unsaved_and_saved_changes(self):
        self.draw_box()
        self.assertEqual(self.window.save_badge.text(), "Unsaved changes")
        self.window.save_current_annotations()
        self.assertEqual(self.window.save_badge.text(), "Saved")

    def test_failed_save_restores_clicked_image_selection(self):
        self.draw_box()
        self.window.image_list.setCurrentRow(1)
        with patch.object(self.window.project_manager, "save_project", return_value=False):
            self.window.on_image_list_double_click(self.window.image_list.item(1))
        self.assertEqual(self.window.image_list.currentRow(), 0)
        self.assertEqual(self.window.save_badge.text(), "Save failed")

    def test_mouse_drag_and_resize_remain_undoable(self):
        self.window.show()
        APP.processEvents()
        annotation = self.draw_box()
        viewer = self.window.viewer
        viewport = viewer.viewport()
        before = (annotation.x_min, annotation.y_min, annotation.x_max, annotation.y_max)
        for start, end in [(QPointF(55, 60), QPointF(65, 65)),
                           (QPointF(100, 100), QPointF(115, 110))]:
            QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, viewer.mapFromScene(start))
            QTest.mouseMove(viewport, viewer.mapFromScene(end), 20)
            QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, viewer.mapFromScene(end))
            after = (annotation.x_min, annotation.y_min, annotation.x_max, annotation.y_max)
            self.assertNotEqual(after, before)
            self.window.undo()
            self.assertEqual((annotation.x_min, annotation.y_min, annotation.x_max, annotation.y_max), before)

    def test_small_window_keeps_label_controls_usable(self):
        self.window.resize(900, 600)
        self.window.show()
        APP.processEvents()
        self.assertGreaterEqual(self.window.class_combo.height(), 30)
        self.assertGreaterEqual(self.window.delete_box_btn.height(), 30)


if __name__ == "__main__":
    unittest.main()

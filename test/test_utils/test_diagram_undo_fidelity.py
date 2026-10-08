"""Undo in the diagram editor gives back what was there: typed text, and images."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QFocusEvent, QPixmap
from PySide6.QtWidgets import QApplication, QGraphicsSceneMouseEvent

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _type_into(label, text: str) -> None:
    """Double-click the label, replace its text, and click away."""
    label.mouseDoubleClickEvent(QGraphicsSceneMouseEvent(QEvent.Type.GraphicsSceneMouseDoubleClick))
    label.setPlainText(text)
    label.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))


class TestTextTypedOnTheCanvas:
    def _scene_with_a_node(self):
        scene = DiagramScene()
        node = DiagramNode(x=0, y=0, w=100, h=60, text="Node")
        scene.addItem(node)
        return scene

    def test_it_is_one_undo_step(self, app):
        scene = self._scene_with_a_node()

        _type_into(scene.get_all_nodes()[0].label, "Hello")

        assert scene.undo_stack.count() == 1
        scene.undo_stack.undo()
        assert scene.get_all_nodes()[0].text() == "Node"

    def test_undo_then_redo_brings_it_back(self, app):
        scene = self._scene_with_a_node()
        with scene.undo_scope("Move"):
            scene.get_all_nodes()[0].moveBy(10, 0)
        _type_into(scene.get_all_nodes()[0].label, "Hello")

        scene.undo_stack.undo()
        scene.undo_stack.redo()

        # Undo went back to before the move and redo to just after it: the
        # typed text was in neither snapshot, and was gone for good.
        assert scene.get_all_nodes()[0].text() == "Hello"

    def test_opening_the_editor_without_typing_records_nothing(self, app):
        scene = self._scene_with_a_node()

        _type_into(scene.get_all_nodes()[0].label, "Node")

        assert scene.undo_stack.count() == 0


class TestAnImageTheEditorCannotReload:
    def test_undo_keeps_its_picture(self, app, monkeypatch):
        scene = DiagramScene()
        pixmap = QPixmap(20, 10)
        pixmap.fill(QColor("red"))
        downloads: list = []
        monkeypatch.setattr(scene, "_start_image_download", downloads.append)
        # A .tiff picked through "All Files", and an image added from a URL
        scene.add_image(pixmap, r"C:\scans\page.tiff", QPointF(0, 0))
        scene.add_image(pixmap, "https://img.example/logo.png", QPointF(100, 0))
        with scene.undo_scope("Move"):
            scene.get_all_images()[0].moveBy(5, 0)

        scene.undo_stack.undo()

        # The first went blank (.tiff is not on the list the editor reloads),
        # and the second was downloaded again.
        assert all(not image._pix_item.pixmap().isNull() for image in scene.get_all_images())
        assert downloads == []


def test_a_mouse_move_is_still_one_step(app):
    scene = DiagramScene()
    node = DiagramNode(x=0, y=0, w=100, h=60, text="Node")
    scene.addItem(node)
    node.setSelected(True)
    press = QGraphicsSceneMouseEvent(QEvent.Type.GraphicsSceneMousePress)
    press.setScenePos(QPointF(50, 30))
    press.setButton(Qt.MouseButton.LeftButton)
    press.setButtons(Qt.MouseButton.LeftButton)
    scene.mousePressEvent(press)
    node.moveBy(20, 0)

    scene.end_undo()

    assert scene.undo_stack.count() == 1


def _click(scene: DiagramScene, x: float, y: float) -> None:
    press = QGraphicsSceneMouseEvent(QEvent.Type.GraphicsSceneMousePress)
    press.setScenePos(QPointF(x, y))
    press.setButton(Qt.MouseButton.LeftButton)
    press.setButtons(Qt.MouseButton.LeftButton)
    scene.mousePressEvent(press)


@pytest.mark.parametrize("rebuild", ["undo and redo", "load"])
def test_a_half_made_connection_does_not_outlive_a_rebuild(app, rebuild):
    # Its first node was replaced by the rebuild; finished, the connection
    # pointed at a node no longer on the canvas, and every snapshot (so Save,
    # and Delete) raised KeyError from then on
    from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import ToolMode

    scene = DiagramScene()
    with scene.undo_scope("Add"):
        scene.addItem(DiagramNode(x=0, y=0, w=100, h=60, text="A"))
        scene.addItem(DiagramNode(x=300, y=0, w=100, h=60, text="B"))
    scene.mode = ToolMode.ADD_CONNECTION
    _click(scene, 50, 30)
    if rebuild == "load":
        scene.load_from_dict(scene.to_dict())
    else:
        scene.undo_stack.undo()
        scene.undo_stack.redo()

    _click(scene, 350, 30)

    assert scene.get_all_connections() == []
    scene.to_dict()


def test_a_step_merges_only_with_one_on_the_same_property(app):
    # Qt asks only commands of the same id(); two keys can still share a CRC
    from pybreeze.pybreeze_ui.diagram_editor.diagram_commands import DiagramSnapshotCommand

    scene = DiagramScene()
    first = DiagramSnapshotCommand(scene, "Width", {"step": 0}, {"step": 1}, merge_key="width")
    same = DiagramSnapshotCommand(scene, "Width", {"step": 1}, {"step": 2}, merge_key="width")
    other = DiagramSnapshotCommand(scene, "Height", {"step": 1}, {"step": 2}, merge_key="height")

    assert not first.mergeWith(other)
    assert first.mergeWith(same)
    assert first._new_data == {"step": 2}
    assert DiagramSnapshotCommand(scene, "Add", {}, {}).id() == -1  # no key: never merged
    scene.deleteLater()

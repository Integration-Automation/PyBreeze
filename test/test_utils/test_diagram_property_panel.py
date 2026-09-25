"""The property panel for a connection and an image: what it shows, and what an edit there does."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.diagram_editor.diagram_items import (
    ConnectionStyle, DiagramConnection, DiagramImage, DiagramNode,
)
from pybreeze.pybreeze_ui.diagram_editor.diagram_property_panel import DiagramPropertyPanel
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def connection(app):
    scene = DiagramScene()
    source, target = DiagramNode(x=0, y=0, text="A"), DiagramNode(x=300, y=0, text="B")
    scene.addItem(source)
    scene.addItem(target)
    edge = DiagramConnection(source, target, label="calls", line_width=2)
    scene.addItem(edge)
    panel = DiagramPropertyPanel(scene)
    edge.setSelected(True)
    yield scene, edge, panel
    panel.deleteLater()
    scene.deleteLater()


@pytest.fixture
def image(app):
    scene = DiagramScene()
    picture = DiagramImage(x=0, y=0, w=120, h=80)
    scene.addItem(picture)
    panel = DiagramPropertyPanel(scene)
    picture.setSelected(True)
    yield scene, picture, panel
    panel.deleteLater()
    scene.deleteLater()


def _edges(scene: DiagramScene) -> list[DiagramConnection]:
    return [item for item in scene.items() if isinstance(item, DiagramConnection)]


class TestAConnection:
    def test_selecting_it_shows_it_and_records_nothing(self, connection):
        scene, _edge, panel = connection

        assert panel._conn_label.text() == "calls"
        assert panel._conn_width.value() == 2
        assert not scene.undo_stack.canUndo()

    def test_its_style_colour_and_label_follow_the_panel(self, connection):
        scene, edge, panel = connection

        panel._conn_style.setCurrentIndex(1)
        panel._conn_color.set_color(QColor("#ff0000"))
        panel._conn_color.color_changed.emit(QColor("#ff0000"))
        panel._conn_label.setText("returns")
        panel._conn_label.editingFinished.emit()

        assert edge._style == ConnectionStyle.DASHED
        assert edge._line_color == QColor("#ff0000")
        assert edge.edge_label() == "returns"
        assert scene.undo_stack.count() == 3

    def test_width_steps_are_one_undo_step(self, connection):
        scene, _edge, panel = connection

        for width in (3, 4, 5):
            panel._conn_width.setValue(width)
        scene.undo_stack.undo()

        (restored,) = _edges(scene)
        assert restored._line_width == 2
        assert not scene.undo_stack.canUndo()


class TestAnImage:
    def test_selecting_it_shows_its_size(self, image):
        scene, _picture, panel = image

        assert (panel._img_w.value(), panel._img_h.value()) == (120, 80)
        assert not scene.undo_stack.canUndo()

    def test_a_width_edit_keeps_its_height_and_the_caption_follows(self, image):
        _scene, picture, panel = image

        panel._img_w.setValue(200)
        panel._img_caption.setText("logo")
        panel._img_caption.editingFinished.emit()

        assert (picture.img_w, picture.img_h) == (200, 80)
        assert picture.text() == "logo"


@pytest.fixture
def node(app):
    scene = DiagramScene()
    box = DiagramNode(x=0, y=0, w=140, h=60, text="A")
    scene.addItem(box)
    panel = DiagramPropertyPanel(scene)
    box.setSelected(True)
    yield scene, box, panel
    panel.deleteLater()
    scene.deleteLater()


class TestANode:
    def test_its_text_shape_and_colours_follow_the_panel(self, node):
        scene, box, panel = node

        panel._node_text.setText("Start")
        panel._node_text.editingFinished.emit()
        panel._node_shape.setCurrentIndex(3)
        panel._node_fill.color_changed.emit(QColor("#00ff00"))
        panel._node_border.color_changed.emit(QColor("#0000ff"))

        saved = box.to_dict(0)
        assert (saved["text"], saved["shape"]) == ("Start", "DIAMOND")
        assert (saved["fill_color"], saved["border_color"]) == ("#00ff00", "#0000ff")
        assert scene.undo_stack.count() == 4

    def test_leaving_the_text_box_unchanged_records_nothing(self, node):
        # editingFinished comes with every focus change: a step for it would
        # mark a saved diagram as changed
        scene, _box, panel = node

        panel._node_text.editingFinished.emit()

        assert not scene.undo_stack.canUndo()

    def test_an_edit_with_nothing_selected_changes_nothing(self, node):
        scene, box, panel = node
        box.setSelected(False)

        panel._on_node_fill(QColor("#00ff00"))
        panel._on_conn_label()
        panel._on_img_caption()

        assert box.to_dict(0)["fill_color"] != "#00ff00"
        assert not scene.undo_stack.canUndo()


class TestTheColourButton:
    def test_a_colour_picked_is_shown_and_passed_on(self, node, monkeypatch):
        from pybreeze.pybreeze_ui.diagram_editor import diagram_property_panel

        _scene, box, panel = node
        monkeypatch.setattr(diagram_property_panel.QColorDialog, "getColor",
                            staticmethod(lambda *args: QColor("#123456")))

        panel._node_fill._pick()

        assert panel._node_fill.color() == QColor("#123456")
        assert panel._node_fill.text() == "#123456"
        assert box.to_dict(0)["fill_color"] == "#123456"

    def test_a_cancelled_dialog_changes_nothing(self, node, monkeypatch):
        from pybreeze.pybreeze_ui.diagram_editor import diagram_property_panel

        scene, _box, panel = node
        before = panel._node_fill.color()
        monkeypatch.setattr(diagram_property_panel.QColorDialog, "getColor",
                            staticmethod(lambda *args: QColor()))  # what Cancel returns

        panel._node_fill._pick()

        assert panel._node_fill.color() == before
        assert not scene.undo_stack.canUndo()

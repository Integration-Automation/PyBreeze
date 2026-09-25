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

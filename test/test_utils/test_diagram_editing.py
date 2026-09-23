"""Editing a diagram: what the context menu, stacking, undo, panel and wheel act on."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QGraphicsSceneContextMenuEvent, QGraphicsSceneMouseEvent

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.diagram_editor import diagram_scene as scene_module
from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramImage, DiagramNode
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _node(scene: DiagramScene, x: float, text: str, z: float = 0) -> DiagramNode:
    node = DiagramNode(x=x, y=0, w=100, h=60, text=text)
    node.setZValue(z)
    scene.addItem(node)
    return node


def _top_node(scene: DiagramScene, pos: QPointF) -> DiagramNode:
    """The node drawn on top at *pos* (a hit on its label counts as the node)."""
    for item in scene.items(pos):
        owner = item if isinstance(item, DiagramNode) else item.parentItem()
        if isinstance(owner, DiagramNode):
            return owner
    raise AssertionError("no node there")


def _right_click_and_choose(scene: DiagramScene, monkeypatch, pos: QPointF, label: str) -> None:
    """Open the context menu at *pos* and pick the entry called *label*."""

    class Menu:
        def __init__(self, *_args) -> None:
            self.entries: dict = {}

        def addAction(self, text, slot=None):
            self.entries[text] = slot

        def addSeparator(self) -> None:
            """Separators are not choices."""

        def actions(self) -> list:
            return list(self.entries)

        def exec(self, *_args) -> None:
            self.entries[label]()

    monkeypatch.setattr(scene_module, "QMenu", Menu)
    event = QGraphicsSceneContextMenuEvent(QEvent.Type.GraphicsSceneContextMenu)
    event.setScenePos(pos)
    scene.contextMenuEvent(event)


class TestTheContextMenu:
    def test_delete_removes_the_node_that_was_clicked(self, app, monkeypatch):
        scene = DiagramScene()
        selected = _node(scene, 0, "selected")
        clicked = _node(scene, 300, "clicked")
        selected.setSelected(True)

        _right_click_and_choose(scene, monkeypatch, QPointF(350, 30), "Delete")

        # It used to delete "selected" and leave "clicked".
        assert [node.text() for node in scene.get_all_nodes()] == ["selected"]
        assert clicked.scene() is None

    def test_a_click_inside_the_selection_keeps_the_selection(self, app, monkeypatch):
        scene = DiagramScene()
        first = _node(scene, 0, "a")
        second = _node(scene, 300, "b")
        first.setSelected(True)
        second.setSelected(True)

        _right_click_and_choose(scene, monkeypatch, QPointF(350, 30), "Delete")

        assert scene.get_all_nodes() == []


class TestStacking:
    def test_bring_to_front_goes_above_every_other_node(self, app):
        scene = DiagramScene()
        low = _node(scene, 0, "low", z=0)
        _node(scene, 10, "high", z=5)
        low.setSelected(True)

        scene._change_z(1)

        assert low.zValue() > 5

    def test_send_to_back_goes_below_every_other_node_keeping_their_order(self, app):
        scene = DiagramScene()
        _node(scene, 0, "floor", z=-3)
        first = _node(scene, 10, "first", z=1)
        second = _node(scene, 20, "second", z=2)
        first.setSelected(True)
        second.setSelected(True)

        scene._change_z(-1)

        assert first.zValue() < second.zValue() < -3

    def test_undo_keeps_overlapping_nodes_of_equal_z_the_same_way_up(self, app):
        scene = DiagramScene()
        _node(scene, 0, "under")
        _node(scene, 50, "over")  # added later, same z: drawn on top
        assert _top_node(scene, QPointF(75, 30)).text() == "over"

        with scene.undo_scope("Move"):
            scene.get_all_nodes()[0].moveBy(5, 0)
        scene.undo_stack.undo()

        assert _top_node(scene, QPointF(75, 30)).text() == "over"


class TestUndoAndSizes:
    def test_pressing_on_a_selected_image_starts_an_undo_step(self, app):
        scene = DiagramScene()
        image = DiagramImage(x=0, y=0, w=100, h=100, source="")
        scene.addItem(image)
        image.setSelected(True)
        press = QGraphicsSceneMouseEvent(QEvent.Type.GraphicsSceneMousePress)
        press.setScenePos(QPointF(50, 50))
        press.setButton(Qt.MouseButton.LeftButton)
        press.setButtons(Qt.MouseButton.LeftButton)

        scene.mousePressEvent(press)

        assert scene._pending_undo_desc == "Move"

    @pytest.mark.parametrize(("saved", "loaded"), [(1000, 48), (1, 6), (12.7, 12)])
    def test_a_font_size_from_a_file_is_kept_in_range(self, app, saved, loaded):
        node = DiagramNode.from_dict({"x": 0, "y": 0, "text": "a", "font_size": saved})

        assert node.to_dict(0)["font_size"] == loaded

    def test_the_panel_does_not_shrink_a_large_node(self, app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_property_panel import DiagramPropertyPanel

        scene = DiagramScene()
        node = DiagramNode(x=0, y=0, w=1200, h=900, text="big")
        scene.addItem(node)
        panel = DiagramPropertyPanel(scene)
        node.setSelected(True)

        assert panel._node_w.value() == 1200
        assert panel._node_h.value() == 900
        panel.deleteLater()

    def test_a_scene_already_destroyed_does_not_raise_in_the_panel(self, app):
        import shiboken6

        from pybreeze.pybreeze_ui.diagram_editor.diagram_property_panel import DiagramPropertyPanel

        scene = DiagramScene()
        panel = DiagramPropertyPanel(scene)
        shiboken6.delete(scene)

        panel._on_selection_changed()  # raised RuntimeError before
        panel.deleteLater()


class TestTheWheel:
    def _wheel(self, view, dx: int, dy: int) -> None:
        event = QWheelEvent(
            QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(dx, dy),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False)
        view.wheelEvent(event)

    def test_a_sideways_wheel_does_not_zoom(self, app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_view import DiagramView

        view = DiagramView(DiagramScene())

        self._wheel(view, 120, 0)

        assert view.transform().m11() == 1.0
        self._wheel(view, 0, 120)
        assert view.transform().m11() > 1.0
        view.deleteLater()

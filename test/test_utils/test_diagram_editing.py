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


    def test_a_click_on_the_empty_canvas_can_paste_what_was_copied(self, app, monkeypatch):
        scene = DiagramScene()
        node = _node(scene, 0, "copied")
        node.setSelected(True)
        scene.copy_selected()

        _right_click_and_choose(scene, monkeypatch, QPointF(600, 400), "Paste")

        assert sorted(item.text() for item in scene.get_all_nodes()) == ["copied", "copied"]
        scene.deleteLater()

    def test_with_nothing_copied_the_empty_canvas_offers_no_paste(self, app, monkeypatch):
        scene = DiagramScene()
        _node(scene, 0, "only")

        with pytest.raises(KeyError):  # the menu has no Paste entry to choose
            _right_click_and_choose(scene, monkeypatch, QPointF(600, 400), "Paste")
        scene.deleteLater()


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

    @pytest.mark.parametrize("direction", [1, -1], ids=["front", "back"])
    def test_a_node_alone_on_the_canvas_stays_and_leaves_no_undo_step(self, app, direction):
        scene = DiagramScene()
        node = _node(scene, 0, "alone", z=3)
        node.setSelected(True)

        scene._change_z(direction)

        assert node.zValue() == 3
        assert not scene.undo_stack.canUndo()
        scene.deleteLater()

    def test_pasting_with_nothing_copied_does_nothing(self, app):
        scene = DiagramScene()

        scene.paste_clipboard()

        assert scene.get_all_nodes() == []
        assert not scene.undo_stack.canUndo()
        scene.deleteLater()

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

    @pytest.mark.parametrize(("saved", "loaded"), [
        (1000, 48), (1, 6), (12.7, 12),
        # 1e999 in the file loads as infinity: Open failed with no message
        (float("inf"), 10), (float("nan"), 10), ("big", 10), (None, 10),
    ])
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


class TestThePropertyPanelAndTheCanvas:
    def _selected_node(self):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_property_panel import DiagramPropertyPanel

        scene = DiagramScene()
        node = DiagramNode(x=0, y=0, w=140, h=60, text="A")
        scene.addItem(node)
        panel = DiagramPropertyPanel(scene)
        node.setSelected(True)
        return scene, node, panel

    def test_a_height_edit_keeps_a_width_dragged_on_the_canvas(self, app):
        # The panel still held the width from before the drag, and set it back
        from PySide6.QtCore import QPointF, QRectF

        scene, node, panel = self._selected_node()
        with scene.undo_scope("Resize"):
            node._apply_resize("r", QPointF(200, 0), QRectF(0, 0, 140, 60), QPointF(0, 0))

        assert panel._node_w.value() == 340  # the panel follows the canvas
        panel._node_h.setValue(80)

        size = (node.node_w, node.node_h)
        assert size == (340, 80)

    def test_steps_on_one_property_are_one_undo_step(self, app):
        # Every arrow click was its own step, each with two whole-scene snapshots
        scene, node, panel = self._selected_node()
        before = scene.undo_stack.count()

        for size in (11, 12, 13, 14, 15):
            panel._node_font.setValue(size)

        assert scene.undo_stack.count() == before + 1
        scene.undo_stack.undo()
        restored = [item for item in scene.items() if isinstance(item, DiagramNode)][0]
        assert restored._font_size != 15

    def test_another_property_is_its_own_step(self, app):
        scene, node, panel = self._selected_node()
        before = scene.undo_stack.count()

        panel._node_font.setValue(12)
        panel._node_w.setValue(200)
        panel._node_font.setValue(13)

        assert scene.undo_stack.count() == before + 3

    def test_typing_a_size_applies_it_once(self, app):
        _scene, _node, panel = self._selected_node()

        assert not panel._node_w.keyboardTracking()
        assert not panel._node_font.keyboardTracking()


class TestZooming:
    """Fit went outside the zoom range, and then no step was allowed either way."""

    def _view(self, *nodes):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_view import DiagramView

        scene = DiagramScene()
        for node in nodes:
            scene.addItem(node)
        view = DiagramView(scene)
        view.resize(1200, 800)
        return scene, view

    def test_fitting_one_node_stays_within_the_range_and_can_zoom_out(self, app):
        from pybreeze.pybreeze_ui.diagram_editor import diagram_view

        scene, view = self._view(DiagramNode(x=0, y=0, w=40, h=20))
        view.resize(4000, 3000)
        view.fit(scene.itemsBoundingRect())

        assert view.transform().m11() == pytest.approx(diagram_view._MAX_SCALE)
        view.zoom_out()
        assert view.transform().m11() < diagram_view._MAX_SCALE

    def test_fitting_nodes_far_apart_stays_within_the_range(self, app):
        from pybreeze.pybreeze_ui.diagram_editor import diagram_view

        scene, view = self._view(DiagramNode(x=0, y=0), DiagramNode(x=50000, y=0))
        view.fit(scene.itemsBoundingRect())

        assert view.transform().m11() == pytest.approx(diagram_view._MIN_SCALE)

    def test_a_scale_outside_the_range_can_step_back_toward_it(self, app):
        from pybreeze.pybreeze_ui.diagram_editor import diagram_view

        _scene, view = self._view(DiagramNode(x=0, y=0))
        view.scale(8, 8)  # as a fit used to leave it

        view.zoom_in()
        assert view.transform().m11() == pytest.approx(8)  # further out: refused
        view.zoom_out()
        assert view.transform().m11() < 8
        assert diagram_view._MAX_SCALE < 8



class TestANewNodesText:
    """A node the Rectangle or Text tool adds said "Node" or "Text" whatever the IDE spoke."""

    @pytest.mark.parametrize(("add", "expected"), [("shape", "節點"), ("text", "文字")])
    def test_is_in_the_ide_language(self, app, monkeypatch, add, expected):
        from pybreeze.extend_multi_language.extend_traditional_chinese import (
            pybreeze_traditional_chinese_word_dict,
        )
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import NodeShape

        monkeypatch.setattr(scene_module.language_wrapper, "language_word_dict", pybreeze_traditional_chinese_word_dict)
        scene = DiagramScene()
        if add == "shape":
            scene._add_shape_node(QPointF(0, 0), NodeShape.RECTANGLE)
        else:
            scene._add_text_node(QPointF(0, 0))

        (node,) = [item for item in scene.items() if isinstance(item, DiagramNode)]
        assert node.text() == expected


class TestResizeFromAHandle:
    """Where a handle drag leaves a node or an image: the size follows the handle's
    sides, a left or top handle moves the item too, and each keeps a minimum size
    (a node 40 x 20, an image 40 x 40) with its far side where it was."""

    @pytest.mark.parametrize("role,dx,dy,expected", [
        ("r", 60, 0, (10, 10, 200, 60)),
        ("b", 0, 30, (10, 10, 140, 90)),
        ("l", 20, 0, (30, 10, 120, 60)),
        ("t", 0, 20, (10, 30, 140, 40)),
        ("br", 10, 10, (10, 10, 150, 70)),
        ("tl", -10, -10, (0, 0, 150, 70)),
        ("r", -500, 0, (10, 10, 40, 60)),
        ("l", 500, 0, (110, 10, 40, 60)),
        ("b", 0, -500, (10, 10, 140, 20)),
        ("t", 0, 500, (10, 50, 140, 20)),
    ])
    def test_a_node(self, app, role, dx, dy, expected):
        from PySide6.QtCore import QRectF

        node = DiagramNode(x=10, y=10, w=140, h=60, text="A")
        node._apply_resize(role, QPointF(dx, dy), QRectF(0, 0, 140, 60), QPointF(10, 10))

        geometry = (node.pos().x(), node.pos().y(), node.node_w, node.node_h)
        assert geometry == expected

    @pytest.mark.parametrize("role,dx,dy,expected", [
        ("r", 60, 0, (10, 10, 200, 60)),
        ("t", 0, 500, (10, 30, 140, 40)),
        ("b", 0, -500, (10, 10, 140, 40)),
        ("l", 500, 0, (110, 10, 40, 60)),
    ])
    def test_an_image(self, app, role, dx, dy, expected):
        from PySide6.QtCore import QRectF

        image = DiagramImage(x=10, y=10, w=140, h=60)
        image._apply_resize(role, QPointF(dx, dy), QRectF(0, 0, 140, 60), QPointF(10, 10))

        geometry = (image.pos().x(), image.pos().y(), image.img_w, image.img_h)
        assert geometry == expected

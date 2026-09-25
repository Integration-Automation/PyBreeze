"""What the diagram canvas does with clicks and keys: drawing a connection, Delete, Esc, Select All.

The align commands and horizontal distribution are in test_diagram_align.py.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from je_editor import language_wrapper
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QGraphicsLineItem, QGraphicsSceneMouseEvent

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramConnection, DiagramImage, DiagramNode
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene, ToolMode


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def scene(app):
    diagram = DiagramScene()
    yield diagram
    diagram.deleteLater()


def _two_nodes(scene: DiagramScene) -> tuple[DiagramNode, DiagramNode]:
    first = DiagramNode(x=0, y=0, w=100, h=60, text="A")
    second = DiagramNode(x=300, y=0, w=100, h=60, text="B")
    scene.addItem(first)
    scene.addItem(second)
    return first, second


def _click(scene: DiagramScene, x: float, y: float) -> None:
    press = QGraphicsSceneMouseEvent(QEvent.Type.GraphicsSceneMousePress)
    press.setScenePos(QPointF(x, y))
    press.setButton(Qt.MouseButton.LeftButton)
    press.setButtons(Qt.MouseButton.LeftButton)
    scene.mousePressEvent(press)


def _press(scene: DiagramScene, key: Qt.Key) -> None:
    scene.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))


def _dashed_lines(scene: DiagramScene) -> list:
    return [item for item in scene.items() if isinstance(item, QGraphicsLineItem)]


class TestDrawingAConnection:
    def test_the_source_then_the_target_makes_one_undoable_connection(self, scene):
        first, second = _two_nodes(scene)
        scene.mode = ToolMode.ADD_CONNECTION

        _click(scene, 50, 30)
        assert len(_dashed_lines(scene)) == 1  # the line that follows the mouse
        _click(scene, 350, 30)

        (connection,) = scene.get_all_connections()
        assert (connection.source, connection.target) == (first, second)
        assert _dashed_lines(scene) == []
        assert scene.mode == ToolMode.SELECT
        scene.undo_stack.undo()
        assert scene.get_all_connections() == []

    def test_a_click_on_the_empty_canvas_cancels_it(self, scene):
        _two_nodes(scene)
        scene.mode = ToolMode.ADD_CONNECTION

        _click(scene, 50, 30)
        _click(scene, 200, 300)

        assert scene.get_all_connections() == []
        assert _dashed_lines(scene) == []

    def test_a_node_is_not_connected_to_itself(self, scene):
        _two_nodes(scene)
        scene.mode = ToolMode.ADD_CONNECTION

        _click(scene, 50, 30)
        _click(scene, 60, 40)

        assert scene.get_all_connections() == []
        assert scene.mode == ToolMode.SELECT

    def test_esc_cancels_it_and_goes_back_to_select(self, scene):
        _two_nodes(scene)
        scene.mode = ToolMode.ADD_CONNECTION
        _click(scene, 50, 30)

        _press(scene, Qt.Key.Key_Escape)
        _click(scene, 350, 30)

        assert scene.get_all_connections() == []
        assert _dashed_lines(scene) == []
        assert scene.mode == ToolMode.SELECT


class TestAddingByClicking:
    @pytest.mark.parametrize("mode", [ToolMode.ADD_RECT, ToolMode.ADD_ROUNDED_RECT,
                                      ToolMode.ADD_ELLIPSE, ToolMode.ADD_DIAMOND])
    def test_a_click_adds_that_shape_centred_on_it_in_one_undo_step(self, scene, mode):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import _MODE_SHAPE_MAP

        scene.mode = mode
        _click(scene, 200, 100)

        (node,) = scene.get_all_nodes()
        assert node.shape_type == _MODE_SHAPE_MAP[mode]
        assert node.center_pos() == QPointF(200, 100)
        assert scene.mode == ToolMode.SELECT  # one node per pick of the tool
        scene.undo_stack.undo()
        assert scene.get_all_nodes() == []

    def test_a_click_in_text_mode_adds_a_text_box(self, scene):
        scene.mode = ToolMode.ADD_TEXT
        _click(scene, 200, 100)

        (node,) = scene.get_all_nodes()
        assert node.text() == language_wrapper.language_word_dict.get("diagram_editor_new_text_text")
        assert node.center_pos() == QPointF(200, 100)
        assert scene.mode == ToolMode.SELECT

    def test_a_right_press_adds_nothing(self, scene):
        scene.mode = ToolMode.ADD_RECT
        press = QGraphicsSceneMouseEvent(QEvent.Type.GraphicsSceneMousePress)
        press.setScenePos(QPointF(200, 100))
        press.setButton(Qt.MouseButton.RightButton)
        scene.mousePressEvent(press)

        assert scene.get_all_nodes() == []
        assert scene.mode == ToolMode.ADD_RECT


def test_the_dashed_line_follows_the_mouse_while_a_connection_is_drawn(scene):
    first, _second = _two_nodes(scene)
    scene.mode = ToolMode.ADD_CONNECTION
    _click(scene, 50, 30)
    move = QGraphicsSceneMouseEvent(QEvent.Type.GraphicsSceneMouseMove)
    move.setScenePos(QPointF(250, 200))

    scene.mouseMoveEvent(move)

    (line,) = _dashed_lines(scene)
    assert line.line().p1() == first.center_pos()
    assert line.line().p2() == QPointF(250, 200)


class TestDelete:
    @pytest.mark.parametrize("key", [Qt.Key.Key_Delete, Qt.Key.Key_Backspace])
    def test_a_node_goes_with_its_connections_in_one_undo_step(self, scene, key):
        first, second = _two_nodes(scene)
        with scene.undo_scope("Connect"):
            scene.addItem(DiagramConnection(first, second))
        first.setSelected(True)

        _press(scene, key)

        assert [node.text() for node in scene.get_all_nodes()] == ["B"]
        assert scene.get_all_connections() == []
        scene.undo_stack.undo()
        assert sorted(node.text() for node in scene.get_all_nodes()) == ["A", "B"]
        assert len(scene.get_all_connections()) == 1

    def test_a_connection_alone_leaves_its_nodes(self, scene):
        first, second = _two_nodes(scene)
        connection = DiagramConnection(first, second)
        scene.addItem(connection)
        connection.setSelected(True)

        scene.delete_selected()

        assert scene.get_all_connections() == []
        assert len(scene.get_all_nodes()) == 2
        assert first.connections == []
        assert second.connections == []

    def test_nothing_selected_leaves_no_undo_step(self, scene):
        _two_nodes(scene)

        scene.delete_selected()

        assert not scene.undo_stack.canUndo()

    def test_while_a_node_is_being_edited_the_key_edits_its_text(self, app):
        # Delete removed the node being typed into
        from PySide6.QtWidgets import QGraphicsView

        scene = DiagramScene()
        view = QGraphicsView(scene)
        view.show()
        node, _second = _two_nodes(scene)
        node.setSelected(True)
        node.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        node.label.setFocus()
        app.processEvents()

        _press(scene, Qt.Key.Key_Delete)

        assert node in scene.get_all_nodes()
        view.close()
        view.deleteLater()


class TestSelectAll:
    def test_every_node_connection_and_image_but_not_the_dashed_line(self, scene):
        first, second = _two_nodes(scene)
        scene.addItem(DiagramConnection(first, second))
        scene.addItem(DiagramImage(x=0, y=200, w=50, h=50))
        scene.mode = ToolMode.ADD_CONNECTION
        _click(scene, 50, 30)  # a connection being drawn

        scene.select_all()

        assert len(scene.selectedItems()) == 4
        assert not any(isinstance(item, QGraphicsLineItem) for item in scene.selectedItems())


class TestDistributeVertically:
    def test_equal_gaps_between_the_outer_two(self, scene):
        boxes = ((0, 0, 100, 40), (10, 70, 100, 20), (20, 400, 100, 60))
        nodes = []
        for x, y, w, h in boxes:
            node = DiagramNode(x=x, y=y, w=w, h=h, text="n")
            scene.addItem(node)
            node.setSelected(True)
            nodes.append(node)

        scene.distribute_v()

        tops = [node.pos().y() for node in nodes]
        assert tops[0] == 0
        assert tops[2] == 400
        assert tops[1] - 40 == pytest.approx(400 - (tops[1] + 20))
        assert [node.pos().x() for node in nodes] == [0, 10, 20]

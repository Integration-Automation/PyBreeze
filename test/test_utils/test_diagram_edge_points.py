"""Where a connection meets a node: on the node's own outline, whatever its shape."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramConnection, DiagramNode, NodeShape


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _node(shape: NodeShape, x: float = 0, y: float = 0) -> DiagramNode:
    """A 100 by 60 node: its centre is (x + 50, y + 30)."""
    return DiagramNode(x=x, y=y, w=100, h=60, text="", shape=shape)


def _point(point: QPointF) -> tuple[float, float]:
    return round(point.x(), 3), round(point.y(), 3)


class TestTheRectangle:
    @pytest.mark.parametrize(("target", "edge"), [
        ((150, 30), (100, 30)),    # straight right
        ((50, 130), (50, 60)),     # straight down
        ((50, -70), (50, 0)),      # straight up
        ((250, 60), (100, 37.5)),  # shallow: the side
        ((150, 130), (80, 60)),    # steep: the bottom
    ])
    def test_the_line_from_the_centre_meets_the_edge_it_crosses(self, app, target, edge):
        for shape in (NodeShape.RECTANGLE, NodeShape.ROUNDED_RECT):
            assert _point(_node(shape).edge_point(QPointF(*target))) == edge


class TestTheEllipse:
    @pytest.mark.parametrize("target", [(150, 30), (50, 130), (150, 130), (-20, -40)])
    def test_the_point_is_on_the_ellipse_towards_the_target(self, app, target):
        point = _node(NodeShape.ELLIPSE).edge_point(QPointF(*target))

        assert ((point.x() - 50) / 50) ** 2 + ((point.y() - 30) / 30) ** 2 == pytest.approx(1)
        # In the target's direction as seen from the centre
        assert math.copysign(1, point.x() - 50) == math.copysign(1, target[0] - 50) or target[0] == 50
        assert math.copysign(1, point.y() - 30) == math.copysign(1, target[1] - 30) or target[1] == 30

    def test_straight_right_is_the_widest_point(self, app):
        assert _point(_node(NodeShape.ELLIPSE).edge_point(QPointF(150, 30))) == (100, 30)


class TestTheDiamond:
    @pytest.mark.parametrize(("target", "edge"), [
        ((150, 30), (100, 30)),
        ((150, 130), (68.75, 48.75)),
    ])
    def test_the_point_is_on_the_diamond(self, app, target, edge):
        point = _node(NodeShape.DIAMOND).edge_point(QPointF(*target))

        assert _point(point) == edge
        assert abs(point.x() - 50) / 50 + abs(point.y() - 30) / 30 == pytest.approx(1)


@pytest.mark.parametrize("shape", list(NodeShape))
def test_the_centre_itself_is_the_centre(app, shape):
    assert _point(_node(shape).edge_point(QPointF(50, 30))) == (50, 30)


class TestAConnectionFollowsItsNodes:
    def _pair(self):
        source = _node(NodeShape.RECTANGLE)
        target = _node(NodeShape.RECTANGLE, x=300)
        connection = DiagramConnection(source, target)  # it joins both nodes itself
        return source, target, connection

    def test_a_node_given_a_new_size_moves_the_end_on_it(self, app):
        source, target, connection = self._pair()

        source.set_size(200, 60)

        start = connection.path().elementAt(0)
        assert (start.x, start.y) == _point(source.edge_point(target.center_pos()))
        assert start.x == 200  # the right edge of the wider node

    def test_a_node_resized_by_its_handle_moves_the_end_on_it(self, app):
        from PySide6.QtCore import QRectF

        source, target, connection = self._pair()

        source._apply_resize("r", QPointF(50, 0), QRectF(0, 0, 100, 60), QPointF(0, 0))

        start = connection.path().elementAt(0)
        assert start.x == pytest.approx(150)

"""Each node shape is drawn as its shape: the canvas is rendered and its pixels looked at.

A rounded rectangle is painted by its own ``paint``; nothing rendered one, so a
body drawn square (or not at all) would have gone unseen.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode, NodeShape, NodeStyle
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene

_FILL = QColor("#ff0000")
_WIDTH, _HEIGHT = 140, 60


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _rendered(shape: NodeShape) -> QImage:
    """A white image of one node of *shape*, filled red, drawn at 1:1 from the scene's origin."""
    scene = DiagramScene()
    node = DiagramNode(x=0, y=0, w=_WIDTH, h=_HEIGHT, text="", shape=shape, style=NodeStyle(fill_color="#ff0000"))
    scene.addItem(node)
    image = QImage(_WIDTH, _HEIGHT, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    scene.render(painter, QRectF(0, 0, _WIDTH, _HEIGHT), QRectF(0, 0, _WIDTH, _HEIGHT))
    painter.end()
    scene.deleteLater()
    return image


def _is_fill(image: QImage, x: int, y: int) -> bool:
    return image.pixelColor(x, y) == _FILL


@pytest.mark.parametrize("shape", list(NodeShape))
def test_the_middle_is_filled(app, shape):
    assert _is_fill(_rendered(shape), _WIDTH // 2, _HEIGHT // 2)


@pytest.mark.parametrize(("shape", "corner_filled"), [
    (NodeShape.RECTANGLE, True),
    (NodeShape.ROUNDED_RECT, False),
    (NodeShape.ELLIPSE, False),
    (NodeShape.DIAMOND, False),
])
def test_a_corner_is_filled_only_for_a_rectangle(app, shape, corner_filled):
    # Just inside the border, two pixels in from the top left corner
    assert _is_fill(_rendered(shape), 3, 3) is corner_filled

"""The diagram canvas's zoom (Ctrl+0) and the background grid it draws.

Fit is covered by test_diagram_editing.py.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from pybreeze.pybreeze_ui.diagram_editor import diagram_view as view_module
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene
from pybreeze.pybreeze_ui.diagram_editor.diagram_view import DiagramView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app):
    made = DiagramView(DiagramScene())
    made.resize(400, 300)
    yield made
    made.deleteLater()


def _zoom_reported(view) -> list[int]:
    reported: list[int] = []
    view.zoom_changed.connect(reported.append)
    return reported


class TestSetZoom:
    @pytest.mark.parametrize("percent,scale", [(100, 1.0), (250, 2.5), (1, 0.1), (900, 5.0)])
    def test_the_zoom_is_set_within_the_range(self, view, percent, scale):
        reported = _zoom_reported(view)
        view.set_zoom(150)  # from somewhere else, not added to it

        view.set_zoom(percent)

        assert view.transform().m11() == pytest.approx(scale)
        assert reported[-1] == int(scale * 100)


class TestTheGrid:
    def test_it_is_off_until_turned_on(self, view):
        assert view.draw_grid is False
        view.draw_grid = True
        assert view.draw_grid is True

    def test_a_cell_is_never_smaller_than_five(self, view):
        view.grid_size = 2
        assert view.grid_size == 5
        view.grid_size = 30
        assert view.grid_size == 30

    @staticmethod
    def _background(view, left: float, top: float) -> QImage:
        """The background drawn for the 100 x 100 scene area at (*left*, *top*), as an image."""
        image = QImage(100, 100, QImage.Format.Format_RGB32)
        painter = QPainter(image)
        painter.translate(-left, -top)
        view.drawBackground(painter, QRectF(left, top, 100, 100))
        painter.end()
        return image

    def test_without_it_the_background_is_plain(self, view):
        image = self._background(view, 0, 0)

        assert {image.pixelColor(x, 50).name() for x in range(100)} == {view_module._BG_COLOR.name()}

    def test_lines_fall_on_multiples_of_the_cell_size(self, view):
        view.draw_grid = True
        image = self._background(view, 0, 0)

        background = view_module._BG_COLOR.name()
        assert image.pixelColor(0, 50).name() == view_module._GRID_COLOR_MAJOR.name()  # every fifth line
        assert image.pixelColor(20, 50).name() != background  # a minor line, drawn thinner
        assert image.pixelColor(10, 50).name() == background

    def test_a_new_cell_size_moves_the_lines_while_the_grid_is_shown(self, view):
        view.draw_grid = True
        view.grid_size = 30

        image = self._background(view, 0, 0)
        background = view_module._BG_COLOR.name()
        assert image.pixelColor(30, 50).name() != background
        assert image.pixelColor(20, 50).name() == background

    def test_left_of_the_origin_too(self, view):
        # Scene x -30 to 70: lines at -20, 0, 20..., which are image columns 10, 30, 50...
        view.draw_grid = True
        image = self._background(view, -30, 0)

        background = view_module._BG_COLOR.name()
        assert image.pixelColor(10, 50).name() != background
        assert image.pixelColor(30, 50).name() == view_module._GRID_COLOR_MAJOR.name()
        assert image.pixelColor(20, 50).name() == background

"""A node or an image moved with the grid on lands on the grid; resized, or with the grid off, it does not."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramImage, DiagramNode


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(params=[DiagramNode, DiagramImage], ids=["node", "image"])
def kind(request, app, monkeypatch):
    """Each kind of item, with the grid on at 20 for the test (a class setting, as the scene sets it)."""
    monkeypatch.setattr(request.param, "grid_enabled", True)
    monkeypatch.setattr(request.param, "grid_size", 20)
    return request.param


def _moved(item, x: float, y: float) -> tuple[float, float]:
    item.setPos(QPointF(x, y))
    return item.pos().x(), item.pos().y()


def test_a_move_lands_on_the_nearest_grid_point(kind):
    assert _moved(kind(), 33, 47) == (40, 40)
    assert _moved(kind(), -9, 11) == (0, 20)


def test_with_the_grid_off_it_stays_where_it_was_put(kind, monkeypatch):
    monkeypatch.setattr(kind, "grid_enabled", False)

    assert _moved(kind(), 33, 47) == (33, 47)


def test_a_grid_of_no_size_does_not_snap(kind, monkeypatch):
    monkeypatch.setattr(kind, "grid_size", 0)

    assert _moved(kind(), 33, 47) == (33, 47)


def test_while_it_is_resized_it_is_not_snapped(kind):
    # A resize from the top or left moves the item with the handle
    item = kind()
    item._resizing = True

    assert _moved(item, 33, 47) == (33, 47)

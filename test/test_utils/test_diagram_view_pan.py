"""Panning the diagram canvas with the right or middle button, and the menu a right click opens."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent, QGuiApplication, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.diagram_editor import diagram_scene as scene_module
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene
from pybreeze.pybreeze_ui.diagram_editor.diagram_view import DiagramView

_NO_KEYS = Qt.KeyboardModifier.NoModifier


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def menus(monkeypatch) -> list:
    """Every canvas menu that opens, recorded instead of shown."""
    opened: list = []

    class Menu:
        def __init__(self, *_args) -> None:
            self.entries: list = []

        def addAction(self, *entry) -> None:
            self.entries.append(entry)

        def addSeparator(self) -> None:
            """Separators are not choices."""

        def actions(self) -> list:
            return self.entries

        def exec(self, *_args) -> None:
            opened.append(self)

    monkeypatch.setattr(scene_module, "QMenu", Menu)
    return opened


@pytest.fixture
def menu_on_release(app):
    """Open context menus as Windows does, on the right button's release."""
    hints = QGuiApplication.styleHints()
    before = hints.contextMenuTrigger()
    hints.setContextMenuTrigger(Qt.ContextMenuTrigger.Release)
    yield
    hints.setContextMenuTrigger(before)


@pytest.fixture
def menu_on_press(app):
    """Open context menus as Linux and macOS do, on the right button's press."""
    hints = QGuiApplication.styleHints()
    before = hints.contextMenuTrigger()
    hints.setContextMenuTrigger(Qt.ContextMenuTrigger.Press)
    yield
    hints.setContextMenuTrigger(before)


@pytest.fixture
def view(app):
    scene = DiagramScene()
    scene.setSceneRect(0, 0, 3000, 3000)
    shown = DiagramView(scene)
    shown.resize(400, 300)
    shown.show()
    assert QTest.qWaitForWindowExposed(shown)
    yield shown
    shown.close()
    shown.deleteLater()


def _at(view: DiagramView, x: int, y: int) -> QPoint:
    """A point on the canvas, in the window's coordinates."""
    return view.viewport().mapTo(view.window(), QPoint(x, y))


def _drag(view: DiagramView, button: Qt.MouseButton, start: tuple, end: tuple) -> None:
    # Through the window, as the platform delivers them: that is where Qt
    # turns a right button into a context menu
    window = view.windowHandle()
    QTest.mousePress(window, button, _NO_KEYS, _at(view, *start))
    QTest.mouseMove(window, _at(view, (start[0] + end[0]) // 2, (start[1] + end[1]) // 2))
    QTest.mouseMove(window, _at(view, *end))
    QTest.mouseRelease(window, button, _NO_KEYS, _at(view, *end))
    QApplication.processEvents()


def test_a_right_drag_pans_and_opens_no_menu(view, menus, menu_on_release):
    left = view.horizontalScrollBar().value()

    _drag(view, Qt.MouseButton.RightButton, (200, 150), (100, 100))

    assert view.horizontalScrollBar().value() == left + 100
    # Every right-drag used to end in the canvas menu
    assert menus == []


def test_a_right_click_still_opens_the_menu(view, menus, menu_on_release):
    _drag(view, Qt.MouseButton.RightButton, (200, 150), (200, 150))

    assert len(menus) == 1


def test_a_right_click_after_a_right_drag_opens_the_menu(view, menus, menu_on_release):
    _drag(view, Qt.MouseButton.RightButton, (200, 150), (100, 100))
    _drag(view, Qt.MouseButton.RightButton, (50, 50), (50, 50))

    assert len(menus) == 1


def test_a_middle_drag_pans(view, menus, menu_on_release):
    top = view.verticalScrollBar().value()

    _drag(view, Qt.MouseButton.MiddleButton, (200, 150), (200, 90))

    assert view.verticalScrollBar().value() == top + 60
    assert menus == []


def test_the_menu_key_after_a_right_drag_opens_the_menu(view, menus, menu_on_release):
    _drag(view, Qt.MouseButton.RightButton, (200, 150), (100, 100))

    at = QPoint(50, 50)
    key = QContextMenuEvent(QContextMenuEvent.Reason.Keyboard, at, view.viewport().mapToGlobal(at))
    QApplication.sendEvent(view.viewport(), key)

    assert len(menus) == 1


def test_a_pan_whose_release_went_elsewhere_stops_with_the_next_move(view, menus, menu_on_press):
    # A menu opened on the press (Linux, macOS) takes the release, and the
    # canvas went on following a mouse with no button held
    window = view.windowHandle()
    QTest.mousePress(window, Qt.MouseButton.RightButton, _NO_KEYS, _at(view, 200, 150))
    assert len(menus) == 1
    left = view.horizontalScrollBar().value()

    move = QMouseEvent(
        QEvent.Type.MouseMove, QPointF(100, 150), QPointF(view.viewport().mapToGlobal(QPoint(100, 150))),
        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, _NO_KEYS)
    QApplication.sendEvent(view.viewport(), move)

    assert view.horizontalScrollBar().value() == left
    QTest.mouseRelease(window, Qt.MouseButton.RightButton, _NO_KEYS, _at(view, 100, 150))

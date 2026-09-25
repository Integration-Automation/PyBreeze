"""A menu entry that builds a slow widget shows the wait cursor meanwhile, and gives the cursor back."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QTabWidget, QWidget

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu import menu_utils
from pybreeze.pybreeze_ui.menu.menu_utils import busy_cursor


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _cursor_shape():
    cursor = QApplication.overrideCursor()
    return None if cursor is None else cursor.shape()


class Window(QMainWindow):
    """The members of the main window the menus touch."""

    def __init__(self) -> None:
        super().__init__()
        self.tab_widget = QTabWidget()
        self.automation_menu = QMenu()


@pytest.fixture
def window(app):
    made = Window()
    yield made
    made.deleteLater()


def _recording_factory(seen: list):
    def build(*_args) -> QWidget:
        seen.append(_cursor_shape())
        return QWidget()
    return build


class TestBusyCursor:
    def test_the_wait_cursor_is_shown_while_the_block_runs(self, app):
        with busy_cursor():
            inside = _cursor_shape()

        assert inside == Qt.CursorShape.WaitCursor
        assert _cursor_shape() is None

    def test_the_cursor_goes_back_when_the_block_fails(self, app):
        with pytest.raises(RuntimeError), busy_cursor():
            raise RuntimeError("the widget could not be built")

        assert _cursor_shape() is None


class TestTheEntriesThatBuildWidgets:
    def test_a_tools_tab(self, window, monkeypatch):
        from pybreeze.pybreeze_ui.menu.tools import tools_menu

        seen: list = []
        monkeypatch.setitem(tools_menu._WIDGET_FACTORIES, "SSH", _recording_factory(seen))

        tools_menu._open_tab_handler(window, "SSH", "extend_tools_menu_ssh_client_tab_label")()

        assert seen == [Qt.CursorShape.WaitCursor]
        assert window.tab_widget.count() == 1
        assert _cursor_shape() is None

    def test_a_tools_dock(self, window, monkeypatch):
        from pybreeze.pybreeze_ui.menu.tools import tools_menu

        seen: list = []
        monkeypatch.setitem(tools_menu._WIDGET_FACTORIES, "SSH", _recording_factory(seen))

        tools_menu.add_dock(window, "SSH")

        assert seen == [Qt.CursorShape.WaitCursor]
        assert _cursor_shape() is None

    def test_an_automation_packages_gui(self, window):
        from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
            AutomationMenu, build_automation_menu,
        )

        seen: list = []
        menu = build_automation_menu(window, AutomationMenu(
            "run_label", gui_widget_factory=_recording_factory(seen), gui_label="GUI"))

        menu.actions()[0].trigger()

        assert seen == [Qt.CursorShape.WaitCursor]
        assert window.tab_widget.count() == 1
        assert _cursor_shape() is None

    def test_a_help_page(self, window, monkeypatch):
        seen: list = []
        monkeypatch.setattr(menu_utils, "MainBrowserWidget", lambda start_url: _recording_factory(seen)())

        menu_utils.open_web_browser(window, "https://docs.example", "Docs")

        assert seen == [Qt.CursorShape.WaitCursor]
        assert window.tab_widget.tabText(0) == "Docs0"
        assert _cursor_shape() is None

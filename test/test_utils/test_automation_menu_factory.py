"""The automation menu factory: every entry it builds is still there, and still answers, later.

A QAction added to a menu is not owned by it. One kept only in a local variable
is deleted when the builder returns, and its entry disappears from the menu, so
each test collects garbage before looking.
"""
from __future__ import annotations

import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QTabWidget, QWidget

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.automation_menu import automation_menu_factory
from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    build_automation_menu
)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class FakeWindow(QMainWindow):
    """A main window with the members the factory touches."""

    def __init__(self):
        super().__init__()
        self.automation_menu = self.menuBar().addMenu("Automation")
        self.tab_widget = QTabWidget()


@pytest.fixture
def window(app):
    fake = FakeWindow()
    yield fake
    fake.deleteLater()


def _submenu_actions(menu: QMenu, index: int) -> list[QAction]:
    # Hold the submenu's own action while asking it for the submenu: PySide
    # deletes the submenu along with a temporary wrapper of that action.
    submenu_action = menu.actions()[index]
    return submenu_action.menu().actions()


def test_run_actions_survive_and_answer(window):
    calls = []
    menu = build_automation_menu(
        window, "run_label",
        run_actions=[
            {"label_key": "run_label", "callback": lambda: calls.append("first")},
            {"label_key": "help_label", "callback": lambda: calls.append("second")},
        ],
    )
    gc.collect()

    run_actions = _submenu_actions(menu, 0)
    assert len(run_actions) == 2
    run_actions[1].trigger()
    assert calls == ["second"]


def test_help_actions_survive_and_open_their_page(window, monkeypatch):
    opened = []
    monkeypatch.setattr(
        automation_menu_factory, "open_web_browser",
        lambda ui, url, label: opened.append(url))
    menu = build_automation_menu(
        window, "run_label",
        doc_url="https://docs.example", doc_label_key="help_label",
        doc_tab_label_key="help_label",
        github_url="https://github.example", github_label_key="run_label",
        github_tab_label_key="run_label",
    )
    gc.collect()

    help_actions = _submenu_actions(menu, 0)
    assert len(help_actions) == 2
    for action in help_actions:
        action.trigger()
    assert opened == ["https://docs.example", "https://github.example"]


def test_project_and_gui_actions_survive_and_answer(window):
    created = []
    menu = build_automation_menu(
        window, "run_label",
        create_project_func=lambda: created.append(True),
        create_project_label_key="project_label",
        gui_widget_class=QWidget, gui_label="GUI",
    )
    gc.collect()

    project_actions = _submenu_actions(menu, 0)
    assert len(project_actions) == 1
    project_actions[0].trigger()
    assert created == [True]

    gui_action = menu.actions()[1]
    assert gui_action.text() == "GUI"
    gui_action.trigger()
    assert window.tab_widget.count() == 1

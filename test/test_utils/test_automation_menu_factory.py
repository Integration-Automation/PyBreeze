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
    AutomationMenu, HelpLink, RunAction, build_automation_menu
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
    menu = build_automation_menu(window, AutomationMenu(
        "run_label",
        run_actions=(
            RunAction("run_label", lambda: calls.append("first")),
            RunAction("help_label", lambda: calls.append("second")),
        ),
    ))
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
    menu = build_automation_menu(window, AutomationMenu(
        "run_label",
        help_links=(
            HelpLink("https://docs.example", "help_label", "help_label"),
            HelpLink("https://github.example", "run_label", "run_label"),
        ),
    ))
    gc.collect()

    help_actions = _submenu_actions(menu, 0)
    assert len(help_actions) == 2
    for action in help_actions:
        action.trigger()
    assert opened == ["https://docs.example", "https://github.example"]


def test_project_and_gui_actions_survive_and_answer(window):
    created = []
    menu = build_automation_menu(window, AutomationMenu(
        "run_label",
        create_project=lambda: created.append(True),
        create_project_label_key="project_label",
        gui_widget_factory=QWidget, gui_label="GUI",
    ))
    gc.collect()

    project_actions = _submenu_actions(menu, 0)
    assert len(project_actions) == 1
    project_actions[0].trigger()
    assert created == [True]

    gui_action = menu.actions()[1]
    assert gui_action.text() == "GUI"
    gui_action.trigger()
    assert window.tab_widget.count() == 1


def test_every_create_project_names_a_package_that_exists():
    # Found by finding the package, not importing it: some of these write a log
    # into the working directory as they import.
    import importlib.util
    import re
    from pathlib import Path

    menus = Path(__file__).resolve().parents[2] / "pybreeze" / "pybreeze_ui" / "menu" / "automation_menu"
    names = [name for path in menus.rglob("*.py")
             for name in re.findall(r'safe_create_project\(\w+, "([^"]+)"\)', path.read_text(encoding="utf-8"))]

    assert names, "no create-project entries found"
    assert [name for name in names if importlib.util.find_spec(name) is None] == []


@pytest.mark.parametrize("menu_module, set_menu, gui_module, class_name, label", [
    ("load_density_menu.build_load_density_menu", "set_load_density_menu",
     "je_load_density.gui.main_widget", "LoadDensityWidget", "LoadDensity GUI"),
    ("api_testka_menu.build_api_testka_menu", "set_apitestka_menu",
     "je_api_testka.gui.main_widget", "APITestkaWidget", "APITestka GUI"),
])
def test_a_gui_entry_imports_the_packages_gui_when_chosen(
        window, monkeypatch, menu_module, set_menu, gui_module, class_name, label):
    # A stand-in module, so the package is never imported here: Load Density's
    # brings locust, which patches the whole process with gevent as it imports
    import importlib
    import sys
    import types

    class PackageGUI(QWidget):
        """Stands in for the package's own GUI."""

    stand_in = types.ModuleType(gui_module)
    setattr(stand_in, class_name, PackageGUI)
    monkeypatch.setitem(sys.modules, gui_module, stand_in)
    module = importlib.import_module(f"pybreeze.pybreeze_ui.menu.automation_menu.{menu_module}")
    getattr(module, set_menu)(window)
    gc.collect()

    package_menus = window.automation_menu.actions()
    (gui_action,) = [action for action in package_menus[0].menu().actions() if action.text() == label]
    gui_action.trigger()

    assert isinstance(window.tab_widget.widget(0), PackageGUI)
    assert window.tab_widget.tabText(0) == label


@pytest.mark.parametrize("create_project_dir", [
    lambda project_path=None: None,                       # no parent_name at all
    lambda project_path=None, parent_name=None: None,     # one that is not a folder name
])
def test_a_package_that_names_no_project_folder_gets_none(create_project_dir):
    # The message then says the project went into the chosen folder itself
    assert automation_menu_factory._project_folder_name(create_project_dir) == ""


def test_the_project_folder_is_the_default_parent_name():
    def create_project_dir(project_path=None, parent_name="WebRunner"):
        """A package's own, as je_web_runner's."""

    assert automation_menu_factory._project_folder_name(create_project_dir) == "WebRunner"

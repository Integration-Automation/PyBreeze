from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.menu.menu_utils import open_web_browser
from pybreeze.utils.logging.logger import pybreeze_logger

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


@dataclass(frozen=True)
class RunAction:
    """One entry of the Run submenu: a language key for its label and what it runs."""
    label_key: str
    callback: Callable[[], None]


@dataclass(frozen=True)
class HelpLink:
    """One entry of the HELP submenu: a page opened in a browser tab."""
    url: str
    label_key: str
    tab_label_key: str


@dataclass(frozen=True)
class AutomationMenu:
    """Everything one automation package's menu holds.

    A submenu is built only when it has entries; the project entry needs both
    ``create_project`` and its label key, and the GUI entry both the widget
    class and its label.
    """
    label_key: str
    run_actions: tuple[RunAction, ...] = ()
    help_links: tuple[HelpLink, ...] = ()
    create_project: Callable[[], None] | None = None
    create_project_label_key: str | None = None
    gui_widget_class: type[QWidget] | None = None
    gui_label: str | None = None


def build_automation_menu(ui: PyBreezeMainWindow, spec: AutomationMenu) -> QMenu:
    """Add a standard automation submenu, described by *spec*, to ``ui.automation_menu``.

    In order: a Run submenu, a HELP submenu, a Project submenu and an entry that
    opens the package's GUI as a tab. Every QAction takes the menu it sits in as
    its parent: a menu does not own the actions added to it, so an action held
    only here would be deleted when this returns and its entry would disappear.

    :param ui: The main window instance.
    :param spec: What the menu holds.
    :return: The created QMenu.
    """
    lang = language_wrapper.language_word_dict
    menu = ui.automation_menu.addMenu(lang.get(spec.label_key))
    if spec.run_actions:
        _add_run_menu(menu, spec.run_actions)
    if spec.help_links:
        _add_help_menu(ui, menu, spec.help_links)
    if spec.create_project and spec.create_project_label_key:
        _add_project_menu(menu, spec.create_project, spec.create_project_label_key)
    if spec.gui_widget_class and spec.gui_label:
        _add_gui_action(ui, menu, spec.gui_widget_class, spec.gui_label)
    return menu


def _add_run_menu(menu: QMenu, run_actions: tuple[RunAction, ...]) -> None:
    lang = language_wrapper.language_word_dict
    run_menu = menu.addMenu(lang.get("run_label"))
    for run_action in run_actions:
        action = QAction(lang.get(run_action.label_key), run_menu)
        action.triggered.connect(run_action.callback)
        run_menu.addAction(action)


def _add_help_menu(ui: PyBreezeMainWindow, menu: QMenu, links: tuple[HelpLink, ...]) -> None:
    lang = language_wrapper.language_word_dict
    help_menu = menu.addMenu(lang.get("help_label"))
    for link in links:
        action = QAction(lang.get(link.label_key), help_menu)
        action.triggered.connect(
            lambda checked=False, url=link.url, tab_label_key=link.tab_label_key:
                open_web_browser(ui, url, lang.get(tab_label_key))
        )
        help_menu.addAction(action)


def _add_project_menu(menu: QMenu, create_project: Callable[[], None], label_key: str) -> None:
    lang = language_wrapper.language_word_dict
    project_menu = menu.addMenu(lang.get("project_label"))
    action = QAction(lang.get(label_key), project_menu)
    action.triggered.connect(create_project)
    project_menu.addAction(action)


def _add_gui_action(
        ui: PyBreezeMainWindow, menu: QMenu, widget_class: type[QWidget], label: str) -> None:
    action = QAction(label, menu)
    action.triggered.connect(
        lambda checked=False: ui.tab_widget.addTab(widget_class(), label)
    )
    menu.addAction(action)


def safe_create_project(import_name: str) -> Callable:
    """Create a safe project creation function that handles ImportError."""
    def _create():
        try:
            package = importlib.import_module(import_name)  # nosec  # nosemgrep  # plugin registry uses a curated whitelist of automation packages (build_process)
            package.create_project_dir()
        except ImportError as error:
            pybreeze_logger.error(f"Failed to import {import_name}: {error}")
    return _create

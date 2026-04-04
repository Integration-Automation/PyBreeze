from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.menu.menu_utils import open_web_browser
from pybreeze.utils.logging.logger import pybreeze_logger

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def build_automation_menu(
        ui: PyBreezeMainWindow,
        menu_label_key: str,
        run_actions: list[dict] | None = None,
        doc_url: str | None = None,
        doc_label_key: str | None = None,
        doc_tab_label_key: str | None = None,
        github_url: str | None = None,
        github_label_key: str | None = None,
        github_tab_label_key: str | None = None,
        create_project_func: Callable | None = None,
        create_project_label_key: str | None = None,
        gui_widget_class: type | None = None,
        gui_label: str | None = None,
) -> QMenu:
    """
    Factory function to build a standard automation sub-menu.

    :param ui: The main window instance.
    :param menu_label_key: Language key for the menu label.
    :param run_actions: List of dicts with keys:
        - "label_key": language key for action label
        - "callback": callable to trigger
    :param doc_url: Documentation URL.
    :param doc_label_key: Language key for doc action label.
    :param doc_tab_label_key: Language key for doc tab label.
    :param github_url: GitHub URL.
    :param github_label_key: Language key for github action label.
    :param github_tab_label_key: Language key for github tab label.
    :param create_project_func: Callable to create project directory.
    :param create_project_label_key: Language key for create project action.
    :param gui_widget_class: Optional widget class to add as a tab.
    :param gui_label: Label for the GUI tab.
    :return: The created QMenu.
    """
    lang = language_wrapper.language_word_dict

    # Main menu
    menu = ui.automation_menu.addMenu(lang.get(menu_label_key))

    # Run sub-menu
    if run_actions:
        run_menu = menu.addMenu(lang.get("run_label"))
        for action_config in run_actions:
            action = QAction(lang.get(action_config["label_key"]))
            callback = action_config["callback"]
            action.triggered.connect(callback)
            run_menu.addAction(action)

    # Help sub-menu
    if doc_url or github_url:
        help_menu = menu.addMenu(lang.get("help_label"))
        if doc_url and doc_label_key:
            doc_action = QAction(lang.get(doc_label_key))
            doc_action.triggered.connect(
                lambda checked=False, u=doc_url, t=doc_tab_label_key:
                    open_web_browser(ui, u, lang.get(t))
            )
            help_menu.addAction(doc_action)
        if github_url and github_label_key:
            github_action = QAction(lang.get(github_label_key))
            github_action.triggered.connect(
                lambda checked=False, u=github_url, t=github_tab_label_key:
                    open_web_browser(ui, u, lang.get(t))
            )
            help_menu.addAction(github_action)

    # Project sub-menu
    if create_project_func and create_project_label_key:
        project_menu = menu.addMenu(lang.get("project_label"))
        create_action = QAction(lang.get(create_project_label_key))
        create_action.triggered.connect(create_project_func)
        project_menu.addAction(create_action)

    # GUI widget tab
    if gui_widget_class and gui_label:
        gui_action = QAction(gui_label)
        gui_action.triggered.connect(
            lambda checked=False: ui.tab_widget.addTab(gui_widget_class(), gui_label)
        )
        menu.addAction(gui_action)

    return menu


def safe_create_project(import_name: str) -> Callable:
    """Create a safe project creation function that handles ImportError."""
    def _create():
        try:
            import importlib
            package = importlib.import_module(import_name)
            if package is not None:
                package.create_project_dir()
        except ImportError as error:
            pybreeze_logger.error(f"Failed to import {import_name}: {error}")
    return _create

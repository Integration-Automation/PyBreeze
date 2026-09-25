from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    AutomationMenu, HelpLink, build_automation_menu, package_run_actions, safe_create_project
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def _api_testka_gui() -> QWidget:
    # Imported when its tab opens, not with the menus as the IDE starts
    from je_api_testka.gui.main_widget import APITestkaWidget
    return APITestkaWidget()


def set_apitestka_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(ui_we_want_to_set, AutomationMenu(
        label_key="apitestka_menu_label",
        run_actions=package_run_actions(ui_we_want_to_set, "apitestka", "je_api_testka"),
        help_links=(
            HelpLink("https://apitestka.readthedocs.io/en/latest/",
                     "apitestka_doc_label", "apitestka_doc_tab_label"),
            HelpLink("https://github.com/Integration-Automation/APITestka",
                     "apitestka_github_label", "apitestka_github_tab_label"),
        ),
        create_project=safe_create_project(ui_we_want_to_set, "je_api_testka"),
        create_project_label_key="apitestka_create_project_label",
        gui_widget_factory=_api_testka_gui,
        gui_label="APITestka GUI",
    ))

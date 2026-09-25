from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    AutomationMenu, HelpLink, build_automation_menu, package_run_actions, safe_create_project
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def set_automation_file_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(ui_we_want_to_set, AutomationMenu(
        label_key="file_automation_menu_label",
        run_actions=package_run_actions(ui_we_want_to_set, "file_automation", "automation_file"),
        help_links=(
            HelpLink("https://fileautomation.readthedocs.io/en/latest/",
                     "file_automation_doc_label", "file_automation_doc_tab_label"),
            HelpLink("https://github.com/Integration-Automation/FileAutomation",
                     "file_automation_github_label", "file_automation_github_tab_label"),
        ),
        create_project=safe_create_project(ui_we_want_to_set, "automation_file"),
        create_project_label_key="file_automation_create_project_label",
    ))

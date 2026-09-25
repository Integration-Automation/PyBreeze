from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    AutomationMenu, HelpLink, build_automation_menu, package_run_actions, safe_create_project
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def set_web_runner_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(ui_we_want_to_set, AutomationMenu(
        label_key="web_runner_menu_label",
        run_actions=package_run_actions(ui_we_want_to_set, "web_runner", "je_web_runner"),
        help_links=(
            HelpLink("https://webrunner.readthedocs.io/en/latest/",
                     "web_runner_doc_label", "web_runner_doc_tab_label"),
            HelpLink("https://github.com/Integration-Automation/WebRunner",
                     "web_runner_github_label", "web_runner_github_tab_label"),
        ),
        create_project=safe_create_project(ui_we_want_to_set, "je_web_runner"),
        create_project_label_key="web_runner_create_project_label",
    ))

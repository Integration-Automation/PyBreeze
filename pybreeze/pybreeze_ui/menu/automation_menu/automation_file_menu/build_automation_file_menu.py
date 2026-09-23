from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    AutomationMenu, HelpLink, RunAction, build_automation_menu, safe_create_project
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

from pybreeze.extend.process_executor.file_automation.file_automation_process import (
    call_file_automation_test, call_file_automation_test_with_send,
    call_file_automation_test_multi_file, call_file_automation_test_multi_file_and_send,
)


def set_automation_file_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(ui_we_want_to_set, AutomationMenu(
        label_key="file_automation_menu_label",
        run_actions=(
            RunAction("file_automation_run_script_label",
                      lambda: call_file_automation_test(ui_we_want_to_set)),
            RunAction("file_automation_run_script_with_send_label",
                      lambda: call_file_automation_test_with_send(ui_we_want_to_set)),
            RunAction("file_automation_run_multi_script_label",
                      lambda: call_file_automation_test_multi_file(ui_we_want_to_set)),
            RunAction("file_automation_run_multi_script_with_send_label",
                      lambda: call_file_automation_test_multi_file_and_send(ui_we_want_to_set)),
        ),
        help_links=(
            HelpLink("https://fileautomation.readthedocs.io/en/latest/",
                     "file_automation_doc_label", "file_automation_doc_tab_label"),
            HelpLink("https://github.com/Integration-Automation/FileAutomation",
                     "file_automation_github_label", "file_automation_github_tab_label"),
        ),
        create_project=safe_create_project(ui_we_want_to_set, "automation_file"),
        create_project_label_key="file_automation_create_project_label",
    ))

from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    AutomationMenu, HelpLink, RunAction, build_automation_menu, safe_create_project
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

from pybreeze.extend.process_executor.web_runner.web_runner_process import (
    call_web_runner_test, call_web_runner_test_with_send,
    call_web_runner_test_multi_file, call_web_runner_test_multi_file_and_send,
)


def set_web_runner_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(ui_we_want_to_set, AutomationMenu(
        label_key="web_runner_menu_label",
        run_actions=(
            RunAction("web_runner_run_script_label",
                      lambda: call_web_runner_test(ui_we_want_to_set)),
            RunAction("web_runner_run_script_with_send_label",
                      lambda: call_web_runner_test_with_send(ui_we_want_to_set)),
            RunAction("web_runner_run_multi_script_label",
                      lambda: call_web_runner_test_multi_file(ui_we_want_to_set)),
            RunAction("web_runner_run_multi_script_with_send_label",
                      lambda: call_web_runner_test_multi_file_and_send(ui_we_want_to_set)),
        ),
        help_links=(
            HelpLink("https://webrunner.readthedocs.io/en/latest/",
                     "web_runner_doc_label", "web_runner_doc_tab_label"),
            HelpLink("https://github.com/Integration-Automation/WebRunner",
                     "web_runner_github_label", "web_runner_github_tab_label"),
        ),
        create_project=safe_create_project("je_web_runner"),
        create_project_label_key="web_runner_create_project_label",
    ))

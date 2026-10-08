from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.extend.process_executor.process_executor_utils import build_process
from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    AutomationMenu, HelpLink, RunAction, build_automation_menu, safe_create_project
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def set_mail_thunder_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(ui_we_want_to_set, AutomationMenu(
        label_key="mail_thunder_menu_label",
        run_actions=(
            RunAction("mail_thunder_run_script_label",
                      lambda: build_process(ui_we_want_to_set, "je_mail_thunder", send_mail=False)),
        ),
        help_links=(
            HelpLink("https://mailthunder.readthedocs.io/en/latest/",
                     "mail_thunder_doc_label", "mail_thunder_doc_tab_label"),
            HelpLink("https://github.com/Integration-Automation/MailThunder",
                     "mail_thunder_github_label", "mail_thunder_github_tab_label"),
        ),
        create_project=safe_create_project(ui_we_want_to_set, "je_mail_thunder"),
        create_project_label_key="mail_thunder_create_project_label",
    ))

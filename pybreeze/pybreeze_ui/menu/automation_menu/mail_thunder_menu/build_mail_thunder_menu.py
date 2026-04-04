from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    build_automation_menu, safe_create_project
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

from pybreeze.extend.process_executor.mail_thunder.mail_thunder_process import call_mail_thunder


def set_mail_thunder_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(
        ui=ui_we_want_to_set,
        menu_label_key="mail_thunder_menu_label",
        run_actions=[
            {"label_key": "mail_thunder_run_script_label",
             "callback": lambda: call_mail_thunder(ui_we_want_to_set)},
        ],
        doc_url="https://mailthunder.readthedocs.io/en/latest/",
        doc_label_key="mail_thunder_doc_label",
        doc_tab_label_key="mail_thunder_doc_tab_label",
        github_url="https://github.com/Integration-Automation/MailThunder",
        github_label_key="mail_thunder_github_label",
        github_tab_label_key="mail_thunder_github_tab_label",
        create_project_func=safe_create_project("je_mail_thunder"),
        create_project_label_key="mail_thunder_create_project_label",
    )

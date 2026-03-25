from __future__ import annotations

from typing import TYPE_CHECKING

from je_editor import language_wrapper

from pybreeze.pybreeze_ui.menu.menu_utils import open_web_browser

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow
import sys

from PySide6.QtGui import QAction

from pybreeze.extend.process_executor.mail_thunder.mail_thunder_process import call_mail_thunder


def set_mail_thunder_menu(ui_we_want_to_set: PyBreezeMainWindow):
    """
    Build menu include LoadDensity feature.
    :param ui_we_want_to_set: main window to add menu.
    :return: None
    """
    ui_we_want_to_set.mail_thunder_menu = ui_we_want_to_set.automation_menu.addMenu(
        language_wrapper.language_word_dict.get("mail_thunder_menu_label"))
    ui_we_want_to_set.mail_thunder_run_menu = ui_we_want_to_set.mail_thunder_menu.addMenu(
        language_wrapper.language_word_dict.get("run_label"))
    # Run MailThunder
    ui_we_want_to_set.run_mail_thunder_action = QAction(
        language_wrapper.language_word_dict.get("mail_thunder_run_script_label"))
    ui_we_want_to_set.run_mail_thunder_action.triggered.connect(
        lambda: call_mail_thunder(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.mail_thunder_run_menu.addAction(
        ui_we_want_to_set.run_mail_thunder_action
    )
    # Help menu
    ui_we_want_to_set.mail_thunder_help_menu = ui_we_want_to_set.mail_thunder_menu.addMenu(
        language_wrapper.language_word_dict.get("help_label"))
    # Open Doc
    ui_we_want_to_set.open_mail_thunder_doc_action = QAction(
        language_wrapper.language_word_dict.get("mail_thunder_doc_label"))
    ui_we_want_to_set.open_mail_thunder_doc_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://mailthunder.readthedocs.io/en/latest/",
            language_wrapper.language_word_dict.get("mail_thunder_doc_tab_label")
        )
    )
    ui_we_want_to_set.mail_thunder_help_menu.addAction(
        ui_we_want_to_set.open_mail_thunder_doc_action
    )
    # Open Github
    ui_we_want_to_set.open_mail_thunder_github_action = QAction(
        language_wrapper.language_word_dict.get("mail_thunder_github_label"))
    ui_we_want_to_set.open_mail_thunder_github_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://github.com/Integration-Automation/MailThunder",
            language_wrapper.language_word_dict.get("mail_thunder_github_tab_label")
        )
    )
    ui_we_want_to_set.mail_thunder_help_menu.addAction(
        ui_we_want_to_set.open_mail_thunder_github_action
    )
    ui_we_want_to_set.mail_thunder_project_menu = ui_we_want_to_set.mail_thunder_menu.addMenu(
        language_wrapper.language_word_dict.get("project_label"))
    # Create Project
    ui_we_want_to_set.create_mail_thunder_project_action = QAction(
        language_wrapper.language_word_dict.get("mail_thunder_create_project_label"))
    ui_we_want_to_set.create_mail_thunder_project_action.triggered.connect(
        create_project
    )
    ui_we_want_to_set.mail_thunder_project_menu.addAction(
        ui_we_want_to_set.create_mail_thunder_project_action
    )


def create_project() -> None:
    try:
        import je_mail_thunder
        package = je_mail_thunder
        if package is not None:
            package.create_project_dir()
    except ImportError as error:
        print(repr(error), file=sys.stderr)

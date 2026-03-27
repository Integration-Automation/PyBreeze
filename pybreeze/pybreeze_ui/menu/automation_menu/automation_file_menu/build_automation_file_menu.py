from __future__ import annotations

from typing import TYPE_CHECKING

from je_editor import language_wrapper

from pybreeze.pybreeze_ui.menu.menu_utils import open_web_browser

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow
import sys

from PySide6.QtGui import QAction

from pybreeze.extend.process_executor.file_automation.file_automation_process import call_file_automation_test, \
    call_file_automation_test_with_send, call_file_automation_test_multi_file, \
    call_file_automation_test_multi_file_and_send


def set_automation_file_menu(ui_we_want_to_set: PyBreezeMainWindow):
    """
    Build menu include WebRunner feature.
    :param ui_we_want_to_set: main window to add menu.
    :return: None
    """
    ui_we_want_to_set.automation_file_menu = ui_we_want_to_set.automation_menu.addMenu(
        language_wrapper.language_word_dict.get("file_automation_menu_label"))
    ui_we_want_to_set.automation_run_file_menu = ui_we_want_to_set.automation_file_menu.addMenu(
        language_wrapper.language_word_dict.get("run_label"))
    # Run FileAutomation Script
    ui_we_want_to_set.run_file_automation_action = QAction(
        language_wrapper.language_word_dict.get("file_automation_run_script_label"))
    ui_we_want_to_set.run_file_automation_action.triggered.connect(
        lambda: call_file_automation_test(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.automation_run_file_menu.addAction(ui_we_want_to_set.run_file_automation_action)
    # Run FileAutomation Script With Send
    ui_we_want_to_set.run_file_automation_action_with_send = QAction(
        language_wrapper.language_word_dict.get("file_automation_run_script_with_send_label"))
    ui_we_want_to_set.run_file_automation_action_with_send.triggered.connect(
        lambda: call_file_automation_test_with_send(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.automation_run_file_menu.addAction(
        ui_we_want_to_set.run_file_automation_action_with_send
    )
    # Run Multi FileAutomation Script
    ui_we_want_to_set.run_multi_file_automation_action = QAction(
        language_wrapper.language_word_dict.get("file_automation_run_multi_script_label"))
    ui_we_want_to_set.run_multi_file_automation_action.triggered.connect(
        lambda: call_file_automation_test_multi_file(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.automation_run_file_menu.addAction(
        ui_we_want_to_set.run_multi_file_automation_action
    )
    # Run Multi FileAutomation Script With Send
    ui_we_want_to_set.run_multi_file_automation_action_with_send = QAction(
        language_wrapper.language_word_dict.get("file_automation_run_multi_script_with_send_label"))
    ui_we_want_to_set.run_multi_file_automation_action_with_send.triggered.connect(
        lambda: call_file_automation_test_multi_file_and_send(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.automation_run_file_menu.addAction(
        ui_we_want_to_set.run_multi_file_automation_action_with_send
    )
    ui_we_want_to_set.file_automation_help_menu = ui_we_want_to_set.automation_file_menu.addMenu(
        language_wrapper.language_word_dict.get("help_label")
    )
    # Open Doc
    ui_we_want_to_set.open_file_automation_doc_action = QAction(
        language_wrapper.language_word_dict.get("file_automation_doc_label"))
    ui_we_want_to_set.open_file_automation_doc_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://fileautomation.readthedocs.io/en/latest/",
            language_wrapper.language_word_dict.get("file_automation_doc_tab_label")
        )
    )
    ui_we_want_to_set.file_automation_help_menu.addAction(
        ui_we_want_to_set.open_file_automation_doc_action
    )
    # Open Github
    ui_we_want_to_set.open_file_automation_github_action = QAction(
        language_wrapper.language_word_dict.get("file_automation_github_label"))
    ui_we_want_to_set.open_file_automation_github_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://github.com/Integration-Automation/FileAutomation",
            language_wrapper.language_word_dict.get("file_automation_github_tab_label")
        )
    )
    ui_we_want_to_set.file_automation_help_menu.addAction(
        ui_we_want_to_set.open_file_automation_github_action
    )
    ui_we_want_to_set.file_automation_project_menu = ui_we_want_to_set.automation_file_menu.addMenu(
        language_wrapper.language_word_dict.get("project_label")
    )
    # Create Project
    ui_we_want_to_set.create_web_runner_project_action = QAction(
        language_wrapper.language_word_dict.get("file_automation_create_project_label"))
    ui_we_want_to_set.create_web_runner_project_action.triggered.connect(
        create_project
    )
    ui_we_want_to_set.file_automation_project_menu.addAction(
        ui_we_want_to_set.create_web_runner_project_action
    )


def create_project() -> None:
    try:
        import file_automation
        package = file_automation
        if package is not None:
            package.create_project_dir()
    except ImportError as error:
        print(repr(error), file=sys.stderr)

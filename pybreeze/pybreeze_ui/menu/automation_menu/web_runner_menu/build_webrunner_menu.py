from __future__ import annotations

from typing import TYPE_CHECKING

from je_editor import language_wrapper

from pybreeze.pybreeze_ui.menu.menu_utils import open_web_browser

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import AutomationEditor
import sys

from PySide6.QtGui import QAction

from pybreeze.extend.process_executor.web_runner.web_runner_process import call_web_runner_test, \
    call_web_runner_test_with_send, call_web_runner_test_multi_file, call_web_runner_test_multi_file_and_send


def set_web_runner_menu(ui_we_want_to_set: AutomationEditor):
    """
    Build menu include WebRunner feature.
    :param ui_we_want_to_set: main window to add menu.
    :return: None
    """
    ui_we_want_to_set.web_runner_menu = ui_we_want_to_set.automation_menu.addMenu(
        language_wrapper.language_word_dict.get("web_runner_menu_label"))
    ui_we_want_to_set.web_runner_run_menu = ui_we_want_to_set.web_runner_menu.addMenu(
        language_wrapper.language_word_dict.get("web_runner_menu_label"))
    # Run WEBRunner Script
    ui_we_want_to_set.run_web_runner_action = QAction(
        language_wrapper.language_word_dict.get("web_runner_run_script_label"))
    ui_we_want_to_set.run_web_runner_action.triggered.connect(
        lambda: call_web_runner_test(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.web_runner_run_menu.addAction(ui_we_want_to_set.run_web_runner_action)
    # Run WEBRunner Script With Send
    ui_we_want_to_set.run_web_runner_action_with_send = QAction(
        language_wrapper.language_word_dict.get("web_runner_run_script_with_send_label"))
    ui_we_want_to_set.run_web_runner_action_with_send.triggered.connect(
        lambda: call_web_runner_test_with_send(
            ui_we_want_to_set
        )
    )
    ui_we_want_to_set.web_runner_run_menu.addAction(
        ui_we_want_to_set.run_web_runner_action_with_send
    )
    # Run Multi WEBRunner Script
    ui_we_want_to_set.run_multi_web_runner_action = QAction(
        language_wrapper.language_word_dict.get("web_runner_run_multi_script_label"))
    ui_we_want_to_set.run_multi_web_runner_action.triggered.connect(
        lambda: call_web_runner_test_multi_file(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.web_runner_run_menu.addAction(
        ui_we_want_to_set.run_multi_web_runner_action
    )
    # Run Multi WEBRunner Script With Send
    ui_we_want_to_set.run_multi_web_runner_action_with_send = QAction(
        language_wrapper.language_word_dict.get("web_runner_run_multi_script_with_send_label"))
    ui_we_want_to_set.run_multi_web_runner_action_with_send.triggered.connect(
        lambda: call_web_runner_test_multi_file_and_send(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.web_runner_run_menu.addAction(
        ui_we_want_to_set.run_multi_web_runner_action_with_send
    )
    ui_we_want_to_set.web_runner_help_menu = ui_we_want_to_set.web_runner_menu.addMenu(
        language_wrapper.language_word_dict.get("help_label"))
    # Open Doc
    ui_we_want_to_set.open_web_runner_doc_action = QAction(
        language_wrapper.language_word_dict.get("web_runner_doc_label"))
    ui_we_want_to_set.open_web_runner_doc_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://webrunner.readthedocs.io/en/latest/",
            language_wrapper.language_word_dict.get("web_runner_doc_tab_label")
        )
    )
    ui_we_want_to_set.web_runner_help_menu.addAction(
        ui_we_want_to_set.open_web_runner_doc_action
    )
    # Open Github
    ui_we_want_to_set.open_web_runner_github_action = QAction(
        language_wrapper.language_word_dict.get("web_runner_github_label"))
    ui_we_want_to_set.open_web_runner_github_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://github.com/Intergration-Automation-Testing/WebRunner",
            language_wrapper.language_word_dict.get("web_runner_github_tab_label")
        )
    )
    ui_we_want_to_set.web_runner_help_menu.addAction(
        ui_we_want_to_set.open_web_runner_github_action
    )
    ui_we_want_to_set.web_runner_project_menu = ui_we_want_to_set.web_runner_menu.addMenu(
        language_wrapper.language_word_dict.get("project_label"))
    # Create Project
    ui_we_want_to_set.create_web_runner_project_action = QAction(
        language_wrapper.language_word_dict.get("web_runner_create_project_label"))
    ui_we_want_to_set.create_web_runner_project_action.triggered.connect(
        create_project
    )
    ui_we_want_to_set.web_runner_project_menu.addAction(
        ui_we_want_to_set.create_web_runner_project_action
    )


def create_project() -> None:
    try:
        import je_web_runner
        package = je_web_runner
        if package is not None:
            package.create_project_dir()
    except ImportError as error:
        print(repr(error), file=sys.stderr)

from __future__ import annotations

from typing import TYPE_CHECKING

from je_api_testka.gui.main_widget import APITestkaWidget
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.menu.menu_utils import open_web_browser

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import AutomationEditor
import sys

from PySide6.QtGui import QAction

from pybreeze.extend.process_executor.api_testka.api_testka_process import call_api_testka, \
    call_api_testka_with_send, call_api_testka_multi_file, call_api_testka_multi_file_and_send


def set_apitestka_menu(ui_we_want_to_set: AutomationEditor):
    """
    Build menu include APITestka feature.
    :param ui_we_want_to_set: main window to add menu.
    :return: None
    """
    ui_we_want_to_set.apitestka_menu = ui_we_want_to_set.automation_menu.addMenu(
        language_wrapper.language_word_dict.get("apitestka_menu_label")
    )
    ui_we_want_to_set.apitestka_run_menu = ui_we_want_to_set.apitestka_menu.addMenu(
        language_wrapper.language_word_dict.get("run_label"))
    # Run APITestka Script
    ui_we_want_to_set.run_apitestka_action = QAction(
        language_wrapper.language_word_dict.get("apitestka_run_script_label"))
    ui_we_want_to_set.run_apitestka_action.triggered.connect(
        lambda: call_api_testka(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.apitestka_run_menu.addAction(ui_we_want_to_set.run_apitestka_action)
    # Run APITestka Script With Send
    ui_we_want_to_set.run_apitestka_action_with_send = QAction(
        language_wrapper.language_word_dict.get("apitestka_run_script_with_send_label"))
    ui_we_want_to_set.run_apitestka_action_with_send.triggered.connect(
        lambda: call_api_testka_with_send(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.apitestka_run_menu.addAction(
        ui_we_want_to_set.run_apitestka_action_with_send
    )
    # Run Multi APITestka Script
    ui_we_want_to_set.run_multi_apitestka_action = QAction(
        language_wrapper.language_word_dict.get("apitestka_run_multi_script_label"))
    ui_we_want_to_set.run_multi_apitestka_action.triggered.connect(
        lambda: call_api_testka_multi_file(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.apitestka_run_menu.addAction(
        ui_we_want_to_set.run_multi_apitestka_action
    )
    # Run Multi APITestka Script With Send
    ui_we_want_to_set.run_multi_apitestka_action_with_send = QAction(
        language_wrapper.language_word_dict.get("apitestka_run_multi_script_with_send_label"))
    ui_we_want_to_set.run_multi_apitestka_action_with_send.triggered.connect(
        lambda: call_api_testka_multi_file_and_send(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.apitestka_run_menu.addAction(
        ui_we_want_to_set.run_multi_apitestka_action_with_send
    )
    ui_we_want_to_set.apitestka_help_menu = ui_we_want_to_set.apitestka_menu.addMenu(
        language_wrapper.language_word_dict.get("help_label"))
    # Open Doc
    ui_we_want_to_set.open_apitestka_doc_action = QAction(
        language_wrapper.language_word_dict.get("apitestka_doc_label"))
    ui_we_want_to_set.open_apitestka_doc_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://apitestka.readthedocs.io/en/latest/",
            language_wrapper.language_word_dict.get("apitestka_doc_tab_label")
        )
    )
    ui_we_want_to_set.apitestka_help_menu.addAction(
        ui_we_want_to_set.open_apitestka_doc_action
    )
    # Open Github
    ui_we_want_to_set.open_apitestka_github_action = QAction(
        language_wrapper.language_word_dict.get("apitestka_github_label"))
    ui_we_want_to_set.open_apitestka_github_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://github.com/Intergration-Automation-Testing/APITestka",
            language_wrapper.language_word_dict.get("apitestka_github_tab_label")
        )
    )
    ui_we_want_to_set.apitestka_help_menu.addAction(
        ui_we_want_to_set.open_apitestka_github_action
    )
    ui_we_want_to_set.apitestka_project_menu = ui_we_want_to_set.apitestka_menu.addMenu(
        language_wrapper.language_word_dict.get("project_label"))
    # Create Project
    ui_we_want_to_set.create_apitestka_project_action = QAction(
        language_wrapper.language_word_dict.get("apitestka_create_project_label"))
    ui_we_want_to_set.create_apitestka_project_action.triggered.connect(
        create_project
    )
    ui_we_want_to_set.apitestka_project_menu.addAction(
        ui_we_want_to_set.create_apitestka_project_action
    )
    # APITestka GUI
    ui_we_want_to_set.api_testka_gui_action = QAction(
        "APITestka GUI"
    )
    ui_we_want_to_set.api_testka_gui_action.triggered.connect(
        lambda: add_api_testka_gui(ui_we_want_to_set)
    )
    ui_we_want_to_set.apitestka_menu.addAction(
        ui_we_want_to_set.api_testka_gui_action
    )


def create_project() -> None:
    try:
        import je_api_testka
        package = je_api_testka
        if package is not None:
            package.create_project_dir()
    except ImportError as error:
        print(repr(error), file=sys.stderr)


def add_api_testka_gui(ui_we_want_to_set: AutomationEditor) -> None:
    ui_we_want_to_set.tab_widget.addTab(
        APITestkaWidget(), "APITestka GUI"
    )

from __future__ import annotations

from typing import TYPE_CHECKING

from je_editor import language_wrapper
from je_load_density.gui.main_widget import LoadDensityWidget

from pybreeze.pybreeze_ui.menu.menu_utils import open_web_browser

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import AutomationEditor
import sys

from PySide6.QtGui import QAction

from pybreeze.extend.process_executor.load_density.load_density_process import \
    call_load_density, call_load_density_with_send, call_load_density_multi_file, \
    call_load_density_multi_file_and_send


def set_load_density_menu(ui_we_want_to_set: AutomationEditor):
    """
    Build menu include LoadDensity feature.
    :param ui_we_want_to_set: main window to add menu.
    :return: None
    """
    ui_we_want_to_set.load_density_menu = ui_we_want_to_set.automation_menu.addMenu(
        language_wrapper.language_word_dict.get("load_density_menu_label"))
    ui_we_want_to_set.load_density_run_menu = ui_we_want_to_set.load_density_menu.addMenu(
        language_wrapper.language_word_dict.get("run_label"))
    # Run LoadDensity Script
    ui_we_want_to_set.run_load_density_action = QAction(
        language_wrapper.language_word_dict.get("load_density_run_script_label"))
    ui_we_want_to_set.run_load_density_action.triggered.connect(
        lambda: call_load_density(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.load_density_run_menu.addAction(ui_we_want_to_set.run_load_density_action)
    # Run LoadDensity Script With Send
    ui_we_want_to_set.run_load_density_action_with_send = QAction(
        language_wrapper.language_word_dict.get("load_density_run_script_with_send_label"))
    ui_we_want_to_set.run_load_density_action_with_send.triggered.connect(
        lambda: call_load_density_with_send(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.load_density_run_menu.addAction(
        ui_we_want_to_set.run_load_density_action_with_send
    )
    # Run Multi LoadDensity Script
    ui_we_want_to_set.run_multi_load_density_action = QAction(
        language_wrapper.language_word_dict.get("load_density_run_multi_script_label"))
    ui_we_want_to_set.run_multi_load_density_action.triggered.connect(
        lambda: call_load_density_multi_file(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.load_density_run_menu.addAction(
        ui_we_want_to_set.run_multi_load_density_action
    )
    # Run Multi LoadDensity Script With Send
    ui_we_want_to_set.run_multi_load_density_action_with_send = QAction(
        language_wrapper.language_word_dict.get("load_density_run_multi_script_with_send_label"))
    ui_we_want_to_set.run_multi_load_density_action_with_send.triggered.connect(
        lambda: call_load_density_multi_file_and_send(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.load_density_run_menu.addAction(
        ui_we_want_to_set.run_multi_load_density_action_with_send
    )
    ui_we_want_to_set.load_density_help_menu = ui_we_want_to_set.load_density_menu.addMenu(
        language_wrapper.language_word_dict.get("help_label"))
    # Open Doc
    ui_we_want_to_set.open_load_density_doc_action = QAction(
        language_wrapper.language_word_dict.get("load_density_doc_label"))
    ui_we_want_to_set.open_load_density_doc_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://loaddensity.readthedocs.io/en/latest/",
            language_wrapper.language_word_dict.get("load_density_doc_tab_label")
        )
    )
    ui_we_want_to_set.load_density_help_menu.addAction(
        ui_we_want_to_set.open_load_density_doc_action
    )
    # Open Github
    ui_we_want_to_set.open_load_density_github_action = QAction(
        language_wrapper.language_word_dict.get("load_density_github_label"))
    ui_we_want_to_set.open_load_density_github_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://github.com/Intergration-Automation-Testing/LoadDensity",
            language_wrapper.language_word_dict.get("load_density_github_tab_label")
        )
    )
    ui_we_want_to_set.load_density_help_menu.addAction(
        ui_we_want_to_set.open_load_density_github_action
    )
    ui_we_want_to_set.load_density_project_menu = ui_we_want_to_set.load_density_menu.addMenu(
        language_wrapper.language_word_dict.get("project_label"))
    # Create Project
    ui_we_want_to_set.create_load_density_project_action = QAction(
        language_wrapper.language_word_dict.get("load_density_create_project_label"))
    ui_we_want_to_set.create_load_density_project_action.triggered.connect(
        create_project
    )
    ui_we_want_to_set.load_density_project_menu.addAction(
        ui_we_want_to_set.create_load_density_project_action
    )
    #  AutoControl GUI
    ui_we_want_to_set.load_density_gui_action = QAction(
        "LoadDensity GUI"
    )
    ui_we_want_to_set.load_density_gui_action.triggered.connect(
        lambda: add_load_density_gui(ui_we_want_to_set)
    )
    ui_we_want_to_set.load_density_menu.addAction(
        ui_we_want_to_set.load_density_gui_action
    )


def create_project() -> None:
    try:
        import je_load_density
        package = je_load_density
        if package is not None:
            package.create_project_dir()
    except ImportError as error:
        print(repr(error), file=sys.stderr)


def add_load_density_gui(ui_we_want_to_set: AutomationEditor) -> None:
    ui_we_want_to_set.tab_widget.addTab(
        LoadDensityWidget(), "LoadDensity GUI"
    )

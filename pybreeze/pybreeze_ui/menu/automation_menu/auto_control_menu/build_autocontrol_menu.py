from __future__ import annotations

from typing import TYPE_CHECKING

from je_auto_control.gui.main_widget import AutoControlGUIWidget
from je_editor import EditorWidget, language_wrapper
from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict

from pybreeze.pybreeze_ui.menu.menu_utils import open_web_browser

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import AutomationEditor
import sys

import je_auto_control
from PySide6.QtGui import QAction, QTextCharFormat

from pybreeze.extend.process_executor.auto_control.auto_control_process import \
    call_auto_control, call_auto_control_with_send, call_auto_control_multi_file, \
    call_auto_control_multi_file_and_send


def set_autocontrol_menu(ui_we_want_to_set: AutomationEditor):
    """
    Build menu include AutoControl feature.
    :param ui_we_want_to_set: main window to add menu.
    :return: None
    """
    ui_we_want_to_set.autocontrol_menu = ui_we_want_to_set.automation_menu.addMenu(
        language_wrapper.language_word_dict.get("autocontrol_menu_label"))
    ui_we_want_to_set.autocontrol_run_menu = ui_we_want_to_set.autocontrol_menu.addMenu(
        language_wrapper.language_word_dict.get("run_label"))
    # Run AutoControl Script
    ui_we_want_to_set.run_autocontrol_action = QAction(
        language_wrapper.language_word_dict.get("autocontrol_run_script_label"))
    ui_we_want_to_set.run_autocontrol_action.triggered.connect(
        lambda: call_auto_control(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.autocontrol_run_menu.addAction(ui_we_want_to_set.run_autocontrol_action)
    # Run AutoControl Script With Send
    ui_we_want_to_set.run_autocontrol_action_with_send = QAction(
        language_wrapper.language_word_dict.get("autocontrol_run_script_with_send_label"))
    ui_we_want_to_set.run_autocontrol_action_with_send.triggered.connect(
        lambda: call_auto_control_with_send(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.autocontrol_run_menu.addAction(
        ui_we_want_to_set.run_autocontrol_action_with_send
    )
    # Run Multi AutoControl Script
    ui_we_want_to_set.run_multi_autocontrol_action = QAction(
        language_wrapper.language_word_dict.get("autocontrol_run_multi_script_label"))
    ui_we_want_to_set.run_multi_autocontrol_action.triggered.connect(
        lambda: call_auto_control_multi_file(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.autocontrol_run_menu.addAction(
        ui_we_want_to_set.run_multi_autocontrol_action
    )
    # Run Multi AutoControl Script With Send
    ui_we_want_to_set.run_multi_autocontrol_action_with_send = QAction(
        language_wrapper.language_word_dict.get("autocontrol_run_multi_script_with_send_label")
    )
    ui_we_want_to_set.run_multi_autocontrol_action_with_send.triggered.connect(
        lambda: call_auto_control_multi_file_and_send(
            ui_we_want_to_set,
        )
    )
    ui_we_want_to_set.autocontrol_run_menu.addAction(
        ui_we_want_to_set.run_multi_autocontrol_action_with_send
    )
    ui_we_want_to_set.autocontrol_help_menu = ui_we_want_to_set.autocontrol_menu.addMenu(
        language_wrapper.language_word_dict.get("help_label"))
    # Open Doc
    ui_we_want_to_set.open_autocontrol_doc_action = QAction(
        language_wrapper.language_word_dict.get("autocontrol_doc_label"))
    ui_we_want_to_set.open_autocontrol_doc_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://autocontrol.readthedocs.io/en/latest/",
            language_wrapper.language_word_dict.get("autocontrol_doc_tab_label")
        )
    )
    ui_we_want_to_set.autocontrol_help_menu.addAction(
        ui_we_want_to_set.open_autocontrol_doc_action
    )
    # Open Github
    ui_we_want_to_set.open_autocontrol_github_action = QAction(
        language_wrapper.language_word_dict.get("autocontrol_github_label"))
    ui_we_want_to_set.open_autocontrol_github_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set,
            "https://github.com/Intergration-Automation-Testing/AutoControl",
            language_wrapper.language_word_dict.get("autocontrol_github_tab_label")
        )
    )
    ui_we_want_to_set.autocontrol_help_menu.addAction(
        ui_we_want_to_set.open_autocontrol_github_action
    )
    ui_we_want_to_set.autocontrol_project_menu = ui_we_want_to_set.autocontrol_menu.addMenu(
        language_wrapper.language_word_dict.get("project_label"))
    # Create Project
    ui_we_want_to_set.create_autocontrol_project_action = QAction(
        language_wrapper.language_word_dict.get("autocontrol_create_project_label"))
    ui_we_want_to_set.create_autocontrol_project_action.triggered.connect(
        create_project
    )
    ui_we_want_to_set.autocontrol_project_menu.addAction(
        ui_we_want_to_set.create_autocontrol_project_action
    )
    # Record
    ui_we_want_to_set.autocontrol_record_menu = ui_we_want_to_set.autocontrol_menu.addMenu(
        language_wrapper.language_word_dict.get("autocontrol_record_menu_label"))
    ui_we_want_to_set.record_action = QAction(
        language_wrapper.language_word_dict.get("autocontrol_record_start_label"))
    ui_we_want_to_set.record_action.triggered.connect(
        je_auto_control.record
    )
    ui_we_want_to_set.autocontrol_record_menu.addAction(
        ui_we_want_to_set.record_action
    )
    # Stop Record
    ui_we_want_to_set.stop_record_action = QAction(
        language_wrapper.language_word_dict.get("autocontrol_record_stop_label"))
    ui_we_want_to_set.stop_record_action.triggered.connect(
        lambda: stop_record(ui_we_want_to_set)
    )
    ui_we_want_to_set.autocontrol_record_menu.addAction(
        ui_we_want_to_set.stop_record_action
    )
    #  AutoControl GUI
    ui_we_want_to_set.autocontrol_gui_action = QAction(
        "AutoControl GUI"
    )
    ui_we_want_to_set.autocontrol_gui_action.triggered.connect(
        lambda: add_autocontrol_gui(ui_we_want_to_set)
    )
    ui_we_want_to_set.autocontrol_menu.addAction(
        ui_we_want_to_set.autocontrol_gui_action
    )


def create_project() -> None:
    try:
        package = je_auto_control
        if package is not None:
            package.create_project_dir()
    except ImportError as error:
        print(repr(error), file=sys.stderr)


def stop_record(editor_instance: AutomationEditor):
    widget = editor_instance.tab_widget.currentWidget()
    if isinstance(widget, EditorWidget):
        text_cursor = widget.code_edit.textCursor()
        text_format = QTextCharFormat()
        text_format.setForeground(actually_color_dict.get("normal_output_color"))
        text_cursor.insertText(str(je_auto_control.stop_record()), text_format)
        text_cursor.insertBlock()


def add_autocontrol_gui(ui_we_want_to_set: AutomationEditor) -> None:
    ui_we_want_to_set.tab_widget.addTab(
        AutoControlGUIWidget(), "AutoControl GUI"
    )

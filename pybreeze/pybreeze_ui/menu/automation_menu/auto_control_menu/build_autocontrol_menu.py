from __future__ import annotations

from typing import TYPE_CHECKING

import je_auto_control
from PySide6.QtGui import QAction, QTextCharFormat
from je_auto_control.gui.main_widget import AutoControlGUIWidget
from je_editor import EditorWidget, language_wrapper
from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    build_automation_menu, safe_create_project
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

from pybreeze.extend.process_executor.auto_control.auto_control_process import (
    call_auto_control, call_auto_control_with_send,
    call_auto_control_multi_file, call_auto_control_multi_file_and_send,
)


def set_autocontrol_menu(ui_we_want_to_set: PyBreezeMainWindow):
    menu = build_automation_menu(
        ui=ui_we_want_to_set,
        menu_label_key="autocontrol_menu_label",
        run_actions=[
            {"label_key": "autocontrol_run_script_label",
             "callback": lambda: call_auto_control(ui_we_want_to_set)},
            {"label_key": "autocontrol_run_script_with_send_label",
             "callback": lambda: call_auto_control_with_send(ui_we_want_to_set)},
            {"label_key": "autocontrol_run_multi_script_label",
             "callback": lambda: call_auto_control_multi_file(ui_we_want_to_set)},
            {"label_key": "autocontrol_run_multi_script_with_send_label",
             "callback": lambda: call_auto_control_multi_file_and_send(ui_we_want_to_set)},
        ],
        doc_url="https://autocontrol.readthedocs.io/en/latest/",
        doc_label_key="autocontrol_doc_label",
        doc_tab_label_key="autocontrol_doc_tab_label",
        github_url="https://github.com/Intergration-Automation-Testing/AutoControl",
        github_label_key="autocontrol_github_label",
        github_tab_label_key="autocontrol_github_tab_label",
        create_project_func=safe_create_project("je_auto_control"),
        create_project_label_key="autocontrol_create_project_label",
        gui_widget_class=AutoControlGUIWidget,
        gui_label="AutoControl GUI",
    )

    # AutoControl-specific: Record menu
    lang = language_wrapper.language_word_dict
    record_menu = menu.addMenu(lang.get("autocontrol_record_menu_label"))

    record_action = QAction(lang.get("autocontrol_record_start_label"))
    record_action.triggered.connect(je_auto_control.record)
    record_menu.addAction(record_action)

    stop_record_action = QAction(lang.get("autocontrol_record_stop_label"))
    stop_record_action.triggered.connect(lambda: stop_record(ui_we_want_to_set))
    record_menu.addAction(stop_record_action)


def stop_record(editor_instance: PyBreezeMainWindow):
    widget = editor_instance.tab_widget.currentWidget()
    if isinstance(widget, EditorWidget):
        text_cursor = widget.code_edit.textCursor()
        text_format = QTextCharFormat()
        text_format.setForeground(actually_color_dict.get("normal_output_color"))
        text_cursor.insertText(str(je_auto_control.stop_record()), text_format)
        text_cursor.insertBlock()

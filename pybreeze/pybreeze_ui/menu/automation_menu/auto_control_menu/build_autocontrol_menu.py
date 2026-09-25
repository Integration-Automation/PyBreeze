from __future__ import annotations

import json
from types import ModuleType
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QGuiApplication, QTextCharFormat
from PySide6.QtWidgets import QMessageBox, QWidget
from je_editor import EditorWidget, language_wrapper
from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    AutomationMenu, HelpLink, RunAction, build_automation_menu, safe_create_project
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

from pybreeze.extend.process_executor.auto_control.auto_control_process import (
    call_auto_control, call_auto_control_with_send,
    call_auto_control_multi_file, call_auto_control_multi_file_and_send,
)


def _auto_control() -> ModuleType:
    """The ``je_auto_control`` package, imported the first time it is used.

    It makes the process system DPI aware as it imports. Imported with the
    menus, before the application existed, it kept Qt from making the IDE
    per-monitor aware, and Windows stretched the window as a bitmap on a screen
    scaled differently from the main one.
    """
    import je_auto_control
    return je_auto_control


def _autocontrol_gui() -> QWidget:
    from je_auto_control.gui.main_widget import AutoControlGUIWidget
    return AutoControlGUIWidget()


def _start_recording() -> None:
    _auto_control().record()


def set_autocontrol_menu(ui_we_want_to_set: PyBreezeMainWindow):
    menu = build_automation_menu(ui_we_want_to_set, AutomationMenu(
        label_key="autocontrol_menu_label",
        run_actions=(
            RunAction("autocontrol_run_script_label", lambda: call_auto_control(ui_we_want_to_set)),
            RunAction("autocontrol_run_script_with_send_label",
                      lambda: call_auto_control_with_send(ui_we_want_to_set)),
            RunAction("autocontrol_run_multi_script_label",
                      lambda: call_auto_control_multi_file(ui_we_want_to_set)),
            RunAction("autocontrol_run_multi_script_with_send_label",
                      lambda: call_auto_control_multi_file_and_send(ui_we_want_to_set)),
        ),
        help_links=(
            HelpLink("https://autocontrol.readthedocs.io/en/latest/",
                     "autocontrol_doc_label", "autocontrol_doc_tab_label"),
            HelpLink("https://github.com/Integration-Automation/AutoControlGUI",
                     "autocontrol_github_label", "autocontrol_github_tab_label"),
        ),
        create_project=safe_create_project(ui_we_want_to_set, "je_auto_control"),
        create_project_label_key="autocontrol_create_project_label",
        gui_widget_factory=_autocontrol_gui,
        gui_label="AutoControl GUI",
    ))

    # AutoControl-specific: Record menu
    lang = language_wrapper.language_word_dict
    record_menu = menu.addMenu(lang.get("autocontrol_record_menu_label"))

    record_action = QAction(lang.get("autocontrol_record_start_label"), record_menu)
    record_action.triggered.connect(_start_recording)
    record_menu.addAction(record_action)

    stop_record_action = QAction(lang.get("autocontrol_record_stop_label"), record_menu)
    stop_record_action.triggered.connect(lambda: stop_record(ui_we_want_to_set))
    record_menu.addAction(stop_record_action)


def stop_record(editor_instance: PyBreezeMainWindow) -> None:
    """Stop recording and put the recorded actions where they can be run.

    Recording stops whatever tab is in front: it used to stop only from an
    editor tab, and from any other the keyboard and mouse hooks kept recording.
    The actions go in as the JSON the AutoControl runner reads (they went in as
    a Python repr, which it cannot), at the cursor of the editor tab in front,
    or on the clipboard when there is none. When nothing was recorded -- or
    recording was never started -- the user is told, instead of getting "None".
    """
    actions = _auto_control().stop_record()
    lang = language_wrapper.language_word_dict
    title = lang.get("autocontrol_record_menu_label")
    if not actions:
        QMessageBox.information(editor_instance, title, lang.get("autocontrol_record_nothing"))
        return
    script = json.dumps(actions)
    widget = editor_instance.tab_widget.currentWidget()
    if not isinstance(widget, EditorWidget):
        QGuiApplication.clipboard().setText(script)
        QMessageBox.information(editor_instance, title, lang.get("autocontrol_record_copied"))
        return
    text_cursor = widget.code_edit.textCursor()
    text_format = QTextCharFormat()
    text_format.setForeground(actually_color_dict.get("normal_output_color"))
    text_cursor.insertText(script, text_format)
    text_cursor.insertBlock()

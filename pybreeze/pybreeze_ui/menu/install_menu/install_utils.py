from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox
from je_editor import EditorWidget, ShellManager, language_wrapper

from pybreeze.utils.logging.logger import pybreeze_logger

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def install_package(package_text: str, ui_we_want_to_set: PyBreezeMainWindow) -> bool:
    """Install *package_text* with pip, in the current editor tab's shell panel.

    pip runs with the interpreter chosen in the IDE, falling back to the one the
    shell finds. An editor tab has to be in front: its panel is where the output
    goes, so without one the install is not started and the user is told why
    rather than left with a menu entry that does nothing.

    :param package_text: what pip is asked to install (a name, or a path with extras)
    :param ui_we_want_to_set: the main window
    :return: whether the install started
    """
    widget = ui_we_want_to_set.tab_widget.currentWidget()
    if not isinstance(widget, EditorWidget):
        pybreeze_logger.error("install needs an editor tab in front, not %r", type(widget).__name__)
        messagebox = QMessageBox(ui_we_want_to_set)
        messagebox.setWindowTitle(
            language_wrapper.language_word_dict.get("install_menu_label"))
        messagebox.setText(
            language_wrapper.language_word_dict.get("install_need_editor_tab_message"))
        messagebox.exec()
        return False
    widget.python_compiler = ui_we_want_to_set.python_compiler
    shell_manager = ShellManager(main_window=widget)
    shell_manager.later_init()
    if widget.python_compiler is not None:
        compiler_path = widget.python_compiler
    else:
        compiler_path = shell_manager.compiler_path
    shell_manager.exec_shell([f"{compiler_path}", "-m", "pip", "install", f"{package_text}", "-U"])
    return True

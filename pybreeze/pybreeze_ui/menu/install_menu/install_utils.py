from __future__ import annotations

from typing import TYPE_CHECKING

from je_editor import EditorWidget, ShellManager

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def install_package(package_text: str, ui_we_want_to_set: PyBreezeMainWindow) -> None:
    widget = ui_we_want_to_set.tab_widget.currentWidget()
    if isinstance(widget, EditorWidget):
        widget.python_compiler = ui_we_want_to_set.python_compiler
        shell_manager = ShellManager(main_window=widget)
        shell_manager.later_init()
        if widget.python_compiler is not None:
            compiler_path = widget.python_compiler
        else:
            compiler_path = shell_manager.compiler_path
        shell_manager.exec_shell([f"{compiler_path}", "-m", "pip", "install", f"{package_text}", "-U"])

"""
"Run with..." menu — lets users run the current file with a plugin-registered runner.

Uses je_editor's plugin run config registry instead of scanning sys.modules.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox

from je_editor import language_wrapper
from je_editor.plugins import get_all_plugin_run_configs
from je_editor.pyside_ui.main_ui.editor.editor_widget import EditorWidget
from je_editor.utils.file.save.save_file import write_file

from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def _get_current_file(main_window: PyBreezeMainWindow) -> str | None:
    """Get and save the current editor file, return its path or None."""
    widget = main_window.tab_widget.currentWidget()
    if not isinstance(widget, EditorWidget):
        return None

    # If file already saved, just write current content
    if widget.current_file:
        write_file(widget.current_file, widget.code_edit.toPlainText())
        return widget.current_file

    # No file yet — ask user to save first
    from je_editor.pyside_ui.dialog.file_dialog.save_file_dialog import choose_file_get_save_file_path
    if choose_file_get_save_file_path(main_window):
        return widget.current_file
    return None


def _run_with(main_window: PyBreezeMainWindow, run_config: dict) -> None:
    """Execute the current file using the given run config."""
    file_path = _get_current_file(main_window)
    if not file_path:
        return

    # Check suffix match
    suffix = Path(file_path).suffix.lower()
    supported = run_config.get("suffixes", ())
    if supported and suffix not in supported:
        msg = QMessageBox(main_window)
        msg.setWindowTitle(language_wrapper.language_word_dict.get("run_with_menu_label"))
        msg.setText(
            language_wrapper.language_word_dict.get("run_with_suffix_mismatch").format(
                suffix=suffix,
                expected=", ".join(supported),
            )
        )
        msg.exec()
        return

    code_window = CodeWindow()
    code_window.setWindowTitle(f"{run_config['name']} - {Path(file_path).name}")
    main_window.current_run_code_window.append(code_window)

    runner = FileRunnerProcess(
        main_window=code_window,
        program_encoding=main_window.encoding,
    )
    runner.run_file(run_config, file_path)


def set_run_with_menu(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """Build the 'Run with...' submenu. Only creates if configs exist."""
    configs = get_all_plugin_run_configs()
    if not configs:
        return

    # 依名稱排序 / Sort by name
    configs = sorted(configs, key=lambda c: c.get("name", ""))

    ui_we_want_to_set.run_with_menu = ui_we_want_to_set.run_menu.addMenu(
        language_wrapper.language_word_dict.get("run_with_menu_label")
    )

    for config in configs:
        name = config.get("name", "Unknown")
        suffixes = ", ".join(config.get("suffixes", ()))
        label = f"{name}  ({suffixes})" if suffixes else name

        action = QAction(label, ui_we_want_to_set.run_with_menu)
        action.triggered.connect(
            lambda checked=False, cfg=config: _run_with(ui_we_want_to_set, cfg)
        )
        ui_we_want_to_set.run_with_menu.addAction(action)

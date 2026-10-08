"""Reusable copy / open-in-editor / save-to-file actions for a tool's output.

Several tools produce a block of generated text (code, JSON, a diff). This helper
gives them a consistent row of actions — copy to clipboard, open in a new editor
tab, save to a file — without each tool re-implementing the same logic.

Attach one to a tool by creating an :class:`OutputActions` bound to the tool's
read-only output ``QTextEdit`` and adding its button row to the layout.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QTextEdit, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.exact_text import exact_text
from pybreeze.utils.file_process.replace_file import replace_text
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.pybreeze_ui.plain_text import as_text

# A value that is either fixed or computed on demand (e.g. depends on a selector)
StrOrCallable = str | Callable[[], str]


def _resolve(value: StrOrCallable) -> str:
    """Return *value*, calling it first if it is a callable."""
    return value() if callable(value) else value


class OutputActions:
    """Copy / open-in-editor / save-to-file actions bound to an output widget."""

    def __init__(
            self, parent: QWidget, output_edit: QTextEdit, *,
            main_window=None,
            basename: StrOrCallable = "output",
            extension: StrOrCallable = "txt",
            is_valid: Callable[[], bool] | None = None) -> None:
        """
        :param parent: the tool widget the file dialog is parented to
        :param output_edit: the read-only output the actions operate on
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        :param basename: default file basename (a str, or a callable returning one)
        :param extension: file extension without the dot (str or callable)
        :param is_valid: optional predicate; when it returns ``False`` the
            open/save actions are no-ops (used to avoid saving an error message)
        """
        self._parent = parent
        self._output = output_edit
        self._main_window = main_window
        self._basename = basename
        self._extension = extension
        self._is_valid = is_valid
        word = language_wrapper.language_word_dict

        self.copy_button = QPushButton(word.get("output_actions_copy"))
        self.copy_button.clicked.connect(self.copy)
        self.open_button = QPushButton(word.get("output_actions_open_editor"))
        self.open_button.clicked.connect(self.open_in_editor)
        self.save_button = QPushButton(word.get("output_actions_save"))
        self.save_button.clicked.connect(self.save_to_file)

    def button_row(self) -> QHBoxLayout:
        """Return a horizontal layout holding the three action buttons."""
        row = QHBoxLayout()
        row.addWidget(self.copy_button)
        row.addWidget(self.open_button)
        row.addWidget(self.save_button)
        return row

    def _has_output(self) -> bool:
        """Whether the output has real content the actions should act on."""
        if not exact_text(self._output).strip():
            return False
        return self._is_valid() if self._is_valid is not None else True

    def copy(self) -> None:
        """Copy the output to the clipboard, if there is any."""
        text = exact_text(self._output)
        clipboard = QApplication.clipboard()
        if text and clipboard is not None:
            clipboard.setText(text)

    def open_in_editor(self) -> QWidget | None:
        """Open the output in a new editor tab, if a window is available."""
        if not self._has_output():
            return None
        tab_widget = getattr(self._main_window, "tab_widget", None)
        if tab_widget is None:
            pybreeze_logger.info("output_actions.py no tab_widget to open editor in")
            return None
        from je_editor import EditorWidget
        editor = EditorWidget(self._main_window)
        editor.code_edit.setPlainText(exact_text(self._output))
        tab_widget.addTab(
            editor, language_wrapper.language_word_dict.get("output_actions_editor_tab_label"))
        tab_widget.setCurrentWidget(editor)
        return editor

    def suggested_filename(self) -> str:
        """Return the default filename for the current basename and extension."""
        return f"{_resolve(self._basename)}.{_resolve(self._extension)}"

    def _file_filter(self, extension: str) -> str:
        """Return the file-dialog filter string for an extension."""
        word = language_wrapper.language_word_dict
        filters = {
            "py": word.get("output_actions_filter_python"),
            "json": word.get("output_actions_filter_json"),
        }
        return filters.get(extension, word.get("output_actions_filter_text"))

    def save_to_file(self) -> str | None:
        """Save the output to a user-chosen file; return the path or ``None``."""
        if not self._has_output():
            return None
        extension = _resolve(self._extension)
        path, _selected = QFileDialog.getSaveFileName(
            self._parent,
            language_wrapper.language_word_dict.get("output_actions_save_dialog_title"),
            self.suggested_filename(),
            self._file_filter(extension))
        if not path:
            return None
        try:
            # Replaced in one step: write_text emptied the file first, so a
            # failure part-way lost the file the user chose to replace
            replace_text(Path(path), exact_text(self._output))
        except OSError as error:
            pybreeze_logger.error("output_actions.py save failed: %r", error)
            # It used to go to the log only, and the user took it as saved.
            word = language_wrapper.language_word_dict
            QMessageBox.warning(
                self._parent, word.get("output_actions_save_failed_title"),
                as_text(word.get("output_actions_save_failed_message").format(
                    file=Path(path).name, error=error.strerror or error)))
            return None
        return path

"""A tool tab that pretty-prints, minifies and validates JSON."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.exception.exceptions import ITEJsonException
from pybreeze.utils.json_format.json_process import minify_json, reformat_json
from pybreeze.utils.logging.logger import pybreeze_logger


class JsonFormatGUI(QWidget):
    """Paste JSON, then format it, minify it, or read its validation error."""

    def __init__(self, main_window=None) -> None:
        """
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        # The last valid result (not an error/hint), gating open/save.
        self._valid_output = False
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("json_format_input_label"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(word.get("json_format_input_placeholder"))
        self.input_edit.setAcceptRichText(False)

        self.format_button = QPushButton(word.get("json_format_format_button"))
        self.format_button.clicked.connect(self.format_json)
        self.minify_button = QPushButton(word.get("json_format_minify_button"))
        self.minify_button.clicked.connect(self.minify)

        buttons = QHBoxLayout()
        buttons.addWidget(self.format_button)
        buttons.addWidget(self.minify_button)

        self.output_label = QLabel(word.get("json_format_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="formatted", extension="json",
            is_valid=lambda: self._valid_output)

        layout = QVBoxLayout()
        layout.addWidget(self.input_label)
        layout.addWidget(self.input_edit)
        layout.addLayout(buttons)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output_edit)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

    def _run(self, transform) -> None:
        """Apply a JSON transform, showing the result or a friendly error."""
        word = language_wrapper.language_word_dict
        text = self.input_edit.toPlainText().strip()
        if not text:
            self._valid_output = False
            self.output_edit.setPlainText(word.get("json_format_empty_hint"))
            return
        try:
            result = transform(text)
        except ITEJsonException as error:
            pybreeze_logger.info("json_format_gui.py transform failed: %r", error)
            self._valid_output = False
            self.output_edit.setPlainText(word.get("json_format_error").format(error=str(error)))
            return
        self._valid_output = True
        self.output_edit.setPlainText(result)

    def format_json(self) -> None:
        """Pretty-print the input JSON."""
        self._run(reformat_json)

    def minify(self) -> None:
        """Minify the input JSON onto a single line."""
        self._run(minify_json)

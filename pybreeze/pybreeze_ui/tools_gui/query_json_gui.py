"""A tool tab that converts between URL query strings and JSON."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.exception.exceptions import QueryConvertException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.query_tools.query_convert import json_to_query, query_to_json


class QueryJsonGUI(QWidget):
    """Convert a query string to JSON and back, in either direction."""

    def __init__(self, main_window=None) -> None:
        """
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        self._valid_output = False
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("query_json_input_label"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(word.get("query_json_input_placeholder"))
        self.input_edit.setAcceptRichText(False)

        self.to_json_button = QPushButton(word.get("query_json_to_json_button"))
        self.to_json_button.clicked.connect(self.convert_to_json)
        self.to_query_button = QPushButton(word.get("query_json_to_query_button"))
        self.to_query_button.clicked.connect(self.convert_to_query)

        buttons = QHBoxLayout()
        buttons.addWidget(self.to_json_button)
        buttons.addWidget(self.to_query_button)

        self.output_label = QLabel(word.get("query_json_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="query", extension="txt", is_valid=lambda: self._valid_output)

        layout = QVBoxLayout()
        layout.addWidget(self.input_label)
        layout.addWidget(self.input_edit)
        layout.addLayout(buttons)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output_edit)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

    def convert_to_json(self) -> None:
        """Convert the input query string to JSON."""
        text = self.input_edit.toPlainText().strip()
        if not text:
            self._valid_output = False
            self.output_edit.setPlainText(
                language_wrapper.language_word_dict.get("query_json_empty_hint"))
            return
        self._valid_output = True
        self.output_edit.setPlainText(query_to_json(text))

    def convert_to_query(self) -> None:
        """Convert the input JSON to a query string."""
        word = language_wrapper.language_word_dict
        text = self.input_edit.toPlainText().strip()
        if not text:
            self._valid_output = False
            self.output_edit.setPlainText(word.get("query_json_empty_hint"))
            return
        try:
            result = json_to_query(text)
        except QueryConvertException as error:
            pybreeze_logger.info("query_json_gui.py to-query failed: %r", error)
            self._valid_output = False
            self.output_edit.setPlainText(word.get("query_json_error").format(error=str(error)))
            return
        self._valid_output = True
        self.output_edit.setPlainText(result)

"""A tool tab that parses a URL into JSON parts and rebuilds one from them."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.exception.exceptions import UrlConvertException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.url_tools.url_convert import json_to_url, url_to_json


class UrlBuilderGUI(QWidget):
    """Parse a URL into its JSON parts and build a URL back from them."""

    def __init__(self, main_window=None) -> None:
        """
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        self._valid_output = False
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("url_builder_input_label"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(word.get("url_builder_input_placeholder"))
        self.input_edit.setAcceptRichText(False)

        self.to_json_button = QPushButton(word.get("url_builder_to_json_button"))
        self.to_json_button.clicked.connect(self.convert_to_json)
        self.to_url_button = QPushButton(word.get("url_builder_to_url_button"))
        self.to_url_button.clicked.connect(self.convert_to_url)

        buttons = QHBoxLayout()
        buttons.addWidget(self.to_json_button)
        buttons.addWidget(self.to_url_button)

        self.output_label = QLabel(word.get("url_builder_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="url", extension="txt", is_valid=lambda: self._valid_output)

        layout = QVBoxLayout()
        layout.addWidget(self.input_label)
        layout.addWidget(self.input_edit)
        layout.addLayout(buttons)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output_edit)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

    def convert_to_json(self) -> None:
        """Parse the input URL into its JSON parts."""
        text = self.input_edit.toPlainText().strip()
        if not text:
            self._valid_output = False
            self.output_edit.setPlainText(
                language_wrapper.language_word_dict.get("url_builder_empty_hint"))
            return
        self._valid_output = True
        self.output_edit.setPlainText(url_to_json(text))

    def convert_to_url(self) -> None:
        """Build a URL from the input JSON parts."""
        word = language_wrapper.language_word_dict
        text = self.input_edit.toPlainText().strip()
        if not text:
            self._valid_output = False
            self.output_edit.setPlainText(word.get("url_builder_empty_hint"))
            return
        try:
            result = json_to_url(text)
        except UrlConvertException as error:
            pybreeze_logger.info("url_builder_gui.py to-url failed: %r", error)
            self._valid_output = False
            self.output_edit.setPlainText(word.get("url_builder_error").format(error=str(error)))
            return
        self._valid_output = True
        self.output_edit.setPlainText(result)

"""A tool tab that parses a URL into JSON parts and rebuilds one from them."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.run_shortcut import act_on_ctrl_enter
from pybreeze.pybreeze_ui.exact_text import exact_text
from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.exception.exceptions import UrlConvertException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.url_tools.url_convert import json_to_url, url_to_json
from pybreeze.pybreeze_ui.error_text import error_text
from pybreeze.pybreeze_ui.fixed_pitch import use_fixed_pitch_font


class UrlBuilderGUI(QWidget):
    """Parse a URL into its JSON parts and build a URL back from them."""

    def __init__(self, main_window=None, initial_url: str | None = None) -> None:
        """
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        :param initial_url: a URL to pre-fill and parse on open, if given
        """
        super().__init__()
        self._valid_output = False
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("url_builder_input_label"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(word.get("url_builder_input_placeholder"))
        self.input_edit.setAcceptRichText(False)
        use_fixed_pitch_font(self.input_edit)

        self.to_json_button = QPushButton(word.get("url_builder_to_json_button"))
        self.to_json_button.clicked.connect(self.convert_to_json)
        self.to_url_button = QPushButton(word.get("url_builder_to_url_button"))
        self.to_url_button.clicked.connect(self.convert_to_url)
        # Ctrl+Enter goes the way the input reads: from JSON for a JSON object
        self.to_json_button.setToolTip(word.get("ctrl_enter_when_not_json"))
        self.to_url_button.setToolTip(word.get("ctrl_enter_when_json"))
        act_on_ctrl_enter(self, self.convert_as_pasted)

        buttons = QHBoxLayout()
        buttons.addWidget(self.to_json_button)
        buttons.addWidget(self.to_url_button)

        self.output_label = QLabel(word.get("url_builder_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        use_fixed_pitch_font(self.output_edit)

        self.output_actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="url", extension="txt", is_valid=lambda: self._valid_output)

        layout = QVBoxLayout()
        layout.addWidget(self.input_label)
        layout.addWidget(self.input_edit)
        layout.addLayout(buttons)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output_edit)
        layout.addLayout(self.output_actions.button_row())
        self.setLayout(layout)

        if initial_url:
            self.input_edit.setPlainText(initial_url)
            self.convert_to_json()

    def convert_as_pasted(self) -> None:
        """Ctrl+Enter: JSON → URL for a JSON object, URL → JSON otherwise."""
        pasted_json = exact_text(self.input_edit).lstrip().startswith("{")
        (self.to_url_button if pasted_json else self.to_json_button).click()

    def convert_to_json(self) -> None:
        """Parse the input URL into its JSON parts."""
        word = language_wrapper.language_word_dict
        text = exact_text(self.input_edit).strip()
        if not text:
            self._valid_output = False
            self.output_edit.setPlainText(word.get("url_builder_empty_hint"))
            return
        try:
            result = url_to_json(text)
        except UrlConvertException as error:
            pybreeze_logger.info("url_builder_gui.py to-json failed: %r", error)
            self._valid_output = False
            self.output_edit.setPlainText(word.get("url_builder_parse_error").format(error=error_text(str(error))))
            return
        self._valid_output = True
        self.output_edit.setPlainText(result)

    def convert_to_url(self) -> None:
        """Build a URL from the input JSON parts."""
        word = language_wrapper.language_word_dict
        text = exact_text(self.input_edit).strip()
        if not text:
            self._valid_output = False
            self.output_edit.setPlainText(word.get("url_builder_empty_hint"))
            return
        try:
            result = json_to_url(text)
        except UrlConvertException as error:
            pybreeze_logger.info("url_builder_gui.py to-url failed: %r", error)
            self._valid_output = False
            self.output_edit.setPlainText(word.get("url_builder_error").format(error=error_text(str(error))))
            return
        self._valid_output = True
        self.output_edit.setPlainText(result)

"""A tool tab that converts between epoch values and ISO-8601 date-times."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.exception.exceptions import TimestampParseException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.timestamp_tools.timestamp_converter import (
    TimestampResult, convert_timestamp
)


def build_result_text(result: TimestampResult) -> str:
    """Render a conversion result into a readable block.

    :param result: the converted instant
    :return: display text listing every representation
    """
    word = language_wrapper.language_word_dict
    return "\n".join([
        f"{word.get('timestamp_epoch_seconds_label')}: {result.epoch_seconds}",
        f"{word.get('timestamp_epoch_millis_label')}: {result.epoch_millis}",
        f"{word.get('timestamp_iso_label')}: {result.iso_utc}",
    ])


class TimestampGUI(QWidget):
    """Enter an epoch number or ISO date-time and see all representations."""

    def __init__(self, main_window=None) -> None:
        """
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        self._valid_output = False
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("timestamp_input_label"))
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(word.get("timestamp_input_placeholder"))
        self.input_edit.returnPressed.connect(self.convert)

        self.convert_button = QPushButton(word.get("timestamp_convert_button"))
        self.convert_button.clicked.connect(self.convert)

        self.output_label = QLabel(word.get("timestamp_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="timestamp", extension="txt", is_valid=lambda: self._valid_output)

        layout = QVBoxLayout()
        for widget in (
            self.input_label, self.input_edit, self.convert_button,
            self.output_label, self.output_edit,
        ):
            layout.addWidget(widget)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

    def convert(self) -> None:
        """Convert the input and show every representation of the instant."""
        word = language_wrapper.language_word_dict
        text = self.input_edit.text().strip()
        if not text:
            self._valid_output = False
            self.output_edit.setPlainText(word.get("timestamp_empty_hint"))
            return
        try:
            result = convert_timestamp(text)
        except TimestampParseException as error:
            pybreeze_logger.info("timestamp_gui.py convert failed: %r", error)
            self._valid_output = False
            self.output_edit.setPlainText(
                word.get("timestamp_error").format(error=str(error)))
            return
        self._valid_output = True
        self.output_edit.setPlainText(build_result_text(result))

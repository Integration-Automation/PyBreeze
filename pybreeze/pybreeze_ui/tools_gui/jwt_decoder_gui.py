"""A tool tab that decodes a JWT's header and payload for inspection.

The signature is never verified — this is for reading a token's claims (issuer,
subject, expiry) while building or debugging an API test, not for trusting it.
"""
from __future__ import annotations

import json

from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.exception.exceptions import JwtDecodeException
from pybreeze.utils.jwt_tools.jwt_decoder import (
    DecodedJwt, decode_jwt, humanized_timestamp_claims
)
from pybreeze.utils.logging.logger import pybreeze_logger


def build_decoded_text(decoded: DecodedJwt) -> str:
    """Render a decoded JWT into a readable, sectioned string.

    :param decoded: the decoded token parts
    :return: display text with header, payload and readable timestamps
    """
    word = language_wrapper.language_word_dict
    sections = [
        word.get("jwt_decoder_header_label"),
        json.dumps(decoded.header, indent=4, sort_keys=True, ensure_ascii=False),
        "",
        word.get("jwt_decoder_payload_label"),
        json.dumps(decoded.payload, indent=4, sort_keys=True, ensure_ascii=False),
    ]
    readable = humanized_timestamp_claims(decoded.payload)
    if readable:
        sections.append("")
        sections.append(word.get("jwt_decoder_times_label"))
        sections.extend(f"{claim}: {value}" for claim, value in readable.items())
    return "\n".join(sections)


class JwtDecoderGUI(QWidget):
    """Paste a JWT, decode it, and read its claims."""

    def __init__(self, initial_token: str | None = None, main_window=None) -> None:
        """
        :param initial_token: a token to pre-fill and decode on open, if given
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        self._valid_output = False
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("jwt_decoder_input_label"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(word.get("jwt_decoder_input_placeholder"))
        self.input_edit.setAcceptRichText(False)

        self.decode_button = QPushButton(word.get("jwt_decoder_decode_button"))
        self.decode_button.clicked.connect(self.decode)

        self.output_label = QLabel(word.get("jwt_decoder_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="jwt", extension="txt", is_valid=lambda: self._valid_output)

        layout = QVBoxLayout()
        for widget in (
            self.input_label, self.input_edit, self.decode_button,
            self.output_label, self.output_edit,
        ):
            layout.addWidget(widget)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

        if initial_token:
            self.input_edit.setPlainText(initial_token)
            self.decode()

    def decode(self) -> None:
        """Decode the pasted token and show its header and payload."""
        word = language_wrapper.language_word_dict
        token = self.input_edit.toPlainText().strip()
        if not token:
            self._valid_output = False
            self.output_edit.setPlainText(word.get("jwt_decoder_empty_hint"))
            return
        try:
            decoded = decode_jwt(token)
        except JwtDecodeException as error:
            pybreeze_logger.info("jwt_decoder_gui.py decode failed: %r", error)
            self._valid_output = False
            self.output_edit.setPlainText(
                word.get("jwt_decoder_error").format(error=str(error)))
            return
        self._valid_output = True
        self.output_edit.setPlainText(build_decoded_text(decoded))

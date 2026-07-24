"""A tool tab that turns a pasted ``curl`` command into automation scripts.

Automation engineers routinely copy a request as ``curl`` from browser dev tools.
This widget parses that command and generates a runnable script for a chosen
target (Python ``requests``, APITestka, LoadDensity), which can then be copied,
opened straight into a new editor tab, or saved to a ``.py`` / ``.json`` file
via the shared output actions.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.curl_import.curl_parser import parse_curl
from pybreeze.utils.curl_import.script_templates import TEMPLATE_TARGETS, generate_template
from pybreeze.utils.exception.exceptions import CurlParseException
from pybreeze.utils.logging.logger import pybreeze_logger

# The single target that generates JSON rather than Python
_JSON_TARGET = "apitestka_action"


class CurlImportGUI(QWidget):
    """Paste a ``curl`` command, generate a script, and copy / open / save it."""

    def __init__(self, main_window=None) -> None:
        """
        :param main_window: the window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        # The last successfully generated code (not an error or hint message).
        self._generated_code: str | None = None
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("curl_import_input_label"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(word.get("curl_import_input_placeholder"))
        self.input_edit.setAcceptRichText(False)

        # Target selector: each item stores its template key as user data.
        self.target_label = QLabel(word.get("curl_import_target_label"))
        self.target_select = QComboBox()
        for target_key, label_key in TEMPLATE_TARGETS:
            self.target_select.addItem(word.get(label_key), target_key)
        self.target_select.currentIndexChanged.connect(self._on_target_changed)

        self.convert_button = QPushButton(word.get("curl_import_convert_button"))
        self.convert_button.clicked.connect(self.convert)

        self.output_label = QLabel(word.get("curl_import_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        # Shared copy / open-in-editor / save actions. The extension and basename
        # follow the selected target; open/save are no-ops until a valid template.
        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename=lambda: "action" if self.selected_target() == _JSON_TARGET else "request",
            extension=lambda: "json" if self.selected_target() == _JSON_TARGET else "py",
            is_valid=lambda: self._generated_code is not None)

        layout = QVBoxLayout()
        for widget in (
            self.input_label, self.input_edit,
            self.target_label, self.target_select, self.convert_button,
            self.output_label, self.output_edit,
        ):
            layout.addWidget(widget)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

    def selected_target(self) -> str:
        """Return the template key of the currently selected target."""
        return self.target_select.currentData()

    def _on_target_changed(self, _index: int) -> None:
        """Regenerate when the target changes, if there is already input."""
        if self.input_edit.toPlainText().strip():
            self.convert()

    def convert(self) -> None:
        """Parse the input command and show the template for the chosen target."""
        word = language_wrapper.language_word_dict
        command = self.input_edit.toPlainText().strip()
        if not command:
            self._generated_code = None
            self.output_edit.setPlainText(word.get("curl_import_empty_hint"))
            return
        try:
            code = generate_template(self.selected_target(), parse_curl(command))
        except CurlParseException as error:
            pybreeze_logger.info("curl_import_gui.py convert failed: %r", error)
            self._generated_code = None
            self.output_edit.setPlainText(
                word.get("curl_import_error").format(error=str(error)))
            return
        self._generated_code = code
        self.output_edit.setPlainText(code)

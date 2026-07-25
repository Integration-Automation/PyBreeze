"""A tool tab that turns a browser HAR export into automation scripts.

"Copy as cURL" captures one request; **Save all as HAR** captures the session.
This widget reads that export, lists the recorded requests (hiding page assets
unless asked), and generates a script for the selected ones — a pytest file of
several tests, an APITestka action list that replays the flow, and so on — using
the same targets and output actions as the cURL importer.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.curl_import.script_templates import TEMPLATE_TARGETS
from pybreeze.utils.exception.exceptions import HarParseException
from pybreeze.utils.har_import.har_codegen import generate_har_script
from pybreeze.utils.har_import.har_parser import HarEntry, api_entries, parse_har, summarize
from pybreeze.utils.logging.logger import pybreeze_logger

# The single target that generates JSON rather than Python
_JSON_TARGET = "apitestka_action"
# Separator between hosts in the summary line
_HOST_SEPARATOR = ", "
# Hosts listed before the summary is shortened
_MAX_LISTED_HOSTS = 3


class HarImportGUI(QWidget):
    """Open a ``.har`` export, pick recorded requests, and generate a script."""

    def __init__(self, main_window=None) -> None:
        """
        :param main_window: the window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        # Every request in the export, and the subset currently listed.
        self._entries: list[HarEntry] = []
        self._shown: list[HarEntry] = []
        self._generated_code: str | None = None
        word = language_wrapper.language_word_dict

        self.open_button = QPushButton(word.get("har_import_open_button"))
        self.open_button.clicked.connect(self.open_file)
        self.api_only_check = QCheckBox(word.get("har_import_api_only"))
        self.api_only_check.setChecked(True)
        self.api_only_check.stateChanged.connect(self._refresh_entry_list)

        top_row = QHBoxLayout()
        top_row.addWidget(self.open_button)
        top_row.addWidget(self.api_only_check)

        self.summary_label = QLabel(word.get("har_import_empty_hint"))
        self.entry_list = QListWidget()
        self.entry_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        self.target_label = QLabel(word.get("curl_import_target_label"))
        self.target_select = QComboBox()
        for target_key, label_key in TEMPLATE_TARGETS:
            self.target_select.addItem(word.get(label_key), target_key)

        self.generate_selected_button = QPushButton(word.get("har_import_generate_selected"))
        self.generate_selected_button.clicked.connect(self.generate_selected)
        self.generate_all_button = QPushButton(word.get("har_import_generate_all"))
        self.generate_all_button.clicked.connect(self.generate_all)

        generate_row = QHBoxLayout()
        generate_row.addWidget(self.generate_selected_button)
        generate_row.addWidget(self.generate_all_button)

        self.output_label = QLabel(word.get("curl_import_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename=lambda: "actions" if self.selected_target() == _JSON_TARGET else "session",
            extension=lambda: "json" if self.selected_target() == _JSON_TARGET else "py",
            is_valid=lambda: self._generated_code is not None)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.entry_list)
        layout.addWidget(self.target_label)
        layout.addWidget(self.target_select)
        layout.addLayout(generate_row)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output_edit)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

    def selected_target(self) -> str:
        """Return the template key of the currently selected target."""
        return self.target_select.currentData()

    def open_file(self) -> str | None:
        """Ask for a ``.har`` file, then load it; return the path or ``None``."""
        word = language_wrapper.language_word_dict
        path, _selected = QFileDialog.getOpenFileName(
            self, word.get("har_import_file_dialog_title"), "",
            word.get("har_import_file_filter"))
        if not path:
            return None
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as error:
            pybreeze_logger.info("har_import_gui.py read failed: %r", error)
            self._report_error(word.get("har_import_read_error").format(error=str(error)))
            return None
        self.load_text(text)
        return path

    def load_text(self, text: str) -> bool:
        """Parse *text* as a HAR export and list what it recorded.

        :param text: the contents of a ``.har`` file
        :return: whether the export parsed
        """
        try:
            entries = parse_har(text)
        except HarParseException as error:
            pybreeze_logger.info("har_import_gui.py parse failed: %r", error)
            self._entries = []
            self._refresh_entry_list()
            self._report_error(
                language_wrapper.language_word_dict.get("har_import_error").format(
                    error=str(error)))
            return False
        self._entries = entries
        self._refresh_entry_list()
        return True

    def _report_error(self, message: str) -> None:
        """Show *message* as the summary and clear any generated output."""
        self._generated_code = None
        self.summary_label.setText(message)
        self.output_edit.setPlainText(message)

    def _summary_text(self) -> str:
        """Return the counts-and-hosts line describing the loaded export."""
        word = language_wrapper.language_word_dict
        if not self._entries:
            return word.get("har_import_empty_hint")
        summary = summarize(self._entries)
        hosts = _HOST_SEPARATOR.join(summary.hosts[:_MAX_LISTED_HOSTS])
        if len(summary.hosts) > _MAX_LISTED_HOSTS:
            hosts = f"{hosts}…"
        return word.get("har_import_summary").format(
            total=summary.total, api=summary.api, hosts=hosts)

    def _refresh_entry_list(self) -> None:
        """Rebuild the list from the current export and the API-only filter."""
        self._shown = api_entries(self._entries) if self.api_only_check.isChecked() \
            else list(self._entries)
        self.entry_list.clear()
        self.entry_list.addItems([entry.summary() for entry in self._shown])
        self.summary_label.setText(self._summary_text())

    def selected_entries(self) -> list[HarEntry]:
        """Return the listed entries the user selected, in capture order."""
        rows = sorted(index.row() for index in self.entry_list.selectedIndexes())
        return [self._shown[row] for row in rows if 0 <= row < len(self._shown)]

    def _generate(self, entries: list[HarEntry], empty_hint_key: str) -> None:
        """Generate a script for *entries*, or show the hint when there are none."""
        word = language_wrapper.language_word_dict
        if not entries:
            self._generated_code = None
            self.output_edit.setPlainText(word.get(empty_hint_key))
            return
        code = generate_har_script(
            self.selected_target(), [entry.request for entry in entries])
        self._generated_code = code
        self.output_edit.setPlainText(code)

    def generate_selected(self) -> None:
        """Generate a script covering the selected requests."""
        self._generate(self.selected_entries(), "har_import_no_selection")

    def generate_all(self) -> None:
        """Generate a script covering every request currently listed."""
        self._generate(self._shown, "har_import_empty_hint")

"""A tool tab that analyses a pasted block of HTTP headers.

Paste request or response headers and read back every field, the names that were
sent more than once, and what is worth knowing about them — cookie flags, CORS
and HSTS policies, headers carrying credentials, and the response security
headers that are missing.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog, QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.design.panels import wrapping_row
from pybreeze.pybreeze_ui.plain_text import as_text
from pybreeze.pybreeze_ui.run_shortcut import press_on_ctrl_enter
from pybreeze.pybreeze_ui.exact_text import exact_text
from pybreeze.pybreeze_ui.tools_gui.jwt_decoder_gui import JwtDecoderGUI
from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.pybreeze_ui.tools_gui.tool_tabs import open_tool_tab
from pybreeze.utils.header_tools.header_analyzer import (
    HeaderAnalysis, HeaderFinding, analyze_headers
)
from pybreeze.utils.header_tools.header_rules import HEADER_FINDING_KEY_PREFIX
from pybreeze.utils.header_tools.header_sarif import write_sarif
from pybreeze.utils.jwt_tools.jwt_decoder import find_tokens
from pybreeze.utils.logging.logger import pybreeze_logger


def _finding_line(finding: HeaderFinding) -> str:
    """Render one finding as a translated, level-prefixed line."""
    word = language_wrapper.language_word_dict
    level = word.get(f"header_analyzer_level_{finding.level}") or finding.level
    message = word.get(HEADER_FINDING_KEY_PREFIX + finding.code) or finding.code
    return f"[{level}] {message.format(header=finding.header, detail=finding.detail)}"


def build_header_report(analysis: HeaderAnalysis) -> str:
    """Render a header analysis into a readable, sectioned report.

    :param analysis: the analysed header block
    :return: display text, or the "no headers" message when nothing was found
    """
    word = language_wrapper.language_word_dict
    if not analysis.fields:
        return word.get("header_analyzer_no_headers")

    lines = [word.get("header_analyzer_headers_label").format(count=len(analysis.fields))]
    lines.extend(f"{header.name}: {header.value}" for header in analysis.fields)

    if analysis.duplicates:
        lines.extend(["", word.get("header_analyzer_duplicates_label")])
        lines.extend(f"{name} × {count}" for name, count in analysis.duplicates.items())

    lines.extend(["", word.get("header_analyzer_findings_label")])
    if analysis.findings:
        lines.extend(_finding_line(finding) for finding in analysis.findings)
    else:
        lines.append(word.get("header_analyzer_no_findings"))
    return "\n".join(lines)


class HeaderAnalyzerGUI(QWidget):
    """Paste HTTP headers and read what they say about the request or response."""

    def __init__(self, main_window=None, initial_headers: str | None = None) -> None:
        """
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        :param initial_headers: a header block to pre-fill and analyse on open
        """
        super().__init__()
        self._main_window = main_window
        self._analysis: HeaderAnalysis | None = None
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("header_analyzer_input_label"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(word.get("header_analyzer_input_placeholder"))
        self.input_edit.setAcceptRichText(False)

        self.analyze_button = QPushButton(word.get("header_analyzer_analyze_button"))
        self.analyze_button.clicked.connect(self.analyze)
        press_on_ctrl_enter(self, self.analyze_button)

        self.output_label = QLabel(word.get("header_analyzer_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        # Cross-tool action: a bearer token in a header is worth reading, and the
        # decoder is the tool that reads it.
        self.open_jwt_button = QPushButton(word.get("header_analyzer_open_jwt_button"))
        self.open_jwt_button.clicked.connect(self.open_jwt_in_decoder)
        self.open_jwt_button.setEnabled(False)
        # The findings for a tool that reads them: a code-scanning service, a CI step
        self.export_sarif_button = QPushButton(word.get("header_analyzer_export_sarif_button"))
        self.export_sarif_button.clicked.connect(self.export_sarif)
        self.export_sarif_button.setEnabled(False)

        self.output_actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="headers", extension="txt",
            is_valid=lambda: self._analysis is not None)

        layout = QVBoxLayout()
        for widget in (
            self.input_label, self.input_edit, self.analyze_button,
            self.output_label, self.output_edit,
        ):
            layout.addWidget(widget)
        layout.addLayout(wrapping_row(self.open_jwt_button, self.export_sarif_button))
        layout.addLayout(self.output_actions.button_row())
        self.setLayout(layout)

        if initial_headers:
            self.input_edit.setPlainText(initial_headers)
            self.analyze()

    def _clear_analysis(self, message: str) -> None:
        """Forget the analysis and show *message* instead of a report."""
        self._analysis = None
        self.open_jwt_button.setEnabled(False)
        self.export_sarif_button.setEnabled(False)
        self.output_edit.setPlainText(message)

    def analyze(self) -> None:
        """Analyse the pasted headers and show the report."""
        word = language_wrapper.language_word_dict
        # Dedented before stripped: stripping first took the indent off the first
        # line only, and every other line then read as folded into it
        text = textwrap.dedent(exact_text(self.input_edit)).strip()
        if not text:
            self._clear_analysis(word.get("header_analyzer_empty_hint"))
            return
        analysis = analyze_headers(text)
        if not analysis.fields:
            self._clear_analysis(word.get("header_analyzer_no_headers"))
            return
        self._analysis = analysis
        self.open_jwt_button.setEnabled(bool(self.header_tokens()))
        self.export_sarif_button.setEnabled(True)
        self.output_edit.setPlainText(build_header_report(analysis))

    def export_sarif(self) -> str | None:
        """Save the analysed headers' findings as a SARIF file; return its path, or ``None``.

        The file names rules and lines, never a header's value: what the
        analyzer keeps out of a finding stays out of the report.
        """
        if self._analysis is None:
            return None
        word = language_wrapper.language_word_dict
        path, _selected = QFileDialog.getSaveFileName(
            self, word.get("header_analyzer_sarif_dialog_title"), "headers.sarif",
            word.get("header_analyzer_sarif_filter"))
        if not path:
            return None
        try:
            write_sarif(Path(path), self._analysis)
        except OSError as error:
            pybreeze_logger.error("header_analyzer_gui.py SARIF export failed: %r", error)
            QMessageBox.warning(
                self, word.get("output_actions_save_failed_title"),
                as_text(word.get("output_actions_save_failed_message").format(
                    file=Path(path).name, error=error.strerror or error)))
            return None
        return path

    def header_tokens(self) -> list[str]:
        """Return the JWT-looking tokens carried by the analysed headers."""
        if self._analysis is None:
            return []
        tokens: list[str] = []
        for header in self._analysis.fields:
            tokens.extend(token for token in find_tokens(header.value) if token not in tokens)
        return tokens

    def open_jwt_in_decoder(self) -> QWidget | None:
        """Open the first token found in a header in the JWT decoder, decoded."""
        tokens = self.header_tokens()
        if not tokens:
            return None
        return open_tool_tab(
            self._main_window,
            JwtDecoderGUI(initial_token=tokens[0], main_window=self._main_window),
            "extend_tools_menu_jwt_decoder_tab_label")

"""A tool tab that analyses a pasted block of HTTP headers.

Paste request or response headers and read back every field, the names that were
sent more than once, and what is worth knowing about them — cookie flags, CORS
and HSTS policies, headers carrying credentials, and the response security
headers that are missing.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.header_tools.header_analyzer import (
    HeaderAnalysis, HeaderFinding, analyze_headers
)


def _finding_line(finding: HeaderFinding) -> str:
    """Render one finding as a translated, level-prefixed line."""
    word = language_wrapper.language_word_dict
    level = word.get(f"header_analyzer_level_{finding.level}") or finding.level
    message = word.get(f"header_finding_{finding.code}") or finding.code
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
        self._analysis: HeaderAnalysis | None = None
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("header_analyzer_input_label"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(word.get("header_analyzer_input_placeholder"))
        self.input_edit.setAcceptRichText(False)

        self.analyze_button = QPushButton(word.get("header_analyzer_analyze_button"))
        self.analyze_button.clicked.connect(self.analyze)

        self.output_label = QLabel(word.get("header_analyzer_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="headers", extension="txt",
            is_valid=lambda: self._analysis is not None)

        layout = QVBoxLayout()
        for widget in (
            self.input_label, self.input_edit, self.analyze_button,
            self.output_label, self.output_edit,
        ):
            layout.addWidget(widget)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

        if initial_headers:
            self.input_edit.setPlainText(initial_headers)
            self.analyze()

    def analyze(self) -> None:
        """Analyse the pasted headers and show the report."""
        word = language_wrapper.language_word_dict
        text = self.input_edit.toPlainText().strip()
        if not text:
            self._analysis = None
            self.output_edit.setPlainText(word.get("header_analyzer_empty_hint"))
            return
        analysis = analyze_headers(text)
        if not analysis.fields:
            self._analysis = None
            self.output_edit.setPlainText(word.get("header_analyzer_no_headers"))
            return
        self._analysis = analysis
        self.output_edit.setPlainText(build_header_report(analysis))

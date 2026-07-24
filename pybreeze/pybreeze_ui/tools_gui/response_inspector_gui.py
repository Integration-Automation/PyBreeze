"""A tool tab that inspects a pasted HTTP response.

Detects the status code, headers, a JSON body, and any JWTs in the text, tying
together the HTTP status, JSON format and JWT decoder tools.
"""
from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.http_status_gui import HttpStatusGUI
from pybreeze.pybreeze_ui.tools_gui.jwt_decoder_gui import JwtDecoderGUI
from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.jwt_tools.jwt_decoder import humanized_timestamp_claims
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.response_inspector.response_analyzer import (
    ResponseAnalysis, analyze_response
)


def _status_section(analysis: ResponseAnalysis) -> list[str]:
    """Build the status lines of the report, or an empty list."""
    if analysis.status is None:
        return []
    word = language_wrapper.language_word_dict
    status = analysis.status
    lines = [word.get("response_status_label"), f"{status.code} {status.phrase}  [{status.category}]"]
    if status.description:
        lines.append(f"    {status.description}")
    lines.append("")
    return lines


def _jwt_section(analysis: ResponseAnalysis) -> list[str]:
    """Build the decoded-JWT lines of the report, or an empty list."""
    if not analysis.jwt_findings:
        return []
    word = language_wrapper.language_word_dict
    lines = [word.get("response_jwt_label")]
    for finding in analysis.jwt_findings:
        lines.append(json.dumps(finding.decoded.header, ensure_ascii=False))
        lines.append(json.dumps(finding.decoded.payload, indent=4, ensure_ascii=False))
        for claim, value in humanized_timestamp_claims(finding.decoded.payload).items():
            lines.append(f"    {claim}: {value}")
    lines.append("")
    return lines


def build_report_text(analysis: ResponseAnalysis) -> str:
    """Render a response analysis into a readable, sectioned report.

    :param analysis: the analysed response
    :return: display text
    """
    word = language_wrapper.language_word_dict
    lines: list[str] = []
    lines.extend(_status_section(analysis))
    if analysis.headers:
        lines.append(word.get("response_headers_label"))
        lines.extend(f"{name}: {value}" for name, value in analysis.headers.items())
        lines.append("")
    lines.extend(_jwt_section(analysis))
    lines.append(word.get("response_body_label"))
    lines.append(analysis.pretty_body if analysis.is_json_body else analysis.body)
    return "\n".join(lines)


class ResponseInspectorGUI(QWidget):
    """Paste a raw HTTP response and read a decoded summary of it."""

    def __init__(self, main_window=None) -> None:
        """
        :param main_window: the window whose ``tab_widget`` new tool tabs open in;
            when ``None``, the "open in tool" actions are disabled
        """
        super().__init__()
        self._main_window = main_window
        self._analysis: ResponseAnalysis | None = None
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("response_input_label"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(word.get("response_input_placeholder"))
        self.input_edit.setAcceptRichText(False)

        self.analyze_button = QPushButton(word.get("response_analyze_button"))
        self.analyze_button.clicked.connect(self.analyze)

        self.output_label = QLabel(word.get("response_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        # Cross-tool actions: open a finding in its dedicated tool, pre-filled.
        self.open_jwt_button = QPushButton(word.get("response_open_jwt_button"))
        self.open_jwt_button.clicked.connect(self.open_jwt_in_decoder)
        self.open_jwt_button.setEnabled(False)
        self.open_status_button = QPushButton(word.get("response_open_status_button"))
        self.open_status_button.clicked.connect(self.open_status_in_reference)
        self.open_status_button.setEnabled(False)

        # Shared copy / open-in-editor / save actions, valid once analysed.
        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="response", extension="txt",
            is_valid=lambda: self._analysis is not None)

        cross_tool = QHBoxLayout()
        cross_tool.addWidget(self.open_status_button)
        cross_tool.addWidget(self.open_jwt_button)

        layout = QVBoxLayout()
        layout.addWidget(self.input_label)
        layout.addWidget(self.input_edit)
        layout.addWidget(self.analyze_button)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output_edit)
        layout.addLayout(cross_tool)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

    def analyze(self) -> None:
        """Analyse the pasted response, show the report, and enable cross-tool actions."""
        word = language_wrapper.language_word_dict
        text = self.input_edit.toPlainText().strip()
        if not text:
            self._analysis = None
            self.open_jwt_button.setEnabled(False)
            self.open_status_button.setEnabled(False)
            self.output_edit.setPlainText(word.get("response_empty_hint"))
            return
        self._analysis = analyze_response(text)
        self.output_edit.setPlainText(build_report_text(self._analysis))
        self.open_jwt_button.setEnabled(bool(self._analysis.jwt_findings))
        self.open_status_button.setEnabled(self._analysis.status is not None)

    def _open_tool_tab(self, widget: QWidget, tab_label_key: str) -> QWidget | None:
        """Add *widget* as a new tab in the main window, if there is one."""
        tab_widget = getattr(self._main_window, "tab_widget", None)
        if tab_widget is None:
            pybreeze_logger.info("response_inspector_gui.py no tab_widget to open tool in")
            return None
        tab_widget.addTab(widget, language_wrapper.language_word_dict.get(tab_label_key))
        tab_widget.setCurrentWidget(widget)
        return widget

    def open_jwt_in_decoder(self) -> QWidget | None:
        """Open the first found JWT in the JWT decoder tool, pre-filled."""
        if self._analysis is None or not self._analysis.jwt_findings:
            return None
        token = self._analysis.jwt_findings[0].token
        return self._open_tool_tab(
            JwtDecoderGUI(initial_token=token, main_window=self._main_window),
            "extend_tools_menu_jwt_decoder_tab_label")

    def open_status_in_reference(self) -> QWidget | None:
        """Open the detected status code in the HTTP status reference, pre-filled."""
        if self._analysis is None or self._analysis.status is None:
            return None
        return self._open_tool_tab(
            HttpStatusGUI(
                initial_search=str(self._analysis.status.code),
                main_window=self._main_window),
            "extend_tools_menu_http_status_tab_label")

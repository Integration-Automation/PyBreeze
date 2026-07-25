"""Tests for the HTTP header analyzer tool widget."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict as EN
from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.utils.header_tools.header_analyzer import analyze_headers

_RESPONSE = (
    "HTTP/1.1 200 OK\n"
    "Server: nginx/1.25.3\n"
    "Content-Type: text/html\n"
    "Set-Cookie: sid=abc; Path=/\n"
)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def widget(app):
    from pybreeze.pybreeze_ui.tools_gui.header_analyzer_gui import HeaderAnalyzerGUI
    gui = HeaderAnalyzerGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestHeaderAnalyzerGUI:
    def test_headers_are_listed(self, widget):
        widget.input_edit.setPlainText(_RESPONSE)
        widget.analyze()
        output = widget.output_edit.toPlainText()
        assert "Server: nginx/1.25.3" in output
        assert "Content-Type: text/html" in output

    def test_findings_are_translated_not_raw_codes(self, widget):
        widget.input_edit.setPlainText(_RESPONSE)
        widget.analyze()
        output = widget.output_edit.toPlainText()
        assert "cookie_not_secure" not in output
        assert "Secure attribute" in output

    def test_finding_line_carries_its_level(self, widget):
        widget.input_edit.setPlainText(_RESPONSE)
        widget.analyze()
        assert "[WARNING]" in widget.output_edit.toPlainText()

    def test_duplicate_section_shows_the_count(self, widget):
        widget.input_edit.setPlainText("X-Trace: 1\nX-Trace: 2")
        widget.analyze()
        assert "x-trace × 2" in widget.output_edit.toPlainText()

    def test_clean_request_reports_nothing(self, widget):
        widget.input_edit.setPlainText("GET / HTTP/1.1\nHost: example.com")
        widget.analyze()
        assert EN["header_analyzer_no_findings"] in widget.output_edit.toPlainText()

    def test_empty_input_shows_hint(self, widget):
        widget.input_edit.setPlainText("   ")
        widget.analyze()
        assert widget.output_edit.toPlainText() == EN["header_analyzer_empty_hint"]

    def test_text_without_headers_reports_so(self, widget):
        widget.input_edit.setPlainText("just some prose")
        widget.analyze()
        assert widget.output_edit.toPlainText() == EN["header_analyzer_no_headers"]

    def test_initial_headers_are_analysed_on_open(self, app):
        from pybreeze.pybreeze_ui.tools_gui.header_analyzer_gui import HeaderAnalyzerGUI
        gui = HeaderAnalyzerGUI(initial_headers=_RESPONSE)
        assert "nginx/1.25.3" in gui.output_edit.toPlainText()
        gui.close()
        gui.deleteLater()

    def test_copy_output(self, app, widget):
        widget.input_edit.setPlainText(_RESPONSE)
        widget.analyze()
        widget.actions.copy()
        assert "nginx/1.25.3" in QApplication.clipboard().text()

    def test_save_after_no_headers_is_noop(self, widget):
        widget.input_edit.setPlainText("just some prose")
        widget.analyze()
        assert widget.actions.save_to_file() is None


class _FakeTabWidget:
    def __init__(self):
        self.added = []
        self.current = None

    def addTab(self, widget, label):
        self.added.append((widget, label))

    def setCurrentWidget(self, widget):
        self.current = widget


class _FakeMainWindow:
    def __init__(self):
        self.tab_widget = _FakeTabWidget()


def _jwt(payload: dict) -> str:
    import base64
    import json as json_module

    def seg(obj):
        raw = json_module.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{seg({'alg': 'HS256'})}.{seg(payload)}.sig"


class TestHeaderAnalyzerJwtHandOff:
    def test_button_disabled_without_a_token(self, widget):
        widget.input_edit.setPlainText(_RESPONSE)
        widget.analyze()
        assert not widget.open_jwt_button.isEnabled()

    def test_button_enabled_when_a_header_carries_a_token(self, widget):
        widget.input_edit.setPlainText(f"Authorization: Bearer {_jwt({'sub': '42'})}")
        widget.analyze()
        assert widget.open_jwt_button.isEnabled()

    def test_token_is_found_in_any_header(self, widget):
        token = _jwt({"sub": "7"})
        widget.input_edit.setPlainText(f"X-Custom-Auth: {token}")
        widget.analyze()
        assert widget.header_tokens() == [token]

    def test_open_jwt_opens_prefilled_decoder(self, app):
        from pybreeze.pybreeze_ui.tools_gui.header_analyzer_gui import HeaderAnalyzerGUI
        from pybreeze.pybreeze_ui.tools_gui.jwt_decoder_gui import JwtDecoderGUI
        window = _FakeMainWindow()
        gui = HeaderAnalyzerGUI(main_window=window)
        gui.input_edit.setPlainText(f"Authorization: Bearer {_jwt({'sub': '99'})}")
        gui.analyze()
        gui.open_jwt_in_decoder()
        opened = window.tab_widget.added[0][0]
        assert isinstance(opened, JwtDecoderGUI)
        assert '"sub": "99"' in opened.output_edit.toPlainText()
        gui.close()
        gui.deleteLater()

    def test_open_without_a_token_is_noop(self, widget):
        widget.input_edit.setPlainText(_RESPONSE)
        widget.analyze()
        assert widget.open_jwt_in_decoder() is None

    def test_button_goes_inactive_when_input_is_cleared(self, widget):
        widget.input_edit.setPlainText(f"Authorization: Bearer {_jwt({'sub': '1'})}")
        widget.analyze()
        widget.input_edit.setPlainText("   ")
        widget.analyze()
        assert not widget.open_jwt_button.isEnabled()


class TestEveryFindingCodeIsTranslated:
    def test_report_never_falls_back_to_a_code(self, app):
        # Any finding code without a language key would leak the slug into the UI.
        from pybreeze.pybreeze_ui.tools_gui.header_analyzer_gui import build_header_report
        text = (
            "HTTP/1.1 200 OK\n"
            "Server: nginx\n"
            "X-Powered-By: PHP\n"
            "X-XSS-Protection: 1\n"
            "X-Content-Type-Options: sniff\n"
            "Strict-Transport-Security: max-age=1\n"
            "Content-Security-Policy: default-src 'unsafe-inline' 'unsafe-eval'\n"
            "Access-Control-Allow-Origin: *\n"
            "Access-Control-Allow-Credentials: true\n"
            "Set-Cookie: sid=abc\n"
            "Authorization: Bearer secret\n"
            "Content-Type: text/html\n"
            "X-Trace: 1\n"
            "X-Trace: 2\n"
        )
        analysis = analyze_headers(text)
        report = build_header_report(analysis)
        for finding in analysis.findings:
            assert finding.code not in report
        assert "secret" not in report.split("== Findings ==")[1]

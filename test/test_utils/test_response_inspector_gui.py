"""Tests for the response inspector tool widget."""
from __future__ import annotations

import base64
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict


def _jwt(header: dict, payload: dict) -> str:
    def seg(obj):
        raw = json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{seg(header)}.{seg(payload)}.sig"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def widget(app):
    from pybreeze.pybreeze_ui.tools_gui.response_inspector_gui import ResponseInspectorGUI
    gui = ResponseInspectorGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestResponseInspectorGUI:
    def test_full_response(self, widget):
        widget.input_edit.setPlainText(
            "HTTP/1.1 200 OK\nContent-Type: application/json\n\n{\"ok\": true}")
        widget.analyze()
        output = widget.output_edit.toPlainText()
        assert "200 OK" in output
        assert "Content-Type: application/json" in output
        assert '"ok": true' in output

    def test_json_only(self, widget):
        widget.input_edit.setPlainText('{"a": 1}')
        widget.analyze()
        assert '"a": 1' in widget.output_edit.toPlainText()

    def test_jwt_is_decoded(self, widget):
        token = _jwt({"alg": "HS256"}, {"sub": "42"})
        widget.input_edit.setPlainText(f"HTTP/1.1 200 OK\nAuthorization: Bearer {token}\n\n{{}}")
        widget.analyze()
        assert '"sub": "42"' in widget.output_edit.toPlainText()

    def test_empty_shows_hint(self, widget):
        widget.input_edit.setPlainText("   ")
        widget.analyze()
        assert widget.output_edit.toPlainText() != ""

    def test_copy_output(self, app, widget):
        widget.input_edit.setPlainText('{"a": 1}')
        widget.analyze()
        widget.actions.copy()
        assert '"a": 1' in QApplication.clipboard().text()

    def test_build_report_text_minimal(self, app):
        from pybreeze.pybreeze_ui.tools_gui.response_inspector_gui import build_report_text
        from pybreeze.utils.response_inspector.response_analyzer import analyze_response
        text = build_report_text(analyze_response("plain text body"))
        assert "plain text body" in text


class _FakeTabWidget:
    """Records tabs added and the current widget."""

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


@pytest.fixture()
def widget_with_window(app):
    from pybreeze.pybreeze_ui.tools_gui.response_inspector_gui import ResponseInspectorGUI
    window = _FakeMainWindow()
    gui = ResponseInspectorGUI(window)
    yield gui, window
    gui.close()
    gui.deleteLater()


class TestResponseInspectorActions:
    def test_buttons_disabled_before_analyze(self, app):
        from pybreeze.pybreeze_ui.tools_gui.response_inspector_gui import ResponseInspectorGUI
        gui = ResponseInspectorGUI()
        assert not gui.open_jwt_button.isEnabled()
        assert not gui.open_status_button.isEnabled()
        gui.close()
        gui.deleteLater()

    def test_status_button_enabled_after_status(self, widget_with_window):
        gui, _window = widget_with_window
        gui.input_edit.setPlainText("HTTP/1.1 404 Not Found\n\n{}")
        gui.analyze()
        assert gui.open_status_button.isEnabled()

    def test_jwt_button_enabled_after_jwt(self, widget_with_window):
        gui, _window = widget_with_window
        token = _jwt({"alg": "HS256"}, {"sub": "1"})
        gui.input_edit.setPlainText(f"Authorization: Bearer {token}\n\n{{}}")
        gui.analyze()
        assert gui.open_jwt_button.isEnabled()

    def test_open_status_opens_prefilled_tab(self, widget_with_window):
        from pybreeze.pybreeze_ui.tools_gui.http_status_gui import HttpStatusGUI
        gui, window = widget_with_window
        gui.input_edit.setPlainText("HTTP/1.1 404 Not Found\n\n{}")
        gui.analyze()
        gui.open_status_in_reference()
        assert len(window.tab_widget.added) == 1
        opened = window.tab_widget.added[0][0]
        assert isinstance(opened, HttpStatusGUI)
        assert "404 Not Found" in opened.output_edit.toPlainText()

    def test_open_jwt_opens_prefilled_tab(self, widget_with_window):
        from pybreeze.pybreeze_ui.tools_gui.jwt_decoder_gui import JwtDecoderGUI
        gui, window = widget_with_window
        token = _jwt({"alg": "HS256"}, {"sub": "99"})
        gui.input_edit.setPlainText(f"Authorization: Bearer {token}\n\n{{}}")
        gui.analyze()
        gui.open_jwt_in_decoder()
        opened = window.tab_widget.added[0][0]
        assert isinstance(opened, JwtDecoderGUI)
        assert '"sub": "99"' in opened.output_edit.toPlainText()

    def test_open_without_window_is_safe(self, app):
        from pybreeze.pybreeze_ui.tools_gui.response_inspector_gui import ResponseInspectorGUI
        gui = ResponseInspectorGUI()  # no main window
        gui.input_edit.setPlainText("HTTP/1.1 200 OK\n\n{}")
        gui.analyze()
        assert gui.open_status_in_reference() is None
        gui.close()
        gui.deleteLater()

    def test_open_before_analyze_is_noop(self, widget_with_window):
        gui, window = widget_with_window
        assert gui.open_status_in_reference() is None
        assert window.tab_widget.added == []


class TestResponseInspectorHeaderHandOff:
    def test_headers_button_disabled_without_headers(self, widget_with_window):
        gui, _window = widget_with_window
        gui.input_edit.setPlainText('{"a": 1}')
        gui.analyze()
        assert not gui.open_headers_button.isEnabled()

    def test_headers_button_enabled_after_headers(self, widget_with_window):
        gui, _window = widget_with_window
        gui.input_edit.setPlainText("HTTP/1.1 200 OK\nServer: nginx\n\n{}")
        gui.analyze()
        assert gui.open_headers_button.isEnabled()

    def test_open_headers_opens_prefilled_analyzer(self, widget_with_window):
        from pybreeze.pybreeze_ui.tools_gui.header_analyzer_gui import HeaderAnalyzerGUI
        gui, window = widget_with_window
        gui.input_edit.setPlainText("HTTP/1.1 200 OK\nServer: nginx/1.25.3\n\n{}")
        gui.analyze()
        gui.open_headers_in_analyzer()
        opened = window.tab_widget.added[0][0]
        assert isinstance(opened, HeaderAnalyzerGUI)
        assert "nginx/1.25.3" in opened.output_edit.toPlainText()

    def test_repeated_headers_survive_the_hand_off(self, widget_with_window):
        # The inspector keeps headers in a dict; handing the raw text over is what
        # lets the analyzer still see both Set-Cookie lines.
        gui, window = widget_with_window
        gui.input_edit.setPlainText(
            "HTTP/1.1 200 OK\nSet-Cookie: a=1\nSet-Cookie: b=2\n\n{}")
        gui.analyze()
        gui.open_headers_in_analyzer()
        opened = window.tab_widget.added[0][0]
        assert "set-cookie × 2" in opened.output_edit.toPlainText()

    def test_open_headers_before_analyze_is_noop(self, widget_with_window):
        gui, window = widget_with_window
        assert gui.open_headers_in_analyzer() is None
        assert window.tab_widget.added == []


class TestResponseInspectorBodyHandOff:
    def test_body_button_disabled_for_a_non_json_body(self, widget_with_window):
        gui, _window = widget_with_window
        gui.input_edit.setPlainText("HTTP/1.1 200 OK\n\nplain text body")
        gui.analyze()
        assert not gui.open_body_button.isEnabled()

    def test_body_button_enabled_for_a_json_body(self, widget_with_window):
        gui, _window = widget_with_window
        gui.input_edit.setPlainText('HTTP/1.1 200 OK\n\n{"a": 1}')
        gui.analyze()
        assert gui.open_body_button.isEnabled()

    def test_open_body_opens_prefilled_json_format(self, widget_with_window):
        from pybreeze.pybreeze_ui.tools_gui.json_format_gui import JsonFormatGUI
        gui, window = widget_with_window
        gui.input_edit.setPlainText('HTTP/1.1 200 OK\n\n{"a":[1,2],"b":"x"}')
        gui.analyze()
        gui.open_body_in_json_format()
        opened = window.tab_widget.added[0][0]
        assert isinstance(opened, JsonFormatGUI)
        formatted = opened.output_edit.toPlainText()
        assert '"a": [' in formatted  # arrived already pretty-printed
        assert '"b": "x"' in formatted

    def test_open_body_without_json_is_noop(self, widget_with_window):
        gui, window = widget_with_window
        gui.input_edit.setPlainText("HTTP/1.1 500 Server Error\n\nboom")
        gui.analyze()
        assert gui.open_body_in_json_format() is None
        assert window.tab_widget.added == []

    def test_open_body_before_analyze_is_noop(self, widget_with_window):
        gui, _window = widget_with_window
        assert gui.open_body_in_json_format() is None

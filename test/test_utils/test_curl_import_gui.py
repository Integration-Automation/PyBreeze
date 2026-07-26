"""Tests for the cURL import tool widget."""
from __future__ import annotations

import json
import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    # Merge PyBreeze's translations into the shared dict, as the main window does
    # on startup, so the widget's labels and messages resolve.
    update_language_dict()
    return instance


@pytest.fixture()
def widget(app):
    from pybreeze.pybreeze_ui.tools_gui.curl_import_gui import CurlImportGUI
    gui = CurlImportGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestCurlImportGUI:
    def test_convert_produces_code(self, widget):
        widget.input_edit.setPlainText("curl https://example.com/api")
        widget.convert()
        output = widget.output_edit.toPlainText()
        assert "import requests" in output
        assert "https://example.com/api" in output

    def test_convert_reports_parse_error(self, widget):
        widget.input_edit.setPlainText("wget https://example.com")
        widget.convert()
        # The output should be an error message, not generated code.
        assert "import requests" not in widget.output_edit.toPlainText()

    def test_empty_input_shows_hint(self, widget):
        widget.input_edit.setPlainText("   ")
        widget.convert()
        assert widget.output_edit.toPlainText() != ""
        assert "import requests" not in widget.output_edit.toPlainText()

    def test_copy_output_sets_clipboard(self, app, widget):
        widget.input_edit.setPlainText("curl https://example.com/api")
        widget.convert()
        widget.actions.copy()
        assert "import requests" in QApplication.clipboard().text()

    def test_copy_with_empty_output_is_safe(self, widget):
        widget.output_edit.setPlainText("")
        widget.actions.copy()  # must not raise

    def test_json_body_conversion(self, widget):
        widget.input_edit.setPlainText(
            "curl -X POST https://x -H 'Content-Type: application/json' -d '{\"a\": 1}'")
        widget.convert()
        assert "json=json_body" in widget.output_edit.toPlainText()

    def _select_target(self, widget, target_key):
        index = widget.target_select.findData(target_key)
        widget.target_select.setCurrentIndex(index)

    def test_target_selector_has_all_targets(self, widget):
        keys = [widget.target_select.itemData(i) for i in range(widget.target_select.count())]
        assert keys == [
            "requests", "pytest", "apitestka_python", "apitestka_action", "loaddensity_python"]

    def test_generate_apitestka_python(self, widget):
        widget.input_edit.setPlainText("curl https://example.com/api")
        self._select_target(widget, "apitestka_python")
        widget.convert()
        assert "test_api_method_requests" in widget.output_edit.toPlainText()

    def test_generate_apitestka_action(self, widget):
        widget.input_edit.setPlainText("curl https://example.com/api")
        self._select_target(widget, "apitestka_action")
        widget.convert()
        assert "AT_test_api_method" in widget.output_edit.toPlainText()

    def test_changing_target_regenerates(self, widget):
        widget.input_edit.setPlainText("curl https://example.com/api")
        self._select_target(widget, "requests")
        widget.convert()
        assert "import requests" in widget.output_edit.toPlainText()
        # Switching target auto-regenerates because there is input.
        self._select_target(widget, "apitestka_action")
        assert "AT_test_api_method" in widget.output_edit.toPlainText()


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


class _FakeEditor:
    """Stand-in for a JEditor EditorWidget with a code_edit."""

    def __init__(self, _main_window):
        self.code_edit = type("CodeEdit", (), {"setPlainText": lambda self, t: setattr(self, "text", t)})()


@pytest.fixture()
def widget_with_window(app):
    from pybreeze.pybreeze_ui.tools_gui.curl_import_gui import CurlImportGUI
    window = _FakeMainWindow()
    gui = CurlImportGUI(window)
    yield gui, window
    gui.close()
    gui.deleteLater()


class TestCurlImportActions:
    def _select_target(self, widget, target_key):
        widget.target_select.setCurrentIndex(widget.target_select.findData(target_key))

    def test_open_in_editor_adds_tab_with_code(self, widget_with_window):
        gui, window = widget_with_window
        gui.input_edit.setPlainText("curl https://example.com/api")
        gui.convert()
        with patch(
            "je_editor.pyside_ui.main_ui.editor.editor_widget.EditorWidget", _FakeEditor
        ):
            editor = gui.actions.open_in_editor()
        assert len(window.tab_widget.added) == 1
        assert "import requests" in editor.code_edit.text

    def test_open_in_editor_without_code_is_noop(self, widget_with_window):
        gui, window = widget_with_window
        assert gui.actions.open_in_editor() is None
        assert window.tab_widget.added == []

    def test_open_after_parse_error_is_noop(self, widget_with_window):
        gui, window = widget_with_window
        gui.input_edit.setPlainText("wget https://x")
        gui.convert()
        assert gui.actions.open_in_editor() is None
        assert window.tab_widget.added == []

    def test_open_in_editor_without_window_is_safe(self, widget):
        widget.input_edit.setPlainText("curl https://x")
        widget.convert()
        assert widget.actions.open_in_editor() is None  # no main window

    def test_suggested_filename_python(self, widget):
        self._select_target(widget, "requests")
        assert widget.actions.suggested_filename() == "request.py"

    def test_suggested_filename_json(self, widget):
        self._select_target(widget, "apitestka_action")
        assert widget.actions.suggested_filename() == "action.json"

    def test_save_to_file_writes(self, widget, tmp_path):
        widget.input_edit.setPlainText("curl https://x")
        widget.convert()
        target = tmp_path / "out.py"
        with patch(
            "pybreeze.pybreeze_ui.tools_gui.output_actions.QFileDialog.getSaveFileName",
            return_value=(str(target), "Python (*.py)"),
        ):
            result = widget.actions.save_to_file()
        assert result == str(target)
        assert "import requests" in target.read_text(encoding="utf-8")

    def test_save_cancelled_returns_none(self, widget, tmp_path):
        widget.input_edit.setPlainText("curl https://x")
        widget.convert()
        with patch(
            "pybreeze.pybreeze_ui.tools_gui.output_actions.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ):
            assert widget.actions.save_to_file() is None

    def test_save_after_parse_error_is_noop(self, widget):
        widget.input_edit.setPlainText("wget https://x")
        widget.convert()
        assert widget.actions.save_to_file() is None


class TestCurlImportOpenUrlInBuilder:
    def test_button_disabled_before_convert(self, widget):
        assert not widget.open_url_button.isEnabled()

    def test_button_enabled_after_convert(self, widget):
        widget.input_edit.setPlainText("curl https://example.com/api")
        widget.convert()
        assert widget.open_url_button.isEnabled()

    def test_button_disabled_again_after_parse_error(self, widget):
        widget.input_edit.setPlainText("curl https://example.com/api")
        widget.convert()
        widget.input_edit.setPlainText("wget https://example.com")
        widget.convert()
        assert not widget.open_url_button.isEnabled()

    def test_open_url_opens_prefilled_builder_tab(self, widget_with_window):
        from pybreeze.pybreeze_ui.tools_gui.url_builder_gui import UrlBuilderGUI
        gui, window = widget_with_window
        gui.input_edit.setPlainText("curl 'https://example.com/api?a=1' -H 'Accept: */*'")
        gui.convert()
        gui.open_url_in_builder()
        assert len(window.tab_widget.added) == 1
        opened = window.tab_widget.added[0][0]
        assert isinstance(opened, UrlBuilderGUI)
        parsed = json.loads(opened.output_edit.toPlainText())
        assert parsed["host"] == "example.com"
        assert parsed["path"] == "/api"

    def test_query_string_survives_the_hand_off(self, widget_with_window):
        # The curl parser moves a URL's query into params; the builder must still
        # receive the address as curl would send it.
        gui, window = widget_with_window
        gui.input_edit.setPlainText("curl 'https://example.com/api?a=1&b=2'")
        gui.convert()
        gui.open_url_in_builder()
        opened = window.tab_widget.added[0][0]
        assert json.loads(opened.output_edit.toPlainText())["query"] == {"a": "1", "b": "2"}

    def test_open_before_convert_is_noop(self, widget_with_window):
        gui, window = widget_with_window
        assert gui.open_url_in_builder() is None
        assert window.tab_widget.added == []

    def test_open_without_window_is_safe(self, widget):
        widget.input_edit.setPlainText("curl https://example.com/api")
        widget.convert()
        assert widget.open_url_in_builder() is None


class TestCurlImportOpenHeadersInAnalyzer:
    def test_button_disabled_without_headers(self, widget):
        widget.input_edit.setPlainText("curl https://example.com/api")
        widget.convert()
        assert not widget.open_headers_button.isEnabled()

    def test_button_enabled_when_headers_were_parsed(self, widget):
        widget.input_edit.setPlainText("curl https://x -H 'Authorization: Bearer abc'")
        widget.convert()
        assert widget.open_headers_button.isEnabled()

    def test_open_headers_opens_prefilled_analyzer(self, widget_with_window):
        from pybreeze.pybreeze_ui.tools_gui.header_analyzer_gui import HeaderAnalyzerGUI
        gui, window = widget_with_window
        gui.input_edit.setPlainText(
            "curl https://x -H 'Accept: application/json' -H 'X-Trace: 1'")
        gui.convert()
        gui.open_headers_in_analyzer()
        opened = window.tab_widget.added[0][0]
        assert isinstance(opened, HeaderAnalyzerGUI)
        output = opened.output_edit.toPlainText()
        assert "Accept: application/json" in output
        assert "X-Trace: 1" in output

    def test_open_headers_before_convert_is_noop(self, widget_with_window):
        gui, window = widget_with_window
        assert gui.open_headers_in_analyzer() is None
        assert window.tab_widget.added == []

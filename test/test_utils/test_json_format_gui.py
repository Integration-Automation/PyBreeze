"""Tests for the JSON format/minify tool widget."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def widget(app):
    from pybreeze.pybreeze_ui.tools_gui.json_format_gui import JsonFormatGUI
    gui = JsonFormatGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestJsonFormatGUI:
    def test_format_pretty_prints(self, widget):
        widget.input_edit.setPlainText('{"a":1,"b":2}')
        widget.format_json()
        assert "\n" in widget.output_edit.toPlainText()
        assert json.loads(widget.output_edit.toPlainText()) == {"a": 1, "b": 2}

    def test_minify_compacts(self, widget):
        widget.input_edit.setPlainText('{ "a" : 1 }')
        widget.minify()
        assert widget.output_edit.toPlainText() == '{"a":1}'

    def test_invalid_shows_error(self, widget):
        widget.input_edit.setPlainText("{bad}")
        widget.format_json()
        assert widget.output_edit.toPlainText() != ""
        assert "{bad}" not in widget.output_edit.toPlainText()

    def test_empty_shows_hint(self, widget):
        widget.input_edit.setPlainText("   ")
        widget.minify()
        assert widget.output_edit.toPlainText() != ""

    def test_copy_output(self, app, widget):
        widget.input_edit.setPlainText('{"a":1}')
        widget.minify()
        widget.actions.copy()
        assert '{"a":1}' in QApplication.clipboard().text()

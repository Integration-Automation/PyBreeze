"""Tests for the query <-> JSON tool widget."""
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
    from pybreeze.pybreeze_ui.tools_gui.query_json_gui import QueryJsonGUI
    gui = QueryJsonGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestQueryJsonGUI:
    def test_query_to_json(self, widget):
        widget.input_edit.setPlainText("a=1&b=2")
        widget.convert_to_json()
        assert json.loads(widget.output_edit.toPlainText()) == {"a": "1", "b": "2"}

    def test_json_to_query(self, widget):
        widget.input_edit.setPlainText('{"a": "1", "b": "2"}')
        widget.convert_to_query()
        assert widget.output_edit.toPlainText() == "a=1&b=2"

    def test_invalid_json_shows_error(self, widget):
        widget.input_edit.setPlainText("not json")
        widget.convert_to_query()
        assert widget.output_edit.toPlainText() != ""
        assert "a=1" not in widget.output_edit.toPlainText()

    def test_empty_to_json_shows_hint(self, widget):
        widget.input_edit.setPlainText("   ")
        widget.convert_to_json()
        assert widget.output_edit.toPlainText() != ""

    def test_empty_to_query_shows_hint(self, widget):
        widget.input_edit.setPlainText("   ")
        widget.convert_to_query()
        assert widget.output_edit.toPlainText() != ""

    def test_copy_output(self, app, widget):
        widget.input_edit.setPlainText("a=1&b=2")
        widget.convert_to_json()
        widget.actions.copy()
        assert "a" in QApplication.clipboard().text()

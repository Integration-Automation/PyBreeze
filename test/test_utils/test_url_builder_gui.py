"""Tests for the URL parser/builder tool widget."""
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
    from pybreeze.pybreeze_ui.tools_gui.url_builder_gui import UrlBuilderGUI
    gui = UrlBuilderGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestUrlBuilderGUI:
    def test_url_to_json(self, widget):
        widget.input_edit.setPlainText("https://example.com/api?a=1")
        widget.convert_to_json()
        data = json.loads(widget.output_edit.toPlainText())
        assert data["host"] == "example.com"
        assert data["query"] == {"a": "1"}

    def test_json_to_url(self, widget):
        widget.input_edit.setPlainText('{"scheme": "https", "host": "x", "path": "/a"}')
        widget.convert_to_url()
        assert widget.output_edit.toPlainText() == "https://x/a"

    def test_invalid_json_shows_error(self, widget):
        widget.input_edit.setPlainText("not json")
        widget.convert_to_url()
        assert widget.output_edit.toPlainText() != ""
        assert "https://" not in widget.output_edit.toPlainText()

    def test_empty_to_json_shows_hint(self, widget):
        widget.input_edit.setPlainText("   ")
        widget.convert_to_json()
        assert widget.output_edit.toPlainText() != ""

    def test_empty_to_url_shows_hint(self, widget):
        widget.input_edit.setPlainText("   ")
        widget.convert_to_url()
        assert widget.output_edit.toPlainText() != ""

    def test_copy_output(self, app, widget):
        widget.input_edit.setPlainText("https://example.com/api?a=1")
        widget.convert_to_json()
        widget.actions.copy()
        assert "example.com" in QApplication.clipboard().text()


class TestUrlBuilderInitialUrl:
    def test_initial_url_is_parsed_on_open(self, app):
        from pybreeze.pybreeze_ui.tools_gui.url_builder_gui import UrlBuilderGUI
        gui = UrlBuilderGUI(initial_url="https://example.com:8443/api?a=1#frag")
        data = json.loads(gui.output_edit.toPlainText())
        assert data["host"] == "example.com"
        assert data["port"] == 8443
        assert data["fragment"] == "frag"
        gui.close()
        gui.deleteLater()

    def test_initial_url_is_kept_in_the_input(self, app):
        from pybreeze.pybreeze_ui.tools_gui.url_builder_gui import UrlBuilderGUI
        gui = UrlBuilderGUI(initial_url="https://example.com/api")
        assert gui.input_edit.toPlainText() == "https://example.com/api"
        gui.close()
        gui.deleteLater()

    def test_without_initial_url_the_output_stays_empty(self, widget):
        assert widget.output_edit.toPlainText() == ""

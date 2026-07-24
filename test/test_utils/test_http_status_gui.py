"""Tests for the HTTP status reference tool widget."""
from __future__ import annotations

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
    from pybreeze.pybreeze_ui.tools_gui.http_status_gui import HttpStatusGUI
    gui = HttpStatusGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestHttpStatusGUI:
    def test_shows_table_on_open(self, widget):
        assert "200" in widget.output_edit.toPlainText()
        assert "404" in widget.output_edit.toPlainText()

    def test_search_filters(self, widget):
        widget.search_edit.setText("404")
        output = widget.output_edit.toPlainText()
        assert "404 Not Found" in output
        assert "200 OK" not in output

    def test_keyword_search(self, widget):
        widget.search_edit.setText("teapot")
        assert "418" in widget.output_edit.toPlainText()

    def test_no_match_message(self, widget):
        widget.search_edit.setText("zzzzz")
        assert "200" not in widget.output_edit.toPlainText()
        assert widget.output_edit.toPlainText() != ""

    def test_clearing_search_shows_all_again(self, widget):
        widget.search_edit.setText("404")
        widget.search_edit.setText("")
        assert "200" in widget.output_edit.toPlainText()

    def test_build_status_text_empty(self, app):
        from pybreeze.pybreeze_ui.tools_gui.http_status_gui import build_status_text
        assert build_status_text([], "none") == "none"

    def test_initial_search_prefills(self, app):
        from pybreeze.pybreeze_ui.tools_gui.http_status_gui import HttpStatusGUI
        gui = HttpStatusGUI(initial_search="404")
        assert gui.search_edit.text() == "404"
        assert "404 Not Found" in gui.output_edit.toPlainText()
        assert "200 OK" not in gui.output_edit.toPlainText()
        gui.close()
        gui.deleteLater()

    def test_has_output_actions(self, widget):
        # The reference table is always content, so save/copy operate on it.
        assert widget.actions.suggested_filename() == "http_status.txt"
        widget.actions.copy()
        assert "200 OK" in QApplication.clipboard().text()

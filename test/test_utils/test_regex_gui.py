"""Tests for the regex tester tool widget."""
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
    from pybreeze.pybreeze_ui.tools_gui.regex_gui import RegexGUI
    gui = RegexGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestRegexGUI:
    def test_finds_matches(self, widget):
        widget.pattern_edit.setText(r"\d+")
        widget.text_edit.setPlainText("a1 b22")
        widget.test()
        output = widget.output_edit.toPlainText()
        assert "'1'" in output
        assert "'22'" in output

    def test_no_match_message(self, widget):
        widget.pattern_edit.setText(r"z")
        widget.text_edit.setPlainText("abc")
        widget.test()
        assert widget.output_edit.toPlainText() != ""
        assert "'z'" not in widget.output_edit.toPlainText()

    def test_invalid_pattern_shows_error(self, widget):
        widget.pattern_edit.setText("(")
        widget.text_edit.setPlainText("abc")
        widget.test()
        assert widget.output_edit.toPlainText() != ""

    def test_ignorecase_flag_used(self, widget):
        widget.pattern_edit.setText("abc")
        widget.text_edit.setPlainText("ABC")
        widget.flag_checkboxes["IGNORECASE"].setChecked(True)
        widget.test()
        assert "'ABC'" in widget.output_edit.toPlainText()
        widget.flag_checkboxes["IGNORECASE"].setChecked(False)

    def test_selected_flags(self, widget):
        widget.flag_checkboxes["DOTALL"].setChecked(True)
        assert "DOTALL" in widget.selected_flags()
        widget.flag_checkboxes["DOTALL"].setChecked(False)

    def test_copy_output(self, app, widget):
        widget.pattern_edit.setText(r"\d+")
        widget.text_edit.setPlainText("a1")
        widget.test()
        widget.actions.copy()
        assert "'1'" in QApplication.clipboard().text()

    def test_build_matches_text_no_matches(self, app):
        from pybreeze.pybreeze_ui.tools_gui.regex_gui import build_matches_text
        assert build_matches_text([], "none") == "none"

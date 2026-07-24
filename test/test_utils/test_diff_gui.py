"""Tests for the text diff tool widget."""
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
    from pybreeze.pybreeze_ui.tools_gui.diff_gui import DiffGUI
    gui = DiffGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestDiffGUI:
    def test_shows_diff(self, widget):
        widget.left_edit.setPlainText("a\nb")
        widget.right_edit.setPlainText("a\nc")
        widget.compare()
        output = widget.output_edit.toPlainText()
        assert "-b" in output
        assert "+c" in output

    def test_identical_summary(self, widget):
        widget.left_edit.setPlainText("same")
        widget.right_edit.setPlainText("same")
        widget.compare()
        assert widget.summary_label.text() != ""
        assert widget.output_edit.toPlainText() == ""

    def test_summary_counts(self, widget):
        widget.left_edit.setPlainText("a")
        widget.right_edit.setPlainText("a\nb")
        widget.compare()
        # The summary mentions one added line.
        assert "1" in widget.summary_label.text()

    def test_copy_output(self, app, widget):
        widget.left_edit.setPlainText("a")
        widget.right_edit.setPlainText("b")
        widget.compare()
        widget.actions.copy()
        assert QApplication.clipboard().text() != ""

    def test_build_summary_line_identical(self, app):
        from pybreeze.pybreeze_ui.tools_gui.diff_gui import build_summary_line
        from pybreeze.utils.diff_tools.text_diff import DiffSummary
        text = build_summary_line(DiffSummary(added=0, removed=0, is_equal=True))
        assert text != ""

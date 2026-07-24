"""Tests for the timestamp converter tool widget."""
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
    from pybreeze.pybreeze_ui.tools_gui.timestamp_gui import TimestampGUI
    gui = TimestampGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestTimestampGUI:
    def test_convert_epoch(self, widget):
        widget.input_edit.setText("1609459200")
        widget.convert()
        output = widget.output_edit.toPlainText()
        assert "1609459200" in output
        assert "2021-01-01T00:00:00" in output

    def test_convert_iso(self, widget):
        widget.input_edit.setText("2021-01-01T00:00:00Z")
        widget.convert()
        assert "1609459200" in widget.output_edit.toPlainText()

    def test_invalid_shows_error(self, widget):
        widget.input_edit.setText("nope")
        widget.convert()
        assert "1609459200" not in widget.output_edit.toPlainText()
        assert widget.output_edit.toPlainText() != ""

    def test_empty_shows_hint(self, widget):
        widget.input_edit.setText("   ")
        widget.convert()
        assert widget.output_edit.toPlainText() != ""

    def test_copy_output(self, app, widget):
        widget.input_edit.setText("1609459200")
        widget.convert()
        widget.actions.copy()
        assert "1609459200" in QApplication.clipboard().text()

    def test_save_after_error_is_noop(self, widget, tmp_path):
        # A failed conversion shows an error; open/save must not act on it.
        from unittest.mock import patch
        widget.input_edit.setText("not-a-timestamp")
        widget.convert()
        with patch(
            "pybreeze.pybreeze_ui.tools_gui.output_actions.QFileDialog.getSaveFileName",
            return_value=(str(tmp_path / "x.txt"), "Text (*.txt)"),
        ):
            assert widget.actions.save_to_file() is None

    def test_suggested_filename(self, widget):
        assert widget.actions.suggested_filename() == "timestamp.txt"

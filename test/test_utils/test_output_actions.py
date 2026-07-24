"""Tests for the reusable output actions (copy / open-in-editor / save)."""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QTextEdit, QWidget

from pybreeze.extend_multi_language.update_language_dict import update_language_dict


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


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
    def __init__(self, _main_window):
        self.code_edit = type(
            "CodeEdit", (), {"setPlainText": lambda self, t: setattr(self, "text", t)})()


def _make(app, main_window=None, **kwargs):
    from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
    parent = QWidget()
    output = QTextEdit(parent)
    output.setReadOnly(True)
    actions = OutputActions(parent, output, main_window=main_window, **kwargs)
    return parent, output, actions


class TestCopy:
    def test_copies_text(self, app):
        parent, output, actions = _make(app)
        output.setPlainText("hello")
        actions.copy()
        assert QApplication.clipboard().text() == "hello"
        parent.deleteLater()

    def test_empty_is_safe(self, app):
        parent, output, actions = _make(app)
        output.setPlainText("")
        actions.copy()  # must not raise
        parent.deleteLater()


class TestOpenInEditor:
    def test_opens_tab_with_text(self, app):
        window = _FakeMainWindow()
        parent, output, actions = _make(app, main_window=window)
        output.setPlainText("some code")
        with patch(
            "je_editor.pyside_ui.main_ui.editor.editor_widget.EditorWidget", _FakeEditor
        ):
            editor = actions.open_in_editor()
        assert editor.code_edit.text == "some code"
        assert len(window.tab_widget.added) == 1
        parent.deleteLater()

    def test_no_window_is_safe(self, app):
        parent, output, actions = _make(app)
        output.setPlainText("code")
        assert actions.open_in_editor() is None
        parent.deleteLater()

    def test_empty_output_is_noop(self, app):
        window = _FakeMainWindow()
        parent, output, actions = _make(app, main_window=window)
        output.setPlainText("   ")
        assert actions.open_in_editor() is None
        assert window.tab_widget.added == []
        parent.deleteLater()

    def test_is_valid_false_blocks_open(self, app):
        window = _FakeMainWindow()
        parent, output, actions = _make(app, main_window=window, is_valid=lambda: False)
        output.setPlainText("looks like content")
        assert actions.open_in_editor() is None
        parent.deleteLater()


class TestSaveToFile:
    def test_writes_file(self, app, tmp_path):
        parent, output, actions = _make(app, basename="thing", extension="txt")
        output.setPlainText("saved content")
        target = tmp_path / "out.txt"
        with patch(
            "pybreeze.pybreeze_ui.tools_gui.output_actions.QFileDialog.getSaveFileName",
            return_value=(str(target), "Text (*.txt)"),
        ):
            result = actions.save_to_file()
        assert result == str(target)
        assert target.read_text(encoding="utf-8") == "saved content"
        parent.deleteLater()

    def test_cancel_returns_none(self, app, tmp_path):
        parent, output, actions = _make(app)
        output.setPlainText("content")
        with patch(
            "pybreeze.pybreeze_ui.tools_gui.output_actions.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ):
            assert actions.save_to_file() is None
        parent.deleteLater()

    def test_empty_output_is_noop(self, app):
        parent, output, actions = _make(app)
        output.setPlainText("")
        assert actions.save_to_file() is None
        parent.deleteLater()


class TestSuggestedFilename:
    def test_static(self, app):
        parent, _output, actions = _make(app, basename="report", extension="json")
        assert actions.suggested_filename() == "report.json"
        parent.deleteLater()

    def test_callable(self, app):
        parent, _output, actions = _make(
            app, basename=lambda: "dyn", extension=lambda: "py")
        assert actions.suggested_filename() == "dyn.py"
        parent.deleteLater()

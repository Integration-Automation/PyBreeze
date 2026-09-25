"""AutoControl's Record Stop: recording stops from any tab, and what it gives back can be run."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QPlainTextEdit, QTabWidget, QWidget

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.automation_menu.auto_control_menu import build_autocontrol_menu as record_menu

_RECORDED = [["AC_type_keyboard", {"keycode": 65}],
             ["mouse_left", {"mouse_keycode": "mouse_left", "x": 10, "y": 20}]]


class EditorTab(QWidget):
    """Stands in for a JEditor editor tab."""

    def __init__(self) -> None:
        super().__init__()
        self.code_edit = QPlainTextEdit()


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def window(app, monkeypatch):
    monkeypatch.setattr(record_menu, "EditorWidget", EditorTab)
    made = QMainWindow()
    made.tab_widget = QTabWidget()
    made.told = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: made.told.append(a[2])))
    yield made
    made.deleteLater()


def _recording(monkeypatch, actions) -> list:
    stopped: list = []

    def stop():
        stopped.append(True)
        return actions

    monkeypatch.setattr(record_menu.je_auto_control, "stop_record", stop)
    return stopped


def test_the_recording_goes_in_as_json_the_runner_reads(window, monkeypatch):
    _recording(monkeypatch, _RECORDED)
    tab = EditorTab()
    window.tab_widget.addTab(tab, "script.json")

    record_menu.stop_record(window)

    # It went in as str(list): single quotes, which json.loads refuses.
    assert json.loads(tab.code_edit.toPlainText()) == _RECORDED


def test_recording_stops_whatever_tab_is_in_front(window, monkeypatch):
    stopped = _recording(monkeypatch, _RECORDED)
    window.tab_widget.addTab(QWidget(), "a tool tab")

    record_menu.stop_record(window)

    # From a tool tab it used to stop nothing, and the hooks kept recording.
    assert stopped == [True]
    assert json.loads(QApplication.clipboard().text()) == _RECORDED
    assert window.told


@pytest.mark.parametrize("nothing", [None, []])
def test_nothing_recorded_says_so_and_inserts_nothing(window, monkeypatch, nothing):
    _recording(monkeypatch, nothing)
    tab = EditorTab()
    window.tab_widget.addTab(tab, "script.json")

    record_menu.stop_record(window)

    # It used to insert the text "None".
    assert tab.code_edit.toPlainText() == ""
    assert window.told

"""AutoControl's Record Stop: recording stops from any tab, and what it gives back can be run."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import je_auto_control
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

    monkeypatch.setattr(je_auto_control, "stop_record", stop)
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


class TestTheMenu:
    """The entries that reach AutoControl import it only when chosen (see test_startup_imports.py)."""

    @staticmethod
    def _menu(window) -> dict[str, object]:
        from PySide6.QtWidgets import QMenu

        window.automation_menu = QMenu()
        record_menu.set_autocontrol_menu(window)
        (autocontrol,) = [action.menu() for action in window.automation_menu.actions()]
        entries = {}
        for action in autocontrol.actions():
            entries[action.text()] = action
            if action.menu() is not None:
                entries.update({sub.text(): sub for sub in action.menu().actions()})
        return entries

    def test_record_starts_autocontrol_recording(self, window, monkeypatch):
        from je_editor import language_wrapper

        started: list = []
        monkeypatch.setattr(je_auto_control, "record", lambda: started.append(True))

        self._menu(window)[language_wrapper.language_word_dict.get("autocontrol_record_start_label")].trigger()

        assert started == [True]

    def test_the_gui_entry_opens_autocontrols_gui_in_a_tab(self, window, monkeypatch):
        from je_auto_control.gui import main_widget

        class AutoControlGUI(QWidget):
            """Stands in for AutoControl's own GUI."""

        monkeypatch.setattr(main_widget, "AutoControlGUIWidget", AutoControlGUI)

        self._menu(window)["AutoControl GUI"].trigger()

        assert isinstance(window.tab_widget.widget(0), AutoControlGUI)
        assert window.tab_widget.tabText(0) == "AutoControl GUI"

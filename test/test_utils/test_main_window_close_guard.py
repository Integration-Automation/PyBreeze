"""Closing the IDE: one tab, dock or run window that raises on close does not stop the rest."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget

from pybreeze.pybreeze_ui.editor_main import main_ui
from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow, _close_guarded


class Refusing(QWidget):
    def close(self) -> bool:
        raise RuntimeError("a third-party tab that fails to close")


class Recording(QWidget):
    def __init__(self, closed: list) -> None:
        super().__init__()
        self._closed = closed

    def close(self) -> bool:
        self._closed.append(self)
        return super().close()


def test_a_failing_step_is_logged_and_the_next_still_runs(monkeypatch):
    QApplication.instance() or QApplication([])
    logged: list = []
    monkeypatch.setattr(main_ui.pybreeze_logger, "error", lambda *args: logged.append(args))
    ran: list = []

    def fail():
        raise OSError("the run's child could not be stopped")

    _close_guarded(QWidget(), fail, lambda: ran.append("close"))

    assert ran == ["close"]
    assert logged


def test_every_other_tool_tab_is_still_closed(monkeypatch):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(main_ui.pybreeze_logger, "error", lambda *args: None)
    window = QMainWindow()
    window.tab_widget = QTabWidget()
    closed: list = []
    before, after = Recording(closed), Recording(closed)
    for tab in (before, Refusing(), after):
        window.tab_widget.addTab(tab, "tool")

    # It used to raise here, and JEditor's own close -- open files, settings,
    # auto-save threads -- never ran.
    PyBreezeMainWindow._close_tool_tabs_and_docks(window)

    assert before in closed and after in closed
    window.deleteLater()

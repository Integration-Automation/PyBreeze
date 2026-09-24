"""prthinker's Review current file: the file is saved before the review reads it from disk."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget

from pybreeze.pybreeze_ui.menu.automation_menu.prthinker_menu import build_prthinker_menu as menu


class EditorTab(QWidget):
    """Stands in for a JEditor editor tab."""


@pytest.fixture()
def window(monkeypatch):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(menu, "EditorWidget", EditorTab)
    made = QMainWindow()
    made.tab_widget = QTabWidget()
    made.events = []
    monkeypatch.setattr(menu, "_tell", lambda _window, key: made.events.append(("told", key)))
    monkeypatch.setattr(
        menu, "review_current_file", lambda _window: made.events.append("reviewed") or True)
    yield made
    made.deleteLater()


def test_the_file_is_saved_before_it_is_reviewed(window, monkeypatch):
    window.tab_widget.addTab(EditorTab(), "main.py")
    monkeypatch.setattr(
        menu, "save_current_file_for_run", lambda _window: window.events.append("saved") or "main.py")

    menu._review_current_file(window)

    # The review reads the file on disk; unsaved edits used to be left out.
    assert window.events == ["saved", "reviewed"]


def test_a_save_that_did_not_happen_reviews_nothing(window, monkeypatch):
    window.tab_widget.addTab(EditorTab(), "untitled")
    monkeypatch.setattr(menu, "save_current_file_for_run", lambda _window: None)

    menu._review_current_file(window)

    # Cancelled, or failed and already reported: nothing more to say.
    assert window.events == []


def test_a_tab_that_is_not_an_editor_says_what_is_needed(window, monkeypatch):
    window.tab_widget.addTab(QWidget(), "a tool tab")
    monkeypatch.setattr(menu, "save_current_file_for_run", lambda _window: None)

    menu._review_current_file(window)

    assert window.events == [("told", "prthinker_need_saved_file_message")]

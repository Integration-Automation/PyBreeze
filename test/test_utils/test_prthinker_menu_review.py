"""prthinker's Review current file: the file is saved before the review reads it from disk."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget

from pybreeze.pybreeze_ui.menu.automation_menu.prthinker_menu import build_prthinker_menu as menu


class EditorTab(QWidget):
    """Stands in for a JEditor editor tab."""


@pytest.fixture
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


class TestReviewAPullRequest:
    @staticmethod
    def _answer(monkeypatch, number: int, chosen: bool) -> list:
        asked: list = []

        def get_int(*args):
            asked.append(args[3:])  # the value it starts at, the lowest and the highest
            return number, chosen

        monkeypatch.setattr(menu.QInputDialog, "getInt", staticmethod(get_int))
        return asked

    def test_the_number_asked_for_is_reviewed(self, window, monkeypatch):
        asked = self._answer(monkeypatch, 42, True)
        monkeypatch.setattr(
            menu, "review_pull_request", lambda _window, number: window.events.append(number) or True)

        menu._review_pull_request(window)

        assert window.events == [42]
        assert asked == [(1, 1, 1000000)]

    def test_cancelling_the_question_reviews_nothing(self, window, monkeypatch):
        self._answer(monkeypatch, 1, False)
        monkeypatch.setattr(
            menu, "review_pull_request", lambda _window, number: window.events.append(number) or True)

        menu._review_pull_request(window)

        assert window.events == []

    def test_without_a_repository_set_it_says_so(self, window, monkeypatch):
        self._answer(monkeypatch, 7, True)
        monkeypatch.setattr(menu, "review_pull_request", lambda _window, _number: False)

        menu._review_pull_request(window)

        assert window.events == [("told", "prthinker_need_repository_message")]


class TestTheMenu:
    def test_its_entries_and_what_they_open(self, window, monkeypatch):
        from PySide6.QtWidgets import QMenu

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict

        update_language_dict()
        window.automation_menu = QMenu()
        opened: list = []
        monkeypatch.setattr(menu, "open_web_browser", lambda _window, url, _title: opened.append(url))
        monkeypatch.setattr(menu, "_open_setting", lambda _window: opened.append("settings"))

        menu.set_prthinker_menu(window)
        window.prthinker_setting_action.trigger()
        window.prthinker_doc_action.trigger()
        window.prthinker_github_action.trigger()

        labels = [action.text() for action in window.prthinker_menu.actions()]
        assert labels == ["Review the current file", "Review a Pull Request", "Settings", "Help"]
        assert opened == ["settings", menu.DOCUMENT_URL, menu.GITHUB_URL]
        window.automation_menu.deleteLater()

    def test_the_settings_open_as_a_dialog_of_the_window(self, window, monkeypatch):
        shown: list = []

        class Dialog:
            def __init__(self, parent):
                shown.append(parent)

            def setAttribute(self, *_args):
                shown.append("deleted on close")

            def exec(self):
                shown.append("shown")

        monkeypatch.setattr(menu, "PRThinkerSettingDialog", Dialog)

        menu._open_setting(window)

        assert shown == [window, "deleted on close", "shown"]

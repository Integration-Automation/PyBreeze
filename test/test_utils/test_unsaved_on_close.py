"""Closing a tab or the IDE, or opening another diagram, asks before unsaved edits are lost.

JEditor's close_tab asked about its own editor tabs only and closed every other
tab whatever it said, so a prompt or a diagram being edited was lost unasked.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from pybreeze.extend_multi_language.update_language_dict import update_language_dict


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def answers(monkeypatch):
    """Answer every question with ``answers["reply"]`` and count them."""
    state = {"reply": QMessageBox.StandardButton.No, "asked": 0}

    def question(*_args, **_kwargs):
        state["asked"] += 1
        return state["reply"]

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return state


class TestTheDiagramEditor:
    def _editor(self):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import DiagramEditorWidget
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode

        editor = DiagramEditorWidget()
        with editor._scene.undo_scope("Add"):
            editor._scene.addItem(DiagramNode(x=0, y=0))
        return editor

    def test_an_unchanged_diagram_closes_without_a_question(self, app, answers):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import DiagramEditorWidget

        assert DiagramEditorWidget().may_close() is True
        assert answers["asked"] == 0

    def test_an_unsaved_change_is_asked_about(self, app, answers):
        editor = self._editor()

        assert editor.may_close() is False
        answers["reply"] = QMessageBox.StandardButton.Yes
        assert editor.may_close() is True
        assert answers["asked"] == 2

    def test_a_saved_diagram_closes_without_a_question(self, app, answers, tmp_path):
        editor = self._editor()
        editor._write_json(tmp_path / "saved.diagram.json")

        assert editor.may_close() is True
        assert answers["asked"] == 0

    @staticmethod
    def _offer(monkeypatch, path):
        from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget

        chosen: list = []

        def dialog(*_args, **_kwargs):
            chosen.append(path)
            return str(path), ""

        monkeypatch.setattr(diagram_editor_widget.QFileDialog, "getOpenFileName", staticmethod(dialog))
        return chosen

    def test_opening_another_diagram_asks_before_unsaved_changes_go(self, app, answers, tmp_path, monkeypatch):
        # Open replaced the canvas and cleared the undo history: the edits were
        # gone without a word and could not be undone.
        other = tmp_path / "other.diagram.json"
        self._editor()._write_json(other)
        editor = self._editor()
        editor._current_path = tmp_path / "work.diagram.json"
        chosen = self._offer(monkeypatch, other)

        editor._open_diagram()

        assert answers["asked"] == 1
        assert chosen == [], "the file dialog opened after No"
        assert editor._current_path == tmp_path / "work.diagram.json"
        assert not editor._scene.undo_stack.isClean(), "the edits were dropped"

    def test_yes_lets_the_other_diagram_open(self, app, answers, tmp_path, monkeypatch):
        other = tmp_path / "other.diagram.json"
        self._editor()._write_json(other)
        editor = self._editor()
        answers["reply"] = QMessageBox.StandardButton.Yes
        self._offer(monkeypatch, other)

        editor._open_diagram()

        assert answers["asked"] == 1
        assert editor._current_path == other

    def test_a_diagram_with_nothing_unsaved_opens_another_unasked(self, app, answers, tmp_path, monkeypatch):
        other = tmp_path / "other.diagram.json"
        self._editor()._write_json(other)
        editor = self._editor()
        editor._write_json(tmp_path / "saved.diagram.json")
        self._offer(monkeypatch, other)

        editor._open_diagram()

        assert answers["asked"] == 0
        assert editor._current_path == other


    def test_a_new_diagram_after_a_save_starts_unasked(self, app, answers, tmp_path):
        # New asked "Discard current diagram?" whenever the canvas had anything
        # on it, a diagram just saved included, where Open and Close ask only
        # about unsaved changes
        editor = self._editor()
        editor._write_json(tmp_path / "saved.diagram.json")

        editor._new_diagram()

        assert answers["asked"] == 0
        assert editor._scene.get_all_nodes() == []
        assert editor._current_path is None

    def test_a_new_diagram_asks_before_unsaved_changes_go(self, app, answers):
        editor = self._editor()

        editor._new_diagram()

        assert answers["asked"] == 1
        assert len(editor._scene.get_all_nodes()) == 1, "the edits were dropped after No"
        answers["reply"] = QMessageBox.StandardButton.Yes
        editor._new_diagram()
        assert editor._scene.get_all_nodes() == []
        assert editor._scene.undo_stack.isClean()


class TestThePromptEditor:
    def test_unsaved_edits_are_asked_about(self, app, answers, tmp_path, monkeypatch):
        from pybreeze.pybreeze_ui.extend_ai_gui import prompt_store
        from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_prompt_editor_widget import CoTPromptEditor

        monkeypatch.setattr(prompt_store, "pybreeze_data_path", lambda: tmp_path)
        editor = CoTPromptEditor()
        assert editor.may_close() is True

        editor.middle_editor.document().setModified(True)

        assert editor.may_close() is False
        assert answers["asked"] == 1


class TestTheMainWindowsQuestion:
    def test_a_widget_without_the_question_may_close(self):
        from pybreeze.pybreeze_ui.closing import may_close

        assert may_close(object()) is True
        assert may_close(None) is True

    def test_a_widget_whose_question_raises_does_not_keep_the_ide_open(self):
        from pybreeze.pybreeze_ui.closing import may_close

        class Broken:
            @staticmethod
            def may_close() -> bool:
                raise RuntimeError("third-party tab")

        assert may_close(Broken()) is True

    def test_a_no_is_a_no(self):
        from pybreeze.pybreeze_ui.closing import may_close

        class Keeps:
            @staticmethod
            def may_close() -> bool:
                return False

        assert may_close(Keeps()) is False


class _Answering:
    """Stands in for a tool tab with unsaved work: ``may_close()`` gives *answer*."""

    def __init__(self, answer: bool) -> None:
        from PySide6.QtWidgets import QWidget

        self.widget = QWidget()
        self.widget.may_close = lambda: answer


def _window(*answers: bool):
    """A main window's stand-in holding one tab per answer."""
    from PySide6.QtWidgets import QMainWindow, QTabWidget

    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

    window = QMainWindow()
    window.tab_widget = QTabWidget()
    window._tool_tabs_may_close = lambda: PyBreezeMainWindow._tool_tabs_may_close(window)
    for answer in answers:
        window.tab_widget.addTab(_Answering(answer).widget, "tool")
    return window


def _dock(window, answer: bool):
    """An asking dock on *window* whose widget answers *answer*."""
    from PySide6.QtCore import Qt

    from pybreeze.pybreeze_ui.closing import AskingDock

    dock = AskingDock()
    dock.setWidget(_Answering(answer).widget)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    return dock


class TestTheMainWindow:
    def test_a_tab_the_user_keeps_is_not_closed(self, app):
        from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

        window = _window(False)

        PyBreezeMainWindow.close_tab(window, 0)

        assert window.tab_widget.count() == 1
        window.deleteLater()

    def test_a_no_from_one_tab_keeps_the_ide_open(self, app):
        from PySide6.QtGui import QCloseEvent

        from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

        window = _window(True, False)
        event = QCloseEvent()

        PyBreezeMainWindow.closeEvent(window, event)

        assert not event.isAccepted()
        assert window.tab_widget.count() == 2
        window.deleteLater()

    def test_docks_are_marked_as_asked_only_when_all_agree(self, app):
        from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

        for tab_answer, marked in ((False, False), (True, True)):
            window = _window(tab_answer)
            dock = _dock(window, True)

            assert PyBreezeMainWindow._tool_tabs_may_close(window) is tab_answer
            # Marked, the dock does not ask again as the IDE closes it
            assert dock.already_asked is marked
            window.deleteLater()

    def test_a_docked_widget_is_asked_too(self, app):
        from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

        window = _window(True)
        _dock(window, False)

        assert PyBreezeMainWindow._tool_tabs_may_close(window) is False
        window.deleteLater()


class TestADock:
    """A docked editor closed from its dock's own button, without a word."""

    def test_a_dock_whose_widget_says_no_stays_open(self, app):
        from pybreeze.pybreeze_ui.closing import AskingDock

        dock = AskingDock()
        dock.setWidget(_Answering(False).widget)
        dock.show()

        assert dock.close() is False
        assert dock.isVisible()
        dock.already_asked = True
        assert dock.close() is True

    def test_a_dock_whose_widget_agrees_closes(self, app):
        from pybreeze.pybreeze_ui.closing import AskingDock

        dock = AskingDock()
        dock.setWidget(_Answering(True).widget)
        dock.show()

        assert dock.close() is True

    def test_the_dock_menu_builds_docks_that_ask(self, app):
        import inspect

        from pybreeze.pybreeze_ui.menu.tools import tools_menu

        assert "AskingDock()" in inspect.getsource(tools_menu.add_dock)


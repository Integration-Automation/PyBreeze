"""Closing a tab or the IDE asks before unsaved prompt or diagram edits are lost.

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


@pytest.fixture()
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
    def test_a_widget_without_may_close_may_close(self):
        from pybreeze.pybreeze_ui.editor_main.main_ui import _may_close

        assert _may_close(object()) is True
        assert _may_close(None) is True

    def test_a_widget_whose_question_raises_does_not_keep_the_ide_open(self):
        from pybreeze.pybreeze_ui.editor_main.main_ui import _may_close

        class Broken:
            @staticmethod
            def may_close() -> bool:
                raise RuntimeError("third-party tab")

        assert _may_close(Broken()) is True

    def test_a_no_is_a_no(self):
        from pybreeze.pybreeze_ui.editor_main.main_ui import _may_close

        class Keeps:
            @staticmethod
            def may_close() -> bool:
                return False

        assert _may_close(Keeps()) is False

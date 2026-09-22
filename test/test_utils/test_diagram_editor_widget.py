"""The diagram editor's own file handling: what opening and saving do to files on disk."""
from __future__ import annotations

import json
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
def editor(app):
    from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import DiagramEditorWidget

    widget = DiagramEditorWidget()
    yield widget
    widget.deleteLater()


_A_DIAGRAM = {
    "nodes": [{"id": 0, "x": 0, "y": 0, "w": 100, "h": 60, "text": "A", "shape": "RECTANGLE"}],
    "connections": [],
    "images": [],
}


class TestSaving:
    def test_a_save_that_fails_leaves_the_last_good_file(self, editor, tmp_path, monkeypatch):
        from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget

        target = tmp_path / "keep.diagram.json"
        target.write_text(json.dumps(_A_DIAGRAM), encoding="utf-8")
        editor._scene.load_from_dict(_A_DIAGRAM)
        monkeypatch.setattr(
            diagram_editor_widget.QMessageBox, "warning",
            staticmethod(lambda *args, **kwargs: None))

        def refuse(*_args, **_kwargs):
            raise OSError("no room on the disk")

        monkeypatch.setattr(diagram_editor_widget.os, "replace", refuse)
        editor._write_json(target)

        assert json.loads(target.read_text(encoding="utf-8")) == _A_DIAGRAM
        assert list(tmp_path.iterdir()) == [target], "a half-written file was left behind"

    def test_a_save_writes_the_diagram(self, editor, tmp_path):
        target = tmp_path / "out.diagram.json"
        editor._scene.load_from_dict(_A_DIAGRAM)

        editor._write_json(target)

        stored = json.loads(target.read_text(encoding="utf-8"))
        assert [node["text"] for node in stored["nodes"]] == ["A"]


class TestOpening:
    def test_a_file_that_is_not_a_diagram_leaves_the_canvas_alone(
            self, editor, tmp_path, monkeypatch):
        from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget

        editor._scene.load_from_dict(_A_DIAGRAM)
        editor._current_path = tmp_path / "work.diagram.json"
        editor._current_path.write_text(json.dumps(_A_DIAGRAM), encoding="utf-8")
        other = tmp_path / "other.diagram.json"
        other.write_text(json.dumps([1, 2]), encoding="utf-8")
        said: list = []
        monkeypatch.setattr(
            diagram_editor_widget.QFileDialog, "getOpenFileName",
            staticmethod(lambda *args, **kwargs: (str(other), "")))
        monkeypatch.setattr(
            diagram_editor_widget.QMessageBox, "warning",
            staticmethod(lambda *args, **kwargs: said.append(args)))

        editor._open_diagram()

        assert said, "the user was told nothing"
        assert [n.text() for n in editor._scene.get_all_nodes()] == ["A"]
        # The next save must still go to the file that is open, unharmed.
        editor._write_json(editor._current_path)
        assert json.loads(editor._current_path.read_text(encoding="utf-8"))["nodes"]

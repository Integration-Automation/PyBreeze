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
        from pybreeze.utils.file_process import replace_file

        target = tmp_path / "keep.diagram.json"
        target.write_text(json.dumps(_A_DIAGRAM), encoding="utf-8")
        editor._scene.load_from_dict(_A_DIAGRAM)
        monkeypatch.setattr(
            diagram_editor_widget.QMessageBox, "warning",
            staticmethod(lambda *args, **kwargs: None))

        def refuse(*_args, **_kwargs):
            raise OSError("no room on the disk")

        monkeypatch.setattr(replace_file.os, "replace", refuse)
        editor._write_json(target)

        assert json.loads(target.read_text(encoding="utf-8")) == _A_DIAGRAM
        assert list(tmp_path.iterdir()) == [target], "a half-written file was left behind"

    def test_a_save_writes_the_diagram(self, editor, tmp_path):
        target = tmp_path / "out.diagram.json"
        editor._scene.load_from_dict(_A_DIAGRAM)

        editor._write_json(target)

        stored = json.loads(target.read_text(encoding="utf-8"))
        assert [node["text"] for node in stored["nodes"]] == ["A"]

    def test_save_as_has_a_button(self, editor, tmp_path, monkeypatch):
        # Only Ctrl+Shift+S reached it: once saved, a diagram had no way to a
        # new file from the toolbar
        from PySide6.QtWidgets import QPushButton

        from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget
        from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import _lang

        first, second = tmp_path / "first.diagram.json", tmp_path / "second.diagram.json"
        editor._scene.load_from_dict(_A_DIAGRAM)
        editor._current_path = first
        monkeypatch.setattr(
            diagram_editor_widget.QFileDialog, "getSaveFileName",
            staticmethod(lambda *args, **kwargs: (str(second), "")))
        button = next(button for button in editor.findChildren(QPushButton)
                      if button.text() == _lang("diagram_editor_action_save_as"))

        button.click()

        assert second.is_file() and not first.exists()
        assert editor._current_path == second


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


class TestShortcuts:
    def test_every_shortcut_applies_only_while_the_editor_has_focus(self, editor):
        # Opened as a dock, the editor shares the window with the code editor;
        # window-wide, its Ctrl+D or Ctrl+Z took over, or collided with, the code
        # editor's own.
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QShortcut

        shortcuts = editor.findChildren(QShortcut)

        assert len(shortcuts) >= 11
        assert {shortcut.context() for shortcut in shortcuts} == {
            Qt.ShortcutContext.WidgetWithChildrenShortcut}


class TestExporting:
    """An export replaces the chosen file only once the new one is whole."""

    def _export(self, editor, monkeypatch, target, kind: str) -> list:
        from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget

        warned: list = []
        monkeypatch.setattr(diagram_editor_widget.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *args, **kwargs: (str(target), "")))
        monkeypatch.setattr(diagram_editor_widget.QMessageBox, "warning",
                            staticmethod(lambda *args, **kwargs: warned.append(args)))
        editor._scene.load_from_dict(_A_DIAGRAM)
        getattr(editor, f"_export_{kind}")()
        return warned

    def test_a_png_export_writes_a_png(self, editor, tmp_path, monkeypatch):
        target = tmp_path / "diagram.png"

        assert self._export(editor, monkeypatch, target, "png") == []

        assert target.read_bytes().startswith(b"\x89PNG")
        assert list(tmp_path.iterdir()) == [target]

    def test_an_svg_export_writes_an_svg(self, editor, tmp_path, monkeypatch):
        target = tmp_path / "diagram.svg"

        assert self._export(editor, monkeypatch, target, "svg") == []

        assert "<svg" in target.read_text(encoding="utf-8")
        assert list(tmp_path.iterdir()) == [target]

    def test_a_png_export_draws_the_canvas_where_it_is(self, editor, tmp_path, monkeypatch):
        # The painter was scaled and moved, then rendered to the device's whole
        # rect: the scene came out shifted and shrunk, a node away from the
        # origin only a corner of red
        from PySide6.QtGui import QColor, QImage

        from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget

        target = tmp_path / "diagram.png"
        monkeypatch.setattr(diagram_editor_widget.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *args, **kwargs: (str(target), "")))
        editor._scene.load_from_dict({"nodes": [{
            "id": 0, "x": 500, "y": 300, "w": 200, "h": 100, "text": "",
            "shape": "RECTANGLE", "fill_color": "#ff0000", "border_color": "#ff0000"}]})

        editor._export_png()

        image = QImage(str(target))
        red = [QColor(image.pixel(x, y)).red() > 200 and QColor(image.pixel(x, y)).green() < 60
               for x, y in ((image.width() // 2, image.height() // 2),
                            (image.width() // 4, image.height() // 2),
                            (image.width() * 3 // 4, image.height() // 2))]
        assert red == [True, True, True]
        assert QColor(image.pixel(5, 5)).name() == "#ffffff"

    def test_an_svg_export_views_the_canvas_where_it_is(self, editor, tmp_path, monkeypatch):
        # Rendered the same way, the node sat outside the SVG's view box
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer

        from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget

        target = tmp_path / "diagram.svg"
        monkeypatch.setattr(diagram_editor_widget.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *args, **kwargs: (str(target), "")))
        editor._scene.load_from_dict({"nodes": [{
            "id": 0, "x": 500, "y": 300, "w": 200, "h": 100, "text": "",
            "shape": "RECTANGLE", "fill_color": "#ff0000", "border_color": "#ff0000"}]})

        editor._export_svg()

        renderer = QSvgRenderer(str(target))
        image = QImage(renderer.defaultSize(), QImage.Format.Format_ARGB32)
        image.fill(0xFFFFFFFF)
        painter = QPainter(image)
        renderer.render(painter, QRectF(0, 0, image.width(), image.height()))
        painter.end()
        middle = QColor(image.pixel(image.width() // 2, image.height() // 2))
        assert middle.red() > 200 and middle.green() < 60

    @pytest.mark.parametrize("kind", ["png", "svg"])
    def test_an_export_that_fails_leaves_the_previous_one(self, editor, tmp_path, monkeypatch, kind):
        # It was written in place: a failure part-way left the last export cut short
        from pybreeze.utils.file_process import replace_file

        target = tmp_path / f"diagram.{kind}"
        target.write_bytes(b"the previous export")

        def refuse(*_args, **_kwargs):
            raise OSError("no room on the disk")

        monkeypatch.setattr(replace_file.os, "replace", refuse)
        warned = self._export(editor, monkeypatch, target, kind)

        assert warned
        assert target.read_bytes() == b"the previous export"
        assert list(tmp_path.iterdir()) == [target], "a half-written file was left behind"

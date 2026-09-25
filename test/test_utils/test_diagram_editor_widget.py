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


@pytest.fixture
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


class TestMermaidImport:
    @staticmethod
    def _answer(monkeypatch, text: str, accepted: bool = True) -> None:
        """Stub the paste dialog with what the user would have pasted, and Convert or Cancel."""
        from PySide6.QtWidgets import QDialog

        from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget

        def exec_(dialog):
            dialog._editor.setPlainText(text)
            return QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected

        monkeypatch.setattr(diagram_editor_widget.MermaidImportDialog, "exec", exec_)

    @staticmethod
    def _dialogs_left(editor) -> int:
        from PySide6.QtCore import QCoreApplication, QEvent

        from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import MermaidImportDialog

        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        return len(editor.findChildren(MermaidImportDialog))

    def test_the_pasted_flowchart_becomes_the_diagram(self, editor, monkeypatch):
        self._answer(monkeypatch, "flowchart TD\n    A[Start] --> B[End]")
        editor._import_mermaid()
        assert sorted(n.text() for n in editor._scene.get_all_nodes()) == ["End", "Start"]

    def test_a_cancelled_import_leaves_the_canvas_alone(self, editor, monkeypatch):
        editor._scene.load_from_dict(_A_DIAGRAM)
        self._answer(monkeypatch, "flowchart TD\n    A[Start] --> B[End]", accepted=False)
        editor._import_mermaid()
        assert [n.text() for n in editor._scene.get_all_nodes()] == ["A"]

    @pytest.mark.parametrize("accepted", [True, False])
    def test_the_dialog_goes_once_closed(self, editor, monkeypatch, accepted):
        # It was a child of the editor, kept for good: one more per import
        self._answer(monkeypatch, "flowchart TD\n    A --> B", accepted=accepted)
        for _ in range(3):
            editor._import_mermaid()
        assert self._dialogs_left(editor) == 0


class TestFileDialogFilters:
    """The dialogs' filters were English literals in every language."""

    @staticmethod
    def _filters(editor, monkeypatch) -> dict[str, str]:
        from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget

        asked: list[str] = []

        def dialog(_parent, _title, _start, file_filter):
            asked.append(file_filter)
            return "", ""  # cancelled

        for name in ("getOpenFileName", "getSaveFileName"):
            monkeypatch.setattr(diagram_editor_widget.QFileDialog, name, staticmethod(dialog))
        seen: dict[str, str] = {}
        for name, action in (("open", editor._open_diagram), ("save", editor._save_as_diagram),
                             ("png", editor._export_png), ("svg", editor._export_svg),
                             ("image", editor._add_image_from_file)):
            action()
            seen[name] = asked.pop()
        return seen

    def test_they_speak_the_ide_language(self, editor, monkeypatch):
        from je_editor import language_wrapper

        from pybreeze.extend_multi_language.extend_traditional_chinese import (
            pybreeze_traditional_chinese_word_dict,
        )
        monkeypatch.setattr(language_wrapper, "language_word_dict", pybreeze_traditional_chinese_word_dict)
        filters = self._filters(editor, monkeypatch)

        assert "所有檔案 (*)" in filters["open"]
        assert "所有檔案 (*)" in filters["image"]
        assert filters["open"] == filters["save"]
        assert all("Image" not in text and "Files" not in text for text in filters.values()), filters

    def test_the_image_filter_offers_every_suffix_a_diagram_keeps(self, editor, monkeypatch):
        # .ico was allowed in a saved diagram but not offered by Add Image
        from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import IMAGE_SUFFIXES

        image_filter = self._filters(editor, monkeypatch)["image"]
        assert all(f"*{suffix}" in image_filter for suffix in IMAGE_SUFFIXES)

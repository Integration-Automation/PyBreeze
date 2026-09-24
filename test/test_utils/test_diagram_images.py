"""Where a diagram's images come from, and when the IDE waits for them.

A URL image is fetched on its own thread and kept for the session: an undo
rebuilds every item from the saved dictionary, and fetching again each time was
15 seconds of frozen IDE per image and per undo.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading
import time

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget as editor_module
from pybreeze.pybreeze_ui.diagram_editor import diagram_scene as scene_module
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene
from pybreeze.pybreeze_ui.thread_keeper import is_kept

_A_URL = "https://pictures.example/logo.png"

_A_DIAGRAM = {
    "nodes": [],
    "connections": [],
    "images": [{"x": 0, "y": 0, "w": 100, "h": 100, "source": _A_URL}],
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def an_image() -> bytes:
    """A real PNG, as bytes, so QPixmap has something to load."""
    from PySide6.QtCore import QBuffer, QByteArray

    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data.data())


@pytest.fixture()
def downloads(monkeypatch) -> list:
    """Record every fetch, and answer each with a real image."""
    asked: list = []

    def fetch(source: str) -> bytes:
        asked.append(source)
        return an_image()

    monkeypatch.setattr(scene_module, "safe_download_image", fetch)
    return asked


def wait_for_downloads(scene: DiagramScene, app) -> None:
    for thread in tuple(scene._image_downloads.values()):
        thread.wait(5000)
    app.processEvents()


class TestFetchingAnImage:
    def test_the_load_does_not_wait_for_the_network(self, app, monkeypatch):
        answering = threading.Event()
        started = threading.Event()

        def fetch(_source: str) -> bytes:
            started.set()
            answering.wait(10)
            return an_image()

        monkeypatch.setattr(scene_module, "safe_download_image", fetch)
        scene = DiagramScene()

        scene.load_from_dict(_A_DIAGRAM)

        # The host has not answered yet and the load is already back.
        assert started.wait(5), "the fetch never started"
        assert scene._image_downloads, "the load waited for the fetch"
        answering.set()
        wait_for_downloads(scene, app)
        scene.let_image_downloads_run_out()

    def test_what_comes_back_reaches_the_image(self, app, downloads):
        scene = DiagramScene()
        scene.load_from_dict(_A_DIAGRAM)

        wait_for_downloads(scene, app)

        assert downloads == [_A_URL]
        assert scene._pixmap_cache[_A_URL].isNull() is False
        scene.let_image_downloads_run_out()

    def test_an_undo_does_not_fetch_it_again(self, app, downloads):
        scene = DiagramScene()
        scene.load_from_dict(_A_DIAGRAM)
        wait_for_downloads(scene, app)

        # What undo/redo does: rebuild every item from the same dictionary.
        scene._restore_from_dict(_A_DIAGRAM)
        scene._restore_from_dict(_A_DIAGRAM)

        assert downloads == [_A_URL], "the image was fetched again"
        images = scene.get_all_images()
        assert images and not images[0]._pix_item.pixmap().isNull()
        scene.let_image_downloads_run_out()

    def test_two_images_from_one_source_share_a_single_fetch(self, app, downloads):
        scene = DiagramScene()

        scene.load_from_dict({
            **_A_DIAGRAM,
            "images": [
                {"x": 0, "y": 0, "w": 100, "h": 100, "source": _A_URL},
                {"x": 200, "y": 0, "w": 100, "h": 100, "source": _A_URL},
            ],
        })
        wait_for_downloads(scene, app)

        assert downloads == [_A_URL]
        scene.let_image_downloads_run_out()

    def test_a_fetch_that_fails_is_only_logged(self, app, monkeypatch):
        def refuse(source: str) -> bytes:
            raise scene_module.ImageDownloadError("nothing answered")

        monkeypatch.setattr(scene_module, "safe_download_image", refuse)
        scene = DiagramScene()

        scene.load_from_dict(_A_DIAGRAM)
        wait_for_downloads(scene, app)

        assert _A_URL not in scene._pixmap_cache
        assert scene.get_all_images()
        scene.let_image_downloads_run_out()


def _editor():
    from pybreeze.extend_multi_language.update_language_dict import update_language_dict
    from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import DiagramEditorWidget

    update_language_dict()
    return DiagramEditorWidget()


def _wait_until(app, condition) -> None:
    deadline = time.monotonic() + 5
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        app.processEvents()
        time.sleep(0.01)


@pytest.fixture()
def slow_host(monkeypatch) -> threading.Event:
    """A host that answers with an image once the returned event is set."""
    answering = threading.Event()

    def fetch(_source: str) -> bytes:
        answering.wait(5)
        return an_image()

    monkeypatch.setattr(scene_module, "safe_download_image", fetch)
    return answering


class TestClosingTheEditor:
    def test_it_lets_a_fetch_still_going_run_out(self, app, slow_host):
        editor = _editor()
        editor._scene.load_from_dict(_A_DIAGRAM)
        (fetch,) = editor._scene._image_downloads.values()

        editor.close()  # returns while the host is still answering

        assert editor._scene._image_downloads == {}
        assert is_kept(fetch)
        slow_host.set()
        _wait_until(app, lambda: not is_kept(fetch))


class TestAddingAnImageFromAUrl:
    def _ask_for(self, monkeypatch, url: str) -> None:
        monkeypatch.setattr(editor_module.QInputDialog, "getText", lambda *args: (url, True))

    def test_the_image_arrives_without_holding_the_ui(self, app, monkeypatch, slow_host):
        editor = _editor()
        self._ask_for(monkeypatch, _A_URL)

        editor._add_image_from_url()
        assert editor._scene.get_all_images() == []  # back before the host answered
        slow_host.set()
        _wait_until(app, lambda: editor._scene.get_all_images() and not editor._url_fetches)

        assert editor._scene.get_all_images()[0].source() == _A_URL
        editor.close()

    def test_a_failed_fetch_is_reported(self, app, monkeypatch):
        def refuse(_source: str) -> bytes:
            raise scene_module.ImageDownloadError("nothing answered")

        monkeypatch.setattr(scene_module, "safe_download_image", refuse)
        warned = []
        monkeypatch.setattr(editor_module.QMessageBox, "warning", lambda *args: warned.append(args[2]))
        editor = _editor()
        self._ask_for(monkeypatch, _A_URL)

        editor._add_image_from_url()
        _wait_until(app, lambda: warned)

        # As text: the message quotes the server, and Qt read markup in it
        from pybreeze.pybreeze_ui.plain_text import as_text

        assert warned == [as_text("nothing answered")]
        assert editor._scene.get_all_images() == []
        editor.close()

    def test_something_that_is_not_an_image_is_reported(self, app, monkeypatch):
        monkeypatch.setattr(scene_module, "safe_download_image", lambda _source: b"<html></html>")
        warned = []
        monkeypatch.setattr(editor_module.QMessageBox, "warning", lambda *args: warned.append(args[2]))
        editor = _editor()
        self._ask_for(monkeypatch, _A_URL)

        editor._add_image_from_url()
        _wait_until(app, lambda: warned)

        assert editor._scene.get_all_images() == []
        editor.close()

    def test_closing_mid_fetch_lets_it_run_out(self, app, monkeypatch, slow_host):
        editor = _editor()
        self._ask_for(monkeypatch, _A_URL)
        editor._add_image_from_url()
        (fetch,) = editor._url_fetches

        editor.close()

        assert is_kept(fetch)
        slow_host.set()
        _wait_until(app, lambda: not is_kept(fetch))


class TestCopyingAnImage:
    def _scene_with_an_image(self):
        scene = DiagramScene()
        scene.load_from_dict({
            "nodes": [], "connections": [],
            "images": [{"x": 0, "y": 0, "w": 100, "h": 100, "source": "", "caption": "Logo"}],
        })
        return scene

    def test_an_image_on_its_own_can_be_duplicated(self, app):
        scene = self._scene_with_an_image()
        scene.get_all_images()[0].setSelected(True)

        scene.duplicate_selected()

        images = scene.get_all_images()
        assert len(images) == 2
        assert {image.text() for image in images} == {"Logo"}
        assert {(image.pos().x(), image.pos().y()) for image in images} == {(0.0, 0.0), (30.0, 30.0)}

    def test_a_node_and_an_image_are_copied_together(self, app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode, NodeShape

        scene = self._scene_with_an_image()
        node = DiagramNode(x=0, y=0, w=100, h=60, text="A", shape=NodeShape.RECTANGLE)
        scene.addItem(node)
        for item in scene.get_all_images() + scene.get_all_nodes():
            item.setSelected(True)

        scene.copy_selected()
        scene.clearSelection()
        scene.paste_clipboard()

        assert len(scene.get_all_images()) == 2
        assert len(scene.get_all_nodes()) == 2

    def test_nothing_selected_leaves_the_clipboard_alone(self, app):
        scene = self._scene_with_an_image()
        scene.get_all_images()[0].setSelected(True)
        scene.copy_selected()

        scene.clearSelection()
        scene.copy_selected()

        assert scene._clipboard["images"], "the clipboard was emptied by a copy of nothing"


class _Drag:
    """The parts of a mouse event a resize handle reads."""

    def __init__(self, x: float, y: float) -> None:
        from PySide6.QtCore import QPointF

        self._pos = QPointF(x, y)

    def scenePos(self):
        return self._pos

    @staticmethod
    def button():
        from PySide6.QtCore import Qt

        return Qt.MouseButton.LeftButton

    def accept(self) -> None:
        """Handled."""


def test_an_image_resizes_by_its_corner_handle(app):
    # The handle read node_w, which an image does not have: every press and
    # move raised, and only the property panel could resize an image
    from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramImage

    scene = DiagramScene()
    image = DiagramImage(x=0, y=0, w=100, h=80)
    scene.addItem(image)
    handle = image._handles["br"]

    handle.mousePressEvent(_Drag(100, 80))
    handle.mouseMoveEvent(_Drag(150, 130))
    handle.mouseReleaseEvent(_Drag(150, 130))

    assert (image.img_w, image.img_h) == (150, 130)
    assert scene.undo_stack.count() == 1


def test_an_image_resized_down_and_back_is_as_sharp_as_before(app):
    # Each resize scaled the copy on show: 400 -> 50 -> 400 left it blurred
    from PySide6.QtGui import QPixmap

    from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramImage

    checkers = QImage(400, 400, QImage.Format.Format_RGB32)
    for y in range(400):
        for x in range(400):
            checkers.setPixelColor(x, y, QColor("black") if (x // 20 + y // 20) % 2 else QColor("white"))
    item = DiagramImage(0, 0, 400, 400, pixmap=QPixmap.fromImage(checkers))
    before = item._pix_item.pixmap().toImage()

    item.set_size(50, 50)
    item.set_size(400, 400)

    assert item._pix_item.pixmap().toImage() == before


class TestAnImageOnThisMachine:
    """A saved diagram is untrusted: only an image file here, of a kind it may name, is read."""

    @staticmethod
    def _loaded(app, source: str, downloads: list) -> bool:
        scene = DiagramScene()
        scene.load_from_dict({"nodes": [], "connections": [],
                              "images": [{"x": 0, "y": 0, "w": 4, "h": 4, "source": source}]})
        app.processEvents()
        loaded = not scene.get_all_images()[0]._pix_item.pixmap().isNull()
        assert downloads == []  # a path is never fetched
        return loaded

    def test_an_image_file_is_shown(self, app, tmp_path, downloads):
        picture = tmp_path / "logo.png"
        picture.write_bytes(an_image())
        assert self._loaded(app, str(picture), downloads)

    def test_a_file_of_another_kind_is_not_read(self, app, tmp_path, downloads):
        # A PNG it is, but named .txt: the extension is checked before the file is touched
        disguised = tmp_path / "notes.txt"
        disguised.write_bytes(an_image())
        assert not self._loaded(app, str(disguised), downloads)

    def test_a_file_that_is_not_there_is_left_empty(self, app, tmp_path, downloads):
        assert not self._loaded(app, str(tmp_path / "gone.png"), downloads)

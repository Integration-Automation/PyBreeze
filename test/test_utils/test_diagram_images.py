"""Where a diagram's images come from, and when the IDE waits for them.

A URL image is fetched on its own thread and kept for the session: an undo
rebuilds every item from the saved dictionary, and fetching again each time was
15 seconds of frozen IDE per image and per undo.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from pybreeze.pybreeze_ui.diagram_editor import diagram_scene as scene_module
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene

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
        import threading

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
        scene.stop_image_downloads()

    def test_what_comes_back_reaches_the_image(self, app, downloads):
        scene = DiagramScene()
        scene.load_from_dict(_A_DIAGRAM)

        wait_for_downloads(scene, app)

        assert downloads == [_A_URL]
        assert scene._pixmap_cache[_A_URL].isNull() is False
        scene.stop_image_downloads()

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
        scene.stop_image_downloads()

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
        scene.stop_image_downloads()

    def test_a_fetch_that_fails_is_only_logged(self, app, monkeypatch):
        def refuse(source: str) -> bytes:
            raise scene_module.ImageDownloadError("nothing answered")

        monkeypatch.setattr(scene_module, "safe_download_image", refuse)
        scene = DiagramScene()

        scene.load_from_dict(_A_DIAGRAM)
        wait_for_downloads(scene, app)

        assert _A_URL not in scene._pixmap_cache
        assert scene.get_all_images()
        scene.stop_image_downloads()


class TestClosingTheEditor:
    def test_it_waits_for_a_fetch_still_going(self, app, downloads):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import DiagramEditorWidget
        from pybreeze.extend_multi_language.update_language_dict import update_language_dict

        update_language_dict()
        editor = DiagramEditorWidget()
        editor._scene.load_from_dict(_A_DIAGRAM)

        editor.close()

        assert editor._scene._image_downloads == {}

"""A panel that ran a worker thread is freed once it is closed and deleted.

A slot holding the panel, connected to a thread the panel keeps, is a cycle
through Qt that Python's collector cannot see: every such panel opened and
closed stayed in memory with its thread for the rest of the session.
"""
from __future__ import annotations

import gc
import os
import time
import weakref

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    from pybreeze.extend_multi_language.update_language_dict import update_language_dict

    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _wait_for(app, thread, seconds: float = 10) -> None:
    deadline = time.monotonic() + seconds
    while thread.isRunning() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert not thread.isRunning()


def _freed_after_a_run(app, build, drive, thread_of) -> bool:
    """Build a panel, run its worker to the end, close and delete it: is it gone?

    Built here so no caller holds it.
    """
    from PySide6.QtCore import QCoreApplication, QEvent

    widget = build()
    drive(widget)
    _wait_for(app, thread_of(widget))
    watch = weakref.ref(widget)
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(widget, QEvent.Type.DeferredDelete)
    del widget
    gc.collect()
    return watch() is None


def _cot(widget) -> None:
    # A URL the panel refuses to send to: the thread ends at once, with no network
    widget.url_input.setText("ftp://example.invalid/")
    widget.code_paste_area.setPlainText("x")
    widget.start_sending()


def _skills(widget) -> None:
    widget.api_url_input.setText("ftp://example.invalid/")
    widget.prompt_input.setPlainText("x")
    widget.send_prompt()


def _diff(widget) -> None:
    widget.left_edit.setPlainText("a")
    widget.right_edit.setPlainText("b")
    widget.compare()


def test_the_cot_review_panel(app):
    from pybreeze.pybreeze_ui.extend_ai_gui.code_review.cot_code_review_gui import CoTCodeReviewGUI

    assert _freed_after_a_run(app, CoTCodeReviewGUI, _cot, lambda widget: widget.thread)


def test_the_skill_send_panel(app):
    from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import SkillsSendGUI

    assert _freed_after_a_run(app, SkillsSendGUI, _skills, lambda widget: widget.thread)


def test_the_diff_tab(app):
    from pybreeze.pybreeze_ui.tools_gui.diff_gui import DiffGUI

    assert _freed_after_a_run(app, DiffGUI, _diff, lambda widget: widget._compare_thread)


def test_the_ssh_shell_after_a_failed_connect(app, monkeypatch):
    import paramiko

    from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_command_widget

    def refuse(*_args, **_kwargs):
        raise OSError("refused")

    def connect(widget) -> None:
        widget.login_widget.host_edit.setText("h")
        widget.login_widget.user_edit.setText("u")
        widget.connect_ssh()

    monkeypatch.setattr(paramiko.SSHClient, "connect", refuse)

    # The client's host-key policy held the panel as its dialog parent
    assert _freed_after_a_run(
        app, ssh_command_widget.SSHCommandWidget, connect, lambda widget: widget._connecting)


def test_the_diagram_editor_after_an_image_from_a_url(app, monkeypatch):
    # The fetch's finished held a lambda holding the editor: the closed editor,
    # its scene and every image in it stayed
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QInputDialog

    from pybreeze.pybreeze_ui.diagram_editor import diagram_scene
    from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import DiagramEditorWidget

    image = QImage(4, 4, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    png = QByteArray()
    buffer = QBuffer(png)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    monkeypatch.setattr(diagram_scene, "safe_download_image", lambda _url: bytes(png.data()))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *_args, **_kwargs: ("http://x.test/a.png", True)))

    def add_image(widget) -> None:
        widget._add_image_from_url()
        (fetch,) = widget._url_fetches
        _wait_for(app, fetch)
        deadline = time.monotonic() + 5
        while widget._url_fetches and time.monotonic() < deadline:
            app.processEvents()
        assert len(widget._scene.get_all_images()) == 1

    class _Done:
        @staticmethod
        def isRunning() -> bool:
            return False

    assert _freed_after_a_run(app, DiagramEditorWidget, add_image, lambda _widget: _Done)

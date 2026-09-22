"""closeEvent must never leave a running worker QThread to be destroyed mid-run."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

import pytest

from pybreeze.pybreeze_ui.extend_ai_gui.code_review.cot_code_review_gui import CoTCodeReviewGUI
from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import SkillsSendGUI


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _running_thread():
    thread = MagicMock()
    thread.isRunning.return_value = True
    return thread


class TestCoTCloseEvent:
    def test_a_running_review_is_interrupted_and_let_go_of_without_waiting(self):
        # Waiting froze the IDE for up to a request's read timeout. The thread
        # is asked to stop after its current request, cut off from the panel,
        # and kept referenced until it ends.
        from pybreeze.pybreeze_ui import thread_keeper

        gui = CoTCodeReviewGUI.__new__(CoTCodeReviewGUI)
        thread = _running_thread()
        gui.thread = thread
        event = MagicMock()

        CoTCodeReviewGUI.closeEvent(gui, event)

        thread.requestInterruption.assert_called_once()
        thread.wait.assert_not_called()
        thread.update_response.disconnect.assert_called_once()
        assert thread_keeper.is_kept(thread)
        event.accept.assert_called_once()
        thread_keeper._OUTLIVING_THEIR_WIDGET.discard(thread)

    def test_no_thread_just_accepts(self):
        gui = CoTCodeReviewGUI.__new__(CoTCodeReviewGUI)
        gui.thread = None
        event = MagicMock()

        CoTCodeReviewGUI.closeEvent(gui, event)

        event.accept.assert_called_once()

    def test_finished_thread_is_not_awaited(self):
        gui = CoTCodeReviewGUI.__new__(CoTCodeReviewGUI)
        thread = MagicMock()
        thread.isRunning.return_value = False
        gui.thread = thread
        event = MagicMock()

        CoTCodeReviewGUI.closeEvent(gui, event)

        thread.wait.assert_not_called()
        event.accept.assert_called_once()


class TestSkillsCloseEvent:
    def test_a_running_request_is_let_go_of_without_waiting(self):
        # Waiting froze the IDE for as long as the request took (up to the read
        # timeout). The thread is cut off from the panel and kept referenced
        # until it ends, so it is never destroyed while running.
        from pybreeze.pybreeze_ui import thread_keeper

        gui = SkillsSendGUI.__new__(SkillsSendGUI)
        thread = _running_thread()
        gui.thread = thread
        event = MagicMock()

        SkillsSendGUI.closeEvent(gui, event)

        thread.wait.assert_not_called()
        thread.answered.disconnect.assert_called_once()
        thread.error.disconnect.assert_called_once()
        assert thread_keeper.is_kept(thread)
        event.accept.assert_called_once()
        thread_keeper._OUTLIVING_THEIR_WIDGET.discard(thread)

    def test_a_request_let_go_of_is_released_when_it_ends(self, qapp):
        from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import RequestThread
        from pybreeze.pybreeze_ui.thread_keeper import is_kept, let_run_out

        thread = RequestThread("http://.invalid", "prompt")
        let_run_out(thread, thread.answered, thread.error)
        assert is_kept(thread)
        thread.start()
        assert thread.wait(10000)
        qapp.processEvents()

        assert not is_kept(thread)

    def test_its_answer_signal_does_not_hide_the_thread_ending(self):
        from PySide6.QtCore import QThread

        from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import RequestThread

        # QThread.finished is what tells the panel the thread is over, however
        # run() ended; the answer travels on a signal of its own.
        assert RequestThread.finished is QThread.finished
        assert hasattr(RequestThread, "answered")

    def test_no_thread_just_accepts(self):
        gui = SkillsSendGUI.__new__(SkillsSendGUI)
        gui.thread = None
        event = MagicMock()

        SkillsSendGUI.closeEvent(gui, event)

        event.accept.assert_called_once()

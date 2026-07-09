"""closeEvent must never leave a running worker QThread to be destroyed mid-run."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

from pybreeze.pybreeze_ui.extend_ai_gui.code_review.cot_code_review_gui import CoTCodeReviewGUI
from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import SkillsSendGUI


def _running_thread():
    thread = MagicMock()
    thread.isRunning.return_value = True
    return thread


class TestCoTCloseEvent:
    def test_running_thread_is_blocked_interrupted_and_awaited(self):
        gui = CoTCodeReviewGUI.__new__(CoTCodeReviewGUI)
        gui.thread = _running_thread()
        event = MagicMock()

        CoTCodeReviewGUI.closeEvent(gui, event)

        gui.thread.blockSignals.assert_called_once_with(True)
        gui.thread.requestInterruption.assert_called_once()
        gui.thread.wait.assert_called_once()
        event.accept.assert_called_once()

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
    def test_running_thread_is_blocked_and_awaited(self):
        gui = SkillsSendGUI.__new__(SkillsSendGUI)
        gui.thread = _running_thread()
        event = MagicMock()

        SkillsSendGUI.closeEvent(gui, event)

        gui.thread.blockSignals.assert_called_once_with(True)
        gui.thread.wait.assert_called_once()
        event.accept.assert_called_once()

    def test_no_thread_just_accepts(self):
        gui = SkillsSendGUI.__new__(SkillsSendGUI)
        gui.thread = None
        event = MagicMock()

        SkillsSendGUI.closeEvent(gui, event)

        event.accept.assert_called_once()

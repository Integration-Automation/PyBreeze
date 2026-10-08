"""The small decisions ``TaskProcessManager`` makes: colours, notices, the timer, progress, the command line."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from pybreeze.extend.process_executor import python_task_process_manager as mod
from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager, find_venv_path


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class _RunWindow(QObject):
    """A stand-in run window that records what it is told to show, as (text, is_error, own_line)."""

    def __init__(self, python_compiler: str | None = "python") -> None:
        super().__init__()
        self.python_compiler = python_compiler
        self.shown: list[tuple[str, bool, bool]] = []

    def append_output(self, text: str, is_error: bool = False, *, own_line: bool = False) -> None:
        self.shown.append((text, is_error, own_line))

    def show(self) -> None:
        """Nothing to show in a stand-in."""

    def run_started(self) -> None:
        """Nothing to mark in a stand-in."""

    def run_ended(self) -> None:
        """Nothing to mark in a stand-in."""

    def setWindowTitle(self, title: str) -> None:  # noqa: N802 — the Qt name the manager calls
        """Nothing to title in a stand-in."""


def _manager(window: _RunWindow) -> TaskProcessManager:
    return TaskProcessManager(window)


class TestEachStreamKeepsItsColour:
    def test_a_tick_shows_standard_output_plainly_and_errors_in_the_error_colour(self, qt_app):
        window = _RunWindow()
        manager = _manager(window)
        manager.run_output_queue.put("out")
        manager.run_error_queue.put("err")

        manager.pull_text()

        assert window.shown == [("out", False, False), ("err", True, False)]

    def test_the_last_of_the_output_keeps_the_colours_too(self, qt_app):
        window = _RunWindow()
        manager = _manager(window)
        manager.run_output_queue.put("out")
        manager.run_error_queue.put("err")

        manager.drain_and_display_queue()

        assert window.shown == [("out", False, False), ("err", True, False)]


class TestTheWindowsOwnNotices:
    """A notice is an error, on a line of its own: not the tail of what the program printed."""

    def test_no_interpreter(self, qt_app, monkeypatch):
        from je_editor import JEditorExecException

        def no_python():
            raise JEditorExecException("none")

        window = _RunWindow(python_compiler=None)
        monkeypatch.setattr(mod, "default_interpreter", no_python)

        assert _manager(window).renew_path() is False
        assert [(is_error, own_line) for _, is_error, own_line in window.shown] == [(True, True)]

    def test_an_interpreter_that_cannot_start(self, qt_app, tmp_path):
        window = _RunWindow(python_compiler=str(tmp_path / "missing-python.exe"))

        _manager(window).start_test_process("json.tool", "{}")

        assert [(is_error, own_line) for _, is_error, own_line in window.shown] == [(True, True)]


class TestThePump:
    def test_with_no_run_the_timer_stops(self, qt_app):
        manager = _manager(_RunWindow())
        manager.timer.start(1000)

        manager.pull_text()

        assert not manager.timer.isActive()

    def test_a_tick_that_showed_one_message_is_progress(self, qt_app, monkeypatch):
        # Output still arriving after the exit keeps the readers' grace going
        manager = _manager(_RunWindow())
        manager.process = type("Exited", (), {"returncode": 0})()
        seen = []
        monkeypatch.setattr(manager._reader_grace, "still_reading",
                            lambda *readers, progressed=False: seen.append(progressed) or True)
        manager.run_output_queue.put("one line")

        manager.pull_text()

        assert seen == [True]


class TestTheScriptOnTheCommandLine:
    """The automation packages decode ``--execute_str`` once more on Windows (architecture.md 6)."""

    @pytest.mark.parametrize(("platform", "encode"), [("win32", json.dumps), ("linux", lambda text: text)])
    def test_it_is_json_quoted_on_windows_only(self, qt_app, monkeypatch, platform, encode):
        manager = _manager(_RunWindow())
        spawned = []
        monkeypatch.setattr(manager, "_spawn_and_pump", lambda package, args, subject="": spawned.append(args))
        monkeypatch.setattr(sys, "platform", platform)
        script = '[["AC_screen_size"]]'

        manager.start_test_process("je_auto_control", script)

        assert spawned[0][-2:] == ["--execute_str", encode(script)]


class TestFindVenvPath:
    @pytest.mark.parametrize(("platform", "folder"), [("win32", "Scripts"), ("linux", "bin")])
    def test_a_dot_venv_in_the_working_folder_is_found(self, tmp_path, monkeypatch, platform, folder):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "platform", platform)
        (tmp_path / ".venv" / folder).mkdir(parents=True)

        assert find_venv_path() == Path.cwd() / ".venv" / folder

    @pytest.mark.parametrize(("platform", "folder"), [("win32", "Scripts"), ("linux", "bin")])
    def test_without_one_it_names_where_venv_would_be(self, tmp_path, monkeypatch, platform, folder):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "platform", platform)

        assert find_venv_path() == Path.cwd() / "venv" / folder

    def test_venv_comes_before_dot_venv(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "platform", "linux")
        (tmp_path / ".venv" / "bin").mkdir(parents=True)
        (tmp_path / "venv" / "bin").mkdir(parents=True)

        assert find_venv_path() == Path.cwd() / "venv" / "bin"

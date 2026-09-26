"""The notices a plugin run writes in its window: each on a line of its own, in the IDE language."""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from pybreeze.extend.process_executor import run_notice as run_notice_mod
from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
from pybreeze.extend_multi_language.extend_traditional_chinese import (
    pybreeze_traditional_chinese_word_dict as CHINESE,
)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class _RunWindow(QObject):
    """A stand-in run window that records what it is told to show, as (text, is_error, own_line)."""

    def __init__(self) -> None:
        super().__init__()
        self.shown: list[tuple[str, bool, bool]] = []

    def append_output(self, text: str, is_error: bool = False, *, own_line: bool = False) -> None:
        self.shown.append((text, is_error, own_line))

    def run_started(self) -> None:
        """Nothing to mark in a stand-in."""

    def run_ended(self) -> None:
        """Nothing to mark in a stand-in."""


class _Running:
    """A child that has not exited."""

    returncode = None

    def poll(self) -> None:
        return None


class TestEachNoticeIsALineOfItsOwn:
    """Written after output the program left unfinished, a notice was the end of that line."""

    def test_a_config_without_a_compiler(self, qt_app):
        window = _RunWindow()

        FileRunnerProcess(window).run_file({"name": "X", "compiler": ""}, "main.x")

        assert [own_line for _, _, own_line in window.shown] == [True]

    def test_a_command_that_is_not_there(self, qt_app):
        window = _RunWindow()

        FileRunnerProcess(window).run_file({"name": "X", "compiler": "no-such-compiler-pybreeze"}, "main.x")

        assert [(own_line, is_error) for _, is_error, own_line in window.shown] == [(True, False), (True, True)]

    def test_a_command_that_cannot_start(self, qt_app, tmp_path):
        window = _RunWindow()

        FileRunnerProcess(window).run_file({"name": "X", "compiler": str(tmp_path)}, "main.x")

        assert [(own_line, is_error) for _, is_error, own_line in window.shown] == [(True, False), (True, True)]

    def test_a_compile_that_runs_out_of_time(self, qt_app, monkeypatch):
        window = _RunWindow()
        runner = FileRunnerProcess(window)
        runner.process = _Running()
        runner._deadline = time.monotonic() - 1
        monkeypatch.setattr("pybreeze.extend.process_executor.file_runner_process.stop_tree", lambda process: None)

        runner._pull_text()

        assert [(own_line, is_error) for _, is_error, own_line in window.shown] == [(True, True)]


class TestTheExitLine:
    def test_it_is_in_the_ide_language(self, qt_app, monkeypatch):
        # "[Process exited with code 0]" whatever the IDE spoke
        monkeypatch.setattr(run_notice_mod.language_wrapper, "language_word_dict", CHINESE)
        window = _RunWindow()
        runner = FileRunnerProcess(window)
        runner.process = type("Exited", (), {"returncode": 3})()

        runner._finish()

        assert window.shown[-1] == ("\n[行程已結束，結束代碼 3]\n", True, False)

    def test_in_english_it_reads_as_it_did(self, qt_app, monkeypatch):
        monkeypatch.setattr(run_notice_mod.language_wrapper, "language_word_dict", {})
        window = _RunWindow()
        runner = FileRunnerProcess(window)
        runner.process = type("Exited", (), {"returncode": 0})()

        runner._finish()

        assert window.shown[-1] == ("\n[Process exited with code 0]\n", False, False)


class TestACompileThatLeftItsLineOpen:
    def test_the_failure_starts_a_line_of_its_own(self, qt_app, tmp_path):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        source = tmp_path / "main.x"
        source.write_text("x", encoding="utf-8")
        window = CodeWindow()
        runner = FileRunnerProcess(window)
        # The "compiler" writes an error with no line break, and fails
        runner.run_file({
            "name": "X", "compiler": sys.executable, "compile_then_run": True,
            "args": ["-c", "import sys; sys.stderr.write('bad'); sys.exit(1)"],
        }, str(source))
        deadline = time.monotonic() + 30
        while "[Compile failed]" not in window.code_result.toPlainText():
            assert time.monotonic() < deadline, "the compile did not finish in time"
            qt_app.processEvents()
            time.sleep(0.01)

        assert "bad\n[Compile failed] exit code 1" in window.code_result.toPlainText()

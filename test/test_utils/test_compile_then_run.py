"""A plugin run that compiles first: the compiler is a streamed child, not a UI-thread wait."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pybreeze.extend.process_executor import file_runner_process
from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess

_WAIT_SECONDS = 30


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _run_events_until(qt_app, condition) -> None:
    deadline = time.monotonic() + _WAIT_SECONDS
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        qt_app.processEvents()
        time.sleep(0.01)


def _compiler(tmp_path, body: str) -> dict:
    """A run config whose "compiler" is Python running *body* as a script."""
    script = tmp_path / "compiler.py"
    script.write_text("import sys, time, pathlib\n" + body, encoding="utf-8")
    return {"name": "Fake C", "compiler": sys.executable, "args": (str(script),),
            "compile_then_run": True, "output_flag": "-o"}


def _runner(monkeypatch):
    """A runner whose compile runs for real and whose run step is only recorded."""
    from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

    window = CodeWindow()
    runner = FileRunnerProcess(window)
    runs: list = []
    real_start = runner._start_process

    def start(command, cleanup_dir=None, after_exit=None, time_limit=None):
        if after_exit is None:  # the run of the compiled binary
            runs.append((command, cleanup_dir))
            return
        real_start(command, cleanup_dir, after_exit, time_limit)

    monkeypatch.setattr(runner, "_start_process", start)
    return window, runner, runs


class TestCompileThenRun:
    def test_the_compile_does_not_hold_the_ui_and_the_run_follows(self, qt_app, tmp_path, monkeypatch):
        go = tmp_path / "go"
        config = _compiler(tmp_path, (
            f"flag = pathlib.Path({str(go)!r})\n"
            "print('compiling', flush=True)\n"
            "deadline = time.monotonic() + 20\n"
            "while not flag.exists() and time.monotonic() < deadline:\n"
            "    time.sleep(0.02)\n"
        ))
        window, runner, runs = _runner(monkeypatch)
        source = tmp_path / "main.c"

        runner.run_file(config, str(source))
        assert runner.process is not None  # back while the compiler still works
        _run_events_until(qt_app, lambda: "compiling" in window.code_result.toPlainText())
        assert runs == []  # its output streamed in before it finished
        go.touch()
        _run_events_until(qt_app, lambda: runs)

        # Built in a folder of its own, which goes once it has run: beside the
        # source it replaced a file of that name there
        [(command, build_dir)] = runs
        built = Path(command[0])
        assert built.name == "main" + (".exe" if sys.platform == "win32" else "")
        assert built.parent == Path(build_dir)
        assert built.parent != tmp_path
        assert f"[Run] {built}" in window.code_result.toPlainText()

    def test_a_failed_compile_is_reported_and_nothing_runs(self, qt_app, tmp_path, monkeypatch):
        config = _compiler(tmp_path, "print('main.c:1: error', file=sys.stderr)\nsys.exit(3)\n")
        window, runner, runs = _runner(monkeypatch)

        runner.run_file(config, str(tmp_path / "main.c"))
        _run_events_until(qt_app, lambda: runner.process is None)

        text = window.code_result.toPlainText()
        assert "main.c:1: error" in text
        assert text.endswith("[Compile failed] exit code 3\n")
        assert "[Process exited" not in text
        assert runs == []

    def test_a_compile_that_runs_too_long_is_stopped(self, qt_app, tmp_path, monkeypatch):
        monkeypatch.setattr(file_runner_process, "COMPILE_TIME_LIMIT_SECONDS", 0.5)
        config = _compiler(tmp_path, "time.sleep(30)\n")
        window, runner, runs = _runner(monkeypatch)

        runner.run_file(config, str(tmp_path / "main.c"))
        _run_events_until(qt_app, lambda: runner.process is None)

        text = window.code_result.toPlainText()
        assert "Timed out after 0.5s" in text
        assert "[Compile failed]" in text
        assert runs == []

    def test_a_missing_compiler_is_reported(self, qt_app, tmp_path, monkeypatch):
        window, runner, runs = _runner(monkeypatch)
        config = {"name": "Fake C", "compiler": str(tmp_path / "no-such-compiler"),
                  "compile_then_run": True}

        runner.run_file(config, str(tmp_path / "main.c"))

        assert "[Error] Command not found" in window.code_result.toPlainText()
        assert runner.process is None
        assert runs == []


class TestRunArguments:
    """JEditor does not check a plugin's run config: ``"args": "run"`` ran ``go r u n main.go``."""

    @pytest.mark.parametrize(("config", "expected"), [
        ({"args": ("run",)}, ["run"]),
        ({"args": ["build", "-v"]}, ["build", "-v"]),
        ({"args": "run"}, ["run"]),
        ({"args": ""}, []),
        ({}, []),
        ({"args": None}, []),
        ({"args": 3}, []),
        ({"args": (1, "x")}, ["1", "x"]),
    ])
    def test_what_goes_between_the_compiler_and_the_file(self, config, expected):
        assert file_runner_process.run_arguments(config) == expected

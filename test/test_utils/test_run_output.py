"""A child's output, end to end: pipe, reader thread, queue, timer pump, run window."""
from __future__ import annotations

import gc
import json
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

# A child process on a busy CI runner can take a while to start.
_RUN_TIMEOUT_SECONDS = 30


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        try:
            app = QApplication([])
        except Exception as exc:  # pragma: no cover - no usable Qt platform
            pytest.skip(f"Cannot start QApplication: {exc}")
    return app


def _run_events_until(qt_app, finished) -> None:
    deadline = time.monotonic() + _RUN_TIMEOUT_SECONDS
    while not finished():
        if time.monotonic() > deadline:
            pytest.fail("the child process did not finish in time")
        qt_app.processEvents()
        time.sleep(0.01)


def _finished_after_collecting(run_window, last_line: str):
    """Return a check that collects garbage, then looks for *last_line* in *run_window*.

    Collecting on every check is what a long-running IDE does sooner or later:
    whatever keeps the run going must survive it.
    """
    def finished() -> bool:
        gc.collect()
        return last_line in run_window.code_result.toPlainText()
    return finished


class MainWindow:
    """The little of the IDE's main window that opening a run window touches."""

    def __init__(self, python_compiler=None) -> None:
        self.python_compiler = python_compiler
        self.current_run_code_window: list = []
        self.encoding = "utf-8"

    def clear_code_result(self) -> None:
        """Nothing to clear in a stand-in."""


class TestTaskProcessOutput:
    def test_indented_output_keeps_its_indentation(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        data = tmp_path / "data.json"
        data.write_text(json.dumps({"outer": {"inner": 1}}), encoding="utf-8")
        process = build_task_process(MainWindow(sys.executable))

        process.start_module_process("json.tool", [str(data)])
        _run_events_until(qt_app, lambda: process.process is None)

        text = process.main_window.code_result.toPlainText()
        assert '{\n    "outer": {\n        "inner": 1\n    }\n}\n' in text
        assert text.endswith("Task exit with code 0\n")

    def test_the_run_finishes_with_no_one_else_holding_its_manager(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        data = tmp_path / "data.json"
        data.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        main_window = MainWindow(sys.executable)

        build_task_process(main_window).start_module_process("json.tool", [str(data)])
        run_window = main_window.current_run_code_window[0]
        _run_events_until(
            qt_app, _finished_after_collecting(run_window, "Task exit with code 0"))

        assert '"key": "value"' in run_window.code_result.toPlainText()


class TestFileRunnerOutput:
    def test_indentation_and_blank_lines_survive(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        script = tmp_path / "show.py"
        script.write_text(
            "import sys\n"
            "print('def f():')\n"
            "print('    return 1')\n"
            "print()\n"
            "print('  warned', file=sys.stderr)\n",
            encoding="utf-8",
        )
        window = CodeWindow()
        runner = FileRunnerProcess(window)

        runner.run_file({"name": "Python", "compiler": sys.executable}, str(script))
        _run_events_until(qt_app, lambda: runner.process is None)

        text = window.code_result.toPlainText()
        assert "def f():\n    return 1\n\n" in text
        assert "  warned\n" in text
        assert text.endswith("[Process exited with code 0]\n")

    def test_run_with_finishes_with_no_one_else_holding_its_runner(
            self, qt_app, tmp_path, monkeypatch):
        from pybreeze.pybreeze_ui.menu.plugin_menu import build_run_with_menu as run_with

        script = tmp_path / "hello.py"
        script.write_text("print('hello from the plugin run')\n", encoding="utf-8")
        monkeypatch.setattr(run_with, "save_current_file_for_run", lambda _w: str(script))
        main_window = MainWindow()

        run_with.run_current_file_with(
            main_window, {"name": "Python", "compiler": sys.executable, "suffixes": (".py",)})
        run_window = main_window.current_run_code_window[0]
        _run_events_until(
            qt_app, _finished_after_collecting(run_window, "[Process exited with code 0]"))

        assert "hello from the plugin run" in run_window.code_result.toPlainText()


_SLEEP_SECONDS = "60"


class TestStoppingARun:
    """Stopping the child a run window shows: what closing the IDE does to every run."""

    def test_a_python_run_is_stopped_and_reports_its_exit(self, qt_app):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        main_window = MainWindow(sys.executable)
        manager = build_task_process(main_window)
        manager.start_module_process(
            "timeit", ["-n", "1", "-r", "1", f"import time; time.sleep({_SLEEP_SECONDS})"])
        child = manager.process
        run_window = main_window.current_run_code_window[0]

        run_window.stop_runner()
        _run_events_until(
            qt_app, lambda: "Task exit with code" in run_window.code_result.toPlainText())

        assert child.poll() is not None

    def test_a_plugin_run_is_stopped_and_reports_its_exit(self, qt_app, tmp_path, monkeypatch):
        from pybreeze.pybreeze_ui.menu.plugin_menu import build_run_with_menu as run_with

        script = tmp_path / "wait.py"
        script.write_text(f"import time\ntime.sleep({_SLEEP_SECONDS})\n", encoding="utf-8")
        monkeypatch.setattr(run_with, "save_current_file_for_run", lambda _w: str(script))
        main_window = MainWindow()

        run_with.run_current_file_with(
            main_window, {"name": "Python", "compiler": sys.executable, "suffixes": (".py",)})
        run_window = main_window.current_run_code_window[0]
        child = run_window.runner.process
        run_window.stop_runner()
        _run_events_until(
            qt_app, lambda: "[Process exited with code" in run_window.code_result.toPlainText())

        assert child.poll() is not None

    def test_stopping_a_finished_run_changes_nothing(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        data = tmp_path / "data.json"
        data.write_text("{}", encoding="utf-8")
        main_window = MainWindow(sys.executable)
        manager = build_task_process(main_window)
        manager.start_module_process("json.tool", [str(data)])
        _run_events_until(qt_app, lambda: manager.process is None)
        run_window = main_window.current_run_code_window[0]
        before = run_window.code_result.toPlainText()

        run_window.stop_runner()

        assert run_window.code_result.toPlainText() == before

    def test_a_window_that_never_ran_anything_can_be_stopped(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        CodeWindow().stop_runner()


class TestTestPioneerRun:
    def test_runs_the_chosen_yaml_through_the_task_manager(self, monkeypatch):
        from pybreeze.extend.process_executor.test_pioneer import test_pioneer_process_manager

        calls: list = []

        class Recorder:
            def start_module_process(self, package, arguments, environment=None):
                calls.append((package, list(arguments), environment))

        monkeypatch.setattr(
            test_pioneer_process_manager, "build_task_process",
            lambda main_window, program_buffer: Recorder())

        test_pioneer_process_manager.init_and_start_test_pioneer_process(
            MainWindow(), "C:/tests/run.yml")

        assert calls == [("test_pioneer", ["-e", "C:/tests/run.yml"], None)]

    def test_no_interpreter_is_reported_not_raised(self, qt_app, monkeypatch):
        from je_editor import JEditorExecException

        from pybreeze.extend.process_executor import python_task_process_manager as manager_module
        from pybreeze.extend.process_executor.test_pioneer import test_pioneer_process_manager

        def no_python(_path):
            raise JEditorExecException("no python interpreter found")

        monkeypatch.setattr(manager_module, "check_and_choose_venv", no_python)
        main_window = MainWindow()

        test_pioneer_process_manager.init_and_start_test_pioneer_process(main_window, "run.yml")

        run_window = main_window.current_run_code_window[0]
        assert "No Python interpreter found" in run_window.code_result.toPlainText()

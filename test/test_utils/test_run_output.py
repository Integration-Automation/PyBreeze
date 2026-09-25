"""A child's output, end to end: pipe, reader thread, queue, timer pump, run window."""
from __future__ import annotations

import gc
import json
import os
import sys
import time
from pathlib import Path

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

    def test_a_program_that_reads_input_gets_end_of_file(self, qt_app, tmp_path):
        # A run window has no input box: a read must end at once rather than
        # wait on a pipe nobody writes to, which hung the run for good.
        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        script = tmp_path / "ask.py"
        script.write_text("input('name? ')\n", encoding="utf-8")
        window = CodeWindow()
        window.runner = FileRunnerProcess(window)

        window.runner.run_file({"name": "Python", "compiler": sys.executable}, str(script))
        _run_events_until(qt_app, lambda: window.runner.process is None)

        text = window.code_result.toPlainText()
        assert "EOFError" in text
        assert text.endswith("[Process exited with code 1]\n")

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
            def start_module_process(self, package, arguments, environment=None, subject=""):
                calls.append((package, list(arguments), environment, subject))

        monkeypatch.setattr(
            test_pioneer_process_manager, "build_task_process",
            lambda main_window, program_buffer: Recorder())

        test_pioneer_process_manager.init_and_start_test_pioneer_process(
            MainWindow(), "C:/tests/run.yml")

        # The run window is titled with the file's name
        assert calls == [("test_pioneer", ["-e", "C:/tests/run.yml"], None, "run.yml")]

    def test_no_interpreter_is_reported_not_raised(self, qt_app, monkeypatch):
        from je_editor import JEditorExecException

        from pybreeze.extend.process_executor import python_task_process_manager as manager_module
        from pybreeze.extend.process_executor.test_pioneer import test_pioneer_process_manager

        def no_python(_path):
            raise JEditorExecException("no python interpreter found")

        monkeypatch.setattr(sys, "frozen", True, raising=False)  # only a packaged build can find none
        monkeypatch.setattr(manager_module, "check_and_choose_venv", no_python)
        main_window = MainWindow()

        test_pioneer_process_manager.init_and_start_test_pioneer_process(main_window, "run.yml")

        run_window = main_window.current_run_code_window[0]
        assert "No Python interpreter found" in run_window.code_result.toPlainText()


class TestAPythonRunThatCannotStart:
    def test_a_missing_interpreter_is_reported_in_the_window(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        main_window = MainWindow(python_compiler=str(tmp_path / "gone" / "python.exe"))

        # It raised FileNotFoundError out of the menu, and the run window was
        # never shown.
        build_task_process(main_window).start_module_process("pip", ["--version"])

        run_window = main_window.current_run_code_window[0]
        assert "pip could not start" in run_window.code_result.toPlainText()
        assert run_window.runner.process is None

    def test_a_script_that_reads_input_gets_end_of_file(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        (tmp_path / "ask.py").write_text("input('name? ')\n", encoding="utf-8")
        main_window = MainWindow(python_compiler=sys.executable)
        runner = build_task_process(main_window)

        # It read the IDE's own console, and waited there.
        runner.start_module_process("ask", [], environment={"PYTHONPATH": str(tmp_path)})
        run_window = main_window.current_run_code_window[0]
        _run_events_until(qt_app, lambda: "Task exit with code" in run_window.code_result.toPlainText())

        assert "EOFError" in run_window.code_result.toPlainText()


class TestAFileRunThatCannotStart:
    def test_a_compiler_that_is_a_folder_is_reported(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        runner = FileRunnerProcess(window)

        # PermissionError: only FileNotFoundError was caught.
        runner.run_file({"name": "Odd", "compiler": str(tmp_path)}, str(tmp_path / "main.x"))

        assert "[Error] Could not start" in window.code_result.toPlainText()
        assert runner.process is None


def _script_leaving_a_process_on_the_pipes(folder, grandchild_code: str):
    """A script that starts a process holding its output, prints that process's id, and exits."""
    script = folder / "leave.py"
    script.write_text(
        "import subprocess, sys\n"
        f"child = subprocess.Popen([sys.executable, '-c', {grandchild_code!r}],\n"
        "                         stdout=sys.stdout, stderr=sys.stderr)\n"
        "print('grandchild', child.pid, flush=True)\n",
        encoding="utf-8",
    )
    return script


def _longest_event_pass(qt_app, finished) -> float:
    """Process events until *finished*, returning the longest single pass in seconds."""
    deadline = time.monotonic() + _RUN_TIMEOUT_SECONDS
    longest = 0.0
    while not finished():
        if time.monotonic() > deadline:
            pytest.fail("the run did not end in time")
        started = time.monotonic()
        qt_app.processEvents()
        longest = max(longest, time.monotonic() - started)
        time.sleep(0.01)
    return longest


def _stop_grandchild(text: str) -> None:
    for line in text.splitlines():
        if line.startswith("grandchild "):
            try:
                os.kill(int(line.split()[1]), 9)
            except OSError:
                pass


# Long enough to outlast the run's grace many times over
_HOLDING = "import time; time.sleep(20)"


class TestAProcessTheRunStartedHoldsItsOutput:
    """The run ends without waiting on the UI thread for pipes a grandchild keeps open."""

    def test_a_python_run_ends_without_freezing_the_window(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        _script_leaving_a_process_on_the_pipes(tmp_path, _HOLDING)
        main_window = MainWindow(python_compiler=sys.executable)
        build_task_process(main_window).start_module_process(
            "leave", [], environment={"PYTHONPATH": str(tmp_path)})
        run_window = main_window.current_run_code_window[0]
        try:
            # Each reader was joined for two seconds inside one timer tick
            longest = _longest_event_pass(
                qt_app, lambda: "Task exit with code" in run_window.code_result.toPlainText())
            text = run_window.code_result.toPlainText()
        finally:
            _stop_grandchild(run_window.code_result.toPlainText())

        assert longest < 1.0
        assert "still holds its output" in text

    def test_a_plugin_run_ends_without_freezing_the_window(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        script = _script_leaving_a_process_on_the_pipes(tmp_path, _HOLDING)
        window = CodeWindow()
        runner = FileRunnerProcess(window)
        runner.run_file({"name": "Python", "compiler": sys.executable}, str(script))
        try:
            longest = _longest_event_pass(qt_app, lambda: not runner.still_running)
            text = window.code_result.toPlainText()
        finally:
            _stop_grandchild(window.code_result.toPlainText())

        assert longest < 1.0
        assert "still holds its output" in text
        assert "[Process exited with code 0]" in text

    def test_output_that_comes_within_the_grace_is_shown(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        _script_leaving_a_process_on_the_pipes(
            tmp_path, "import time; time.sleep(0.3); print('late line', flush=True)")
        main_window = MainWindow(python_compiler=sys.executable)
        build_task_process(main_window).start_module_process(
            "leave", [], environment={"PYTHONPATH": str(tmp_path)})
        run_window = main_window.current_run_code_window[0]
        _run_events_until(qt_app, lambda: "Task exit with code" in run_window.code_result.toPlainText())

        text = run_window.code_result.toPlainText()
        assert text.index("late line") < text.index("Task exit with code")
        assert "still holds its output" not in text


def test_a_runaway_run_holds_a_bounded_backlog_and_stops_promptly(qt_app, tmp_path):
    # The queues were unbounded: a print loop filled memory while it ran, and
    # Stop then poured the whole backlog into the window on the UI thread
    from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
    from pybreeze.extend.process_executor.queue_pump import MAX_QUEUED_MESSAGES
    from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

    script = tmp_path / "flood.py"
    script.write_text("i = 0\nwhile True:\n    print(i)\n    i += 1\n", encoding="utf-8")
    window = CodeWindow()
    runner = FileRunnerProcess(window)
    runner.run_file({"name": "Python", "compiler": sys.executable}, str(script))
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    assert runner.output_queue.qsize() <= MAX_QUEUED_MESSAGES
    runner.stop()
    _run_events_until(qt_app, lambda: not runner.still_running)
    assert "[Process exited with code" in window.code_result.toPlainText()


def test_a_line_without_its_newline_shows_while_the_run_goes_on(qt_app, tmp_path):
    # Read by line, a status line or a progress bar showed nothing until the
    # run's next newline
    from pybreeze.extend.process_executor.process_executor_utils import build_task_process

    (tmp_path / "status.py").write_text(
        "import sys, time\n"
        "sys.stdout.write('working... 50%'); sys.stdout.flush()\n"
        "time.sleep(4)\n"
        "print(' done')\n",
        encoding="utf-8")
    main_window = MainWindow(python_compiler=sys.executable)
    build_task_process(main_window).start_module_process(
        "status", [], environment={"PYTHONPATH": str(tmp_path)})
    run_window = main_window.current_run_code_window[0]

    _run_events_until(qt_app, lambda: "50%" in run_window.code_result.toPlainText())
    assert "done" not in run_window.code_result.toPlainText()
    _run_events_until(qt_app, lambda: "Task exit with code" in run_window.code_result.toPlainText())
    assert "working... 50% done" in run_window.code_result.toPlainText()


def _fake_compiler(folder: Path, seconds: float = 0.0) -> Path:
    """A "compiler" that sleeps *seconds*, then copies a stand-alone Windows program to the -o path."""
    script = folder / "fakecc.py"
    script.write_text(
        "import shutil, sys, time\n"
        f"time.sleep({seconds})\n"
        "shutil.copy(r'C:\\Windows\\System32\\hostname.exe', sys.argv[sys.argv.index('-o') + 1])\n"
        "print('compiled', flush=True)\n",
        encoding="utf-8")
    return script


def _compile_config(script: Path) -> dict:
    return {"name": "Fake", "compiler": sys.executable, "args": (str(script),), "compile_then_run": True}


@pytest.mark.skipif(os.name != "nt", reason="the stand-in program is Windows'")
class TestCompileThenRun:
    def test_the_binary_is_built_away_from_the_source_and_removed(self, qt_app, tmp_path):
        # It was built beside the source, replacing and then deleting a file of
        # that name there
        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        source = tmp_path / "hello.c"
        source.write_text("int main(){}", encoding="utf-8")
        mine = tmp_path / "hello.exe"
        mine.write_bytes(b"the user's own build")
        window = CodeWindow()
        runner = FileRunnerProcess(window)
        window.runner = runner

        runner.run_file(_compile_config(_fake_compiler(tmp_path)), str(source))
        _run_events_until(qt_app, lambda: "[Process exited with code" in window.code_result.toPlainText())

        text = window.code_result.toPlainText()
        assert "[Process exited with code 0]" in text
        assert mine.read_bytes() == b"the user's own build"
        built = next(line for line in text.splitlines() if line.startswith("[Run] "))[len("[Run] "):]
        assert Path(built).parent != tmp_path
        assert not Path(built).parent.exists()

    def test_stop_during_the_compile_is_reported_and_runs_nothing(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        source = tmp_path / "slow.c"
        source.write_text("int main(){}", encoding="utf-8")
        window = CodeWindow()
        runner = FileRunnerProcess(window)
        window.runner = runner
        ended: list = []
        window.run_ended = lambda: ended.append(True)

        runner.run_file(_compile_config(_fake_compiler(tmp_path, seconds=20)), str(source))
        _run_events_until(qt_app, lambda: runner.process is not None)
        runner.stop()
        _run_events_until(qt_app, lambda: ended)

        text = window.code_result.toPlainText()
        # It said "[Compile failed] exit code 1"
        assert "[Stopped]" in text
        assert "[Compile failed]" not in text
        assert "[Run]" not in text

    def test_stop_just_after_the_compile_runs_nothing(self, qt_app, tmp_path):
        # Once the compiler had exited, Stop found nothing to stop and the binary ran
        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        source = tmp_path / "quick.c"
        source.write_text("int main(){}", encoding="utf-8")
        window = CodeWindow()
        runner = FileRunnerProcess(window)
        window.runner = runner
        ended: list = []
        window.run_ended = lambda: ended.append(True)

        runner.run_file(_compile_config(_fake_compiler(tmp_path)), str(source))
        runner.process.wait(30)
        runner.stop()
        _run_events_until(qt_app, lambda: ended)

        text = window.code_result.toPlainText()
        assert "[Stopped]" in text
        assert "[Run]" not in text


def _logging_package(folder: Path, log: Path, seconds: float) -> None:
    """A stand-in automation package: logs when it starts and ends on the file it is given."""
    package = folder / "fakepkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(
        "import sys, time\n"
        f"log = {str(log)!r}\n"
        "name = sys.argv[sys.argv.index('--execute_file') + 1]\n"
        "open(log, 'a', encoding='utf-8').write(f'start {name}\\n')\n"
        f"time.sleep({seconds})\n"
        "open(log, 'a', encoding='utf-8').write(f'end {name}\\n')\n",
        encoding="utf-8")


class TestRunningAFolder:
    """The files of a folder run one after another: their reports went to one file."""

    def _files(self, folder: Path, count: int) -> list[str]:
        files = []
        for index in range(count):
            path = folder / f"case{index}.json"
            path.write_text("[]", encoding="utf-8")
            files.append(str(path))
        return files

    def test_each_file_starts_after_the_one_before_has_ended(self, qt_app, tmp_path, monkeypatch):
        from pybreeze.extend.process_executor.process_executor_utils import run_one_after_another

        log = tmp_path / "log.txt"
        _logging_package(tmp_path, log, seconds=0.5)
        monkeypatch.setenv("PYTHONPATH", str(tmp_path))
        main_window = MainWindow(python_compiler=sys.executable)
        files = self._files(tmp_path, 3)

        run_one_after_another(main_window, "fakepkg", files)
        _run_events_until(qt_app, lambda: log.exists() and log.read_text(encoding="utf-8").count("end") == 3)

        events = log.read_text(encoding="utf-8").split()
        assert events == [word for name in files for word in ("start", name, "end", name)]
        assert len(main_window.current_run_code_window) == 3

    def test_a_stopped_run_ends_the_batch(self, qt_app, tmp_path, monkeypatch):
        from pybreeze.extend.process_executor.process_executor_utils import run_one_after_another

        log = tmp_path / "log.txt"
        _logging_package(tmp_path, log, seconds=20)
        monkeypatch.setenv("PYTHONPATH", str(tmp_path))
        main_window = MainWindow(python_compiler=sys.executable)

        run_one_after_another(main_window, "fakepkg", self._files(tmp_path, 3))
        first = main_window.current_run_code_window[0]
        _run_events_until(qt_app, lambda: log.exists())
        first.stop_runner()
        _run_events_until(qt_app, lambda: "Task exit with code" in first.code_result.toPlainText())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.05)

        assert len(main_window.current_run_code_window) == 1


def _is_running(pid: int) -> bool:
    """Whether a process with *pid* is still there (not os.kill: on Windows that ends it)."""
    import subprocess

    listed = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True,
                            text=True, timeout=30, check=False)
    return str(pid) in listed.stdout


@pytest.mark.skipif(os.name != "nt", reason="checked with tasklist")
def test_stop_ends_what_the_run_started_too(qt_app, tmp_path):
    # A launcher's program (go run, cargo run) or a web run's browser was left
    # running: only the direct child was stopped
    from pybreeze.extend.process_executor.process_executor_utils import build_task_process

    script = tmp_path / "launcher.py"
    script.write_text(
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print('grandchild', child.pid, flush=True)\n"
        "time.sleep(60)\n",
        encoding="utf-8")
    main_window = MainWindow(python_compiler=sys.executable)
    build_task_process(main_window).start_module_process(
        "launcher", [], environment={"PYTHONPATH": str(tmp_path)})
    run_window = main_window.current_run_code_window[0]
    _run_events_until(qt_app, lambda: "grandchild" in run_window.code_result.toPlainText())
    line = next(text for text in run_window.code_result.toPlainText().splitlines() if text.startswith("grandchild"))
    grandchild = int(line.split()[1])
    try:
        run_window.stop_runner()
        _run_events_until(qt_app, lambda: "Task exit with code" in run_window.code_result.toPlainText())

        assert not _is_running(grandchild)
    finally:
        _stop_grandchild(run_window.code_result.toPlainText())



class TestTextInAnyLanguage:
    """A folder and output in Chinese, and a character outside the BMP, reach the run window intact."""

    _TEXT = "你好，世界 🙂 naïve"

    def test_a_package_run(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        folder = tmp_path / "中文資料夾"
        folder.mkdir()
        data = folder / "資料.json"
        data.write_text(json.dumps({"問候": self._TEXT}, ensure_ascii=False), encoding="utf-8")
        process = build_task_process(MainWindow(sys.executable))

        process.start_module_process("json.tool", ["--no-ensure-ascii", str(data)])
        _run_events_until(qt_app, lambda: process.process is None)

        text = process.main_window.code_result.toPlainText()
        assert f'"問候": "{self._TEXT}"' in text
        assert text.endswith("Task exit with code 0\n")

    def test_a_run_with_run(self, qt_app, tmp_path):
        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        folder = tmp_path / "中文資料夾"
        folder.mkdir()
        script = folder / "腳本.py"
        script.write_text(
            "import sys\n"
            f"print({self._TEXT!r})\n"
            f"print('錯誤：' + {self._TEXT!r}, file=sys.stderr)\n",
            encoding="utf-8",
        )
        window = CodeWindow()
        runner = FileRunnerProcess(window)

        runner.run_file({"name": "Python", "compiler": sys.executable}, str(script))
        _run_events_until(qt_app, lambda: runner.process is None)

        text = window.code_result.toPlainText()
        assert f"{self._TEXT}\n" in text
        assert f"錯誤：{self._TEXT}\n" in text
        assert text.endswith("[Process exited with code 0]\n")

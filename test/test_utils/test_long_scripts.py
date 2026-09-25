"""A script too long for a Windows command line still runs.

Running the tab in front passes its script as ``--execute_str``; past Windows'
limit of 32,767 characters the child did not start at all ("could not start").
"""
from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

_REPORTER = """
import json, sys
flag, value = sys.argv[1], sys.argv[2]
if flag == "--execute_file":
    with open(value, encoding="ascii") as handle:
        value = handle.read()
actions = json.loads(value)
if isinstance(actions, str):
    actions = json.loads(actions)  # on Windows --execute_str carries the script JSON-encoded once more
print(json.dumps({"flag": flag, "count": len(actions), "last": actions[-1]}))
"""


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def reporter(tmp_path, monkeypatch):
    """A package that says which flag it was given and what it read, in ASCII."""
    (tmp_path / "report_args.py").write_text(_REPORTER, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    return "report_args"


def _run(app, package: str, script: str, done=None):
    from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager
    from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

    class Window:
        python_compiler = sys.executable

    window = CodeWindow()
    window.main_window = Window()
    manager = TaskProcessManager(window, task_done_trigger_function=done)
    manager.renew_path = lambda: True
    manager.compiler_path = sys.executable
    manager.start_test_process(package, script)
    written = manager._script_file
    deadline = time.monotonic() + 30
    while manager.still_run_program and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    output = window.code_result.toPlainText()
    report = json.loads(next(line for line in output.splitlines() if line.startswith("{")))
    assert not window.stop_button.isEnabled()  # run_ended() was called
    return report, written, manager


@pytest.mark.skipif(sys.platform != "win32", reason="the command-line limit is Windows'")
def test_a_long_script_goes_as_a_file_and_the_file_goes_after(app, reporter):
    actions = [["AC_type_keyboard", {"text": "中文 " + "x" * 50}] for _ in range(600)]
    script = json.dumps(actions, ensure_ascii=False)
    assert len(script) > 32_767

    report, written, manager = _run(app, reporter, script)

    assert report == {"flag": "--execute_file", "count": 600, "last": actions[-1]}
    assert written is not None
    assert not written.exists()
    assert manager._script_file is None


def test_a_short_script_still_goes_on_the_command_line(app, reporter):
    report, written, _manager = _run(app, reporter, '[["AC_type_keyboard", {"text": "hi"}]]')

    assert report == {"flag": "--execute_str", "count": 1, "last": ["AC_type_keyboard", {"text": "hi"}]}
    assert written is None


def test_a_long_script_that_is_not_json_is_written_as_it_is(app):
    # The package reports what is wrong with it, as it would have on the command line
    from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager
    from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

    manager = TaskProcessManager(CodeWindow())
    script = "not json, " * 5000

    written = manager._write_script_file(script)

    assert written.read_text(encoding="utf-8") == script
    manager._remove_script_file()
    assert not written.exists()


def test_a_done_hook_that_fails_is_logged_and_the_run_still_ends(app, reporter, monkeypatch):
    # The hook is the report mail's: its failure must not leave the run window running
    from pybreeze.extend.process_executor import python_task_process_manager

    logged: list = []
    monkeypatch.setattr(python_task_process_manager.pybreeze_logger, "error", lambda *args: logged.append(args))

    def failing_hook() -> None:
        raise RuntimeError("the mail server said no")

    report, _written, _manager = _run(app, reporter, '[["AC_type_keyboard", {"text": "hi"}]]', done=failing_hook)

    assert report["count"] == 1
    assert any("the mail server said no" in repr(entry) for entry in logged)

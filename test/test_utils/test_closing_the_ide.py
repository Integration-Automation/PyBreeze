"""Closing the IDE stops the runs it started.

A run's child is a separate process: nothing ends it when the IDE exits, and it
runs without a console, so one left behind keeps going unseen until it is found
in a task manager.
"""
from __future__ import annotations

from test_utils.started_window import run_started_window

_CLOSE_WITH_A_RUN_GOING = """
import subprocess
from pybreeze.extend.process_executor.process_executor_utils import build_task_process
# This interpreter: left unchosen, a run looks for one on PATH, which may be a
# stub that exits at once instead of a Python that sleeps.
window.python_compiler = sys.executable
build_task_process(window).start_module_process(
    "timeit", ["-n", "1", "-r", "1", "import time; time.sleep(60)"])
child = window.current_run_code_window[0].runner.process
running_before = child.poll() is None
window.close()
try:
    child.wait(timeout=15)
except subprocess.TimeoutExpired:
    child.kill()
    stopped = False
else:
    stopped = True
result = {"running_before": running_before, "stopped": stopped}
"""


def test_closing_the_ide_stops_a_run_still_going(tmp_path):
    seen = run_started_window(tmp_path, _CLOSE_WITH_A_RUN_GOING)

    assert seen["running_before"]
    assert seen["stopped"]

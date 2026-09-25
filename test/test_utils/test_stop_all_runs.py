"""Run > Stop All Program stops PyBreeze's runs too, not only JEditor's.

JEditor's Stop All Program stops the programs its own menus started. An
automation script, a package install or a Run with... run shows in a run window
of PyBreeze's, and went on after it.
"""
from __future__ import annotations

from test_utils.started_window import run_started_window

_BODY = """
class FakeRunWindow:
    stopped = 0

    def stop_runner(self):
        FakeRunWindow.stopped += 1


class BrokenRunWindow:
    def stop_runner(self):
        raise RuntimeError("its process is gone")


window.current_run_code_window.extend([FakeRunWindow(), BrokenRunWindow(), FakeRunWindow()])
window.run_menu.stop_all_program_action.trigger()
result = {"stopped": FakeRunWindow.stopped, "kept": len(window.current_run_code_window)}
# The fakes cannot close: the harness closes the window next
window.current_run_code_window.clear()
"""


def test_stop_all_program_stops_every_run_window(tmp_path):
    # One whose stop fails costs only its own stop; the windows stay, with their output
    assert run_started_window(tmp_path, _BODY) == {"stopped": 2, "kept": 3}


_CLOSED_WINDOW = """
from pybreeze.extend.process_executor.process_executor_utils import open_run_window


class StillRunning:
    def poll(self):
        return None


class Runner:
    process = StillRunning()
    stopped = 0

    def stop(self):
        Runner.stopped += 1


run_window = open_run_window(window, "a long run")
run_window.runner = Runner()
run_window.show()
run_window.close()
kept = run_window in window.current_run_code_window
window.run_menu.stop_all_program_action.trigger()
result = {"kept after closing": kept, "stopped": Runner.stopped}
run_window.runner = None
window.current_run_code_window.clear()
"""


def test_a_run_whose_window_was_closed_can_still_be_stopped(tmp_path):
    # Closing a run window lets its run go on (progress #2): Stop All Program
    # is how it is stopped without closing the IDE
    assert run_started_window(tmp_path, _CLOSED_WINDOW) == {"kept after closing": True, "stopped": 1}

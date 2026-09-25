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

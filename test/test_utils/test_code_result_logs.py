"""Only warnings and errors from loggers reach the editor's Code Result panel.

JEditor hooks a handler onto every logger that exists when the window is built
and shows what it receives in the panel, in red. The automation packages set the
root logger to DEBUG as they import, so opening a file there filled the panel
with gitpython's ``Popen(['git', 'cat-file', ...])`` lines, and PyBreeze's own
debug records went there too.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_utils.started_window import run_started_window

_EMIT_AND_READ = """
import logging
from je_editor.utils.redirect_manager.redirect_manager_class import redirect_manager_instance
queue = redirect_manager_instance.std_err_queue
while not queue.empty():
    queue.get_nowait()
logging.getLogger("git.util").debug("library debug")
logging.getLogger("urllib3.connectionpool").debug("connection debug")
logging.getLogger("Pybreeze").info("own info")
logging.getLogger("git.util").warning("library warning")
logging.getLogger("Pybreeze").error("own error")
result = []
while not queue.empty():
    result.append(queue.get_nowait())
"""


def test_debug_and_info_records_stay_out_of_code_result(tmp_path):
    shown = "\n".join(run_started_window(tmp_path, _EMIT_AND_READ))

    assert "library debug" not in shown
    assert "connection debug" not in shown
    assert "own info" not in shown
    assert "library warning" in shown
    assert "own error" in shown

"""Start the real main window in a child interpreter and read back what it saw.

A child keeps the test process safe: a Qt crash while the window is being built
(an access violation) cannot be caught inside pytest. The child writes its
findings to a file, because JEditor redirects ``sys.stdout`` into its own
console widget once the window exists.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_START_TIMEOUT_SECONDS = 120

_PRELUDE = """
import gc, json, sys
from PySide6.QtWidgets import QApplication
app = QApplication([])
from je_editor import language_wrapper
from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow
window = PyBreezeMainWindow(debug_mode=True)
gc.collect()
"""

# The window is closed before the child ends, even when the body did not close
# it: leaving it open lets the interpreter tear down a JEditor toolbar thread
# that may still be running, and Qt aborts the process (exit 0xC0000409) when a
# running QThread is destroyed. That made this harness fail about one run in ten
# on a busy machine, with nothing in the output to say why.
_REPORT = """
window.close()
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(result, handle, ensure_ascii=False)
"""


def run_started_window(tmp_path: Path, body: str, *, saved_language: str | None = None) -> object:
    """Start the IDE in a child, run *body* there, and return the ``result`` it set.

    *body* runs after the window is built and garbage has been collected, with
    ``window`` and ``language_wrapper`` in scope; it must assign a JSON-able
    value to ``result``. The child's working directory is *tmp_path*, which is
    where JEditor looks for its settings, so *saved_language* is written there
    as the saved language before the start.
    """
    if saved_language is not None:
        settings_dir = tmp_path / ".jeditor"
        settings_dir.mkdir()
        (settings_dir / "user_setting.json").write_text(
            json.dumps({"language": saved_language}), encoding="utf-8")
    result_file = tmp_path / "result.json"
    environment = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(_REPOSITORY_ROOT), os.environ.get("PYTHONPATH")])),
    }
    completed = subprocess.run(  # noqa: S603 — fixed argv: this interpreter and a script built from literals
        [sys.executable, "-c", _PRELUDE + body + _REPORT, str(result_file)],
        cwd=tmp_path, env=environment, capture_output=True, timeout=_START_TIMEOUT_SECONDS,
        check=False, shell=False,
    )
    assert completed.returncode == 0, (
        f"the IDE did not start (exit {completed.returncode})\n"
        f"{completed.stderr.decode('utf-8', 'replace')[-2000:]}")
    return json.loads(result_file.read_text(encoding="utf-8"))

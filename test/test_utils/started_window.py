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

# A modal dialog in a child nobody watches waits for ever: the run timed out
# after two minutes with nothing to say what was on screen. Each one open when
# the watch looks is noted and closed, and the test fails naming it.
_MODAL_WATCH_MS = 3000

_PRELUDE = f"""
import gc, json, sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
app = QApplication([])
from je_editor import language_wrapper
from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow
_modal_dialogs = []
def _close_a_waiting_dialog():
    dialog = QApplication.activeModalWidget()
    if dialog is not None:
        text = dialog.text() if hasattr(dialog, "text") else ""
        _modal_dialogs.append(dialog.windowTitle() + ": " + text)
        dialog.reject()
_modal_watch = QTimer()
_modal_watch.timeout.connect(_close_a_waiting_dialog)
_modal_watch.start({_MODAL_WATCH_MS})
"""

_BUILD_WINDOW = """
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
with open(sys.argv[1] + ".modal", "w", encoding="utf-8") as handle:
    json.dump(_modal_dialogs, handle, ensure_ascii=False)
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(result, handle, ensure_ascii=False)
"""


def run_started_window(
        tmp_path: Path, body: str, *, saved_language: str | None = None,
        before_window: str = "", saved_settings: dict | None = None,
        build: str = _BUILD_WINDOW) -> object:
    """Start the IDE in a child, run *body* there, and return the ``result`` it set.

    *body* runs after the window is built and garbage has been collected, with
    ``window`` and ``language_wrapper`` in scope; it must assign a JSON-able
    value to ``result``. The child's working directory is *tmp_path*, which is
    where JEditor looks for its settings, so *saved_language* is written there
    as the saved language before the start. *before_window* runs after the
    application exists and before the window is built -- to register an
    ``EDITOR_EXTEND_TAB``, say. *saved_settings* are further saved settings
    (``{"ui_style": ...}``), and *build* replaces the code that builds
    ``window`` -- to start it the way ``start_editor`` does, say.
    """
    settings = dict(saved_settings or {})
    if saved_language is not None:
        settings["language"] = saved_language
    if settings:
        settings_dir = tmp_path / ".jeditor"
        settings_dir.mkdir()
        (settings_dir / "user_setting.json").write_text(json.dumps(settings), encoding="utf-8")
    result_file = tmp_path / "result.json"
    environment = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(_REPOSITORY_ROOT), os.environ.get("PYTHONPATH")])),
    }
    try:
        completed = subprocess.run(  # noqa: S603 — fixed argv: this interpreter and a script built from literals
            [sys.executable, "-c", _PRELUDE + before_window + build + body + _REPORT,
             str(result_file)],
            cwd=tmp_path, env=environment, capture_output=True, timeout=_START_TIMEOUT_SECONDS,
            check=False, shell=False,
        )
    except subprocess.TimeoutExpired as error:
        raise AssertionError(
            f"the IDE did not finish in {_START_TIMEOUT_SECONDS} s\n{_tail(error.stderr)}") from None
    assert completed.returncode == 0, (
        f"the IDE did not start (exit {completed.returncode})\n{_tail(completed.stderr)}")
    modal = json.loads((tmp_path / "result.json.modal").read_text(encoding="utf-8"))
    assert modal == [], f"a modal dialog opened and would have waited for ever: {modal}"
    return json.loads(result_file.read_text(encoding="utf-8"))


def _tail(output: bytes | None) -> str:
    """The end of what the child wrote, for a failure message."""
    return (output or b"").decode("utf-8", "replace")[-2000:]

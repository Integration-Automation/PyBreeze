"""Starting the real main window with a language other than English saved.

JEditor picks the saved language inside ``EditorMain.__init__`` and serves it
from a merged copy of its dictionaries. PyBreeze's strings have to be in by
then; when they were added afterwards, every PyBreeze menu got a ``None`` title
and Qt crashed the process (access violation) before the window appeared. A
crash like that cannot be caught inside pytest, so each start runs in a child.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_START_TIMEOUT_SECONDS = 120

# The child writes what it saw to a file: JEditor redirects sys.stdout into
# its own console widget once the window exists.
_CHILD = """
import json, sys
from PySide6.QtWidgets import QApplication
app = QApplication([])
from je_editor import language_wrapper
from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow
window = PyBreezeMainWindow(debug_mode=True)
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump({
        "language": language_wrapper.language,
        "menu_titles": [action.text() for action in window.menuBar().actions()],
        "automation_menu": window.automation_menu.title(),
        "window_title": window.windowTitle(),
    }, handle, ensure_ascii=False)
"""


def _start_with_saved_language(tmp_path: Path, language: str) -> dict:
    settings_dir = tmp_path / ".jeditor"
    settings_dir.mkdir()
    (settings_dir / "user_setting.json").write_text(
        json.dumps({"language": language}), encoding="utf-8")
    result_file = tmp_path / "result.json"
    environment = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(_REPOSITORY_ROOT), os.environ.get("PYTHONPATH")])),
    }
    completed = subprocess.run(  # noqa: S603 — fixed argv: this interpreter and a literal script
        [sys.executable, "-c", _CHILD, str(result_file)],
        cwd=tmp_path, env=environment, capture_output=True, timeout=_START_TIMEOUT_SECONDS,
        check=False, shell=False,
    )
    assert completed.returncode == 0, (
        f"the IDE did not start with {language} saved (exit {completed.returncode})\n"
        f"{completed.stderr.decode('utf-8', 'replace')[-2000:]}")
    return json.loads(result_file.read_text(encoding="utf-8"))


@pytest.mark.parametrize("language", ["Traditional_Chinese", "Japanese"])
def test_the_ide_starts_with_the_saved_language(tmp_path, language):
    seen = _start_with_saved_language(tmp_path, language)

    assert seen["language"] == language
    assert all(seen["menu_titles"]), seen["menu_titles"]
    assert seen["automation_menu"]
    assert seen["window_title"] == "PyBreeze"

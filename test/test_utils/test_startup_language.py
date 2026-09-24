"""Starting the real main window with a language other than English saved.

JEditor picks the saved language inside ``EditorMain.__init__`` and serves it
from a merged copy of its dictionaries. PyBreeze's strings have to be in by
then; when they were added afterwards, every PyBreeze menu got a ``None`` title
and Qt crashed the process (access violation) before the window appeared.
"""
from __future__ import annotations

import pytest

from test_utils.started_window import run_started_window

_REPORT_WHAT_STARTED = """
result = {
    "language": language_wrapper.language,
    "menu_titles": [action.text() for action in window.menuBar().actions()],
    "automation_menu": window.automation_menu.title(),
    "window_title": window.windowTitle(),
}
"""


@pytest.mark.parametrize("language", ["Traditional_Chinese", "Japanese"])
def test_the_ide_starts_with_the_saved_language(tmp_path, language):
    seen = run_started_window(tmp_path, _REPORT_WHAT_STARTED, saved_language=language)

    assert seen["language"] == language
    assert all(seen["menu_titles"]), seen["menu_titles"]
    assert seen["automation_menu"]
    assert seen["window_title"] == "PyBreeze"

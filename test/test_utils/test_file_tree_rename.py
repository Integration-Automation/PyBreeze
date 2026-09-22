"""Renaming an open file, or its folder, from the file tree.

The open tab and its auto-save have to follow the file. Left behind, JEditor's
auto-save wrote the buffer back to the old name -- recreating the file the user
had just renamed away -- and never saved the new one again.
"""
from __future__ import annotations

from test_utils.started_window import run_started_window

_RENAME = """
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication, QTreeView
from pybreeze.pybreeze_ui.editor_main import file_tree_context_menu as menu

here = Path.cwd()
folder = here / "project"
folder.mkdir()
original = folder / "a.py"
original.write_text("x = 1\\n", encoding="utf-8")
window.go_to_new_tab(original)
editor = window.tab_widget.currentWidget()

RENAME_WHAT, NEW_NAME = {what!r}, {new_name!r}
renamed = original if RENAME_WHAT == "file" else folder
menu.QInputDialog.getText = staticmethod(lambda *args, **kwargs: (NEW_NAME, True))
menu._action_rename(QTreeView(), window, renamed)
expected = (folder / NEW_NAME) if RENAME_WHAT == "file" else (here / NEW_NAME / "a.py")

editor.code_edit.setPlainText("x = 2\\n")
deadline = time.monotonic() + 15
while time.monotonic() < deadline:
    QApplication.processEvents()
    if expected.is_file() and "x = 2" in expected.read_text(encoding="utf-8"):
        break
    time.sleep(0.1)

result = {{
    "tab_file": str(Path(editor.current_file)) == str(expected),
    "saved_to_new": expected.is_file() and "x = 2" in expected.read_text(encoding="utf-8"),
    "old_came_back": original.exists(),
}}
"""


def _rename(tmp_path, what: str, new_name: str) -> dict:
    return run_started_window(tmp_path, _RENAME.format(what=what, new_name=new_name))


def test_a_renamed_file_is_saved_under_its_new_name(tmp_path):
    seen = _rename(tmp_path, "file", "b.py")

    assert seen["tab_file"]
    assert seen["saved_to_new"], "the new name never got the edit"
    assert not seen["old_came_back"], "auto-save recreated the old name"


def test_a_file_in_a_renamed_folder_follows_it(tmp_path):
    seen = _rename(tmp_path, "folder", "renamed_project")

    assert seen["tab_file"]
    assert seen["saved_to_new"], "the file under the new folder never got the edit"
    assert not seen["old_came_back"], "auto-save recreated the old folder"

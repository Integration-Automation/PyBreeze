"""The theme ``start_editor(theme=...)`` is given is the one the IDE shows.

JEditor's ``startup_setting()`` applies the saved theme (``dark_amber.xml`` until
one is picked from UI Style) after the window is shown, over the one
``start_editor`` had applied, so the argument never showed at all.
"""
from __future__ import annotations

from test_utils.started_window import run_started_window

_OPEN = """
import os
from pybreeze.pybreeze_ui.editor_main.main_ui import open_main_window
from je_editor.pyside_ui.main_ui.save_settings.user_setting_file import user_setting_dict
window = open_main_window(app, debug_mode=True{theme})
gc.collect()
"""

_READ = """
result = {"shown": os.environ.get("QTMATERIAL_THEME"), "saved": user_setting_dict.get("ui_style")}
"""


def _start(tmp_path, theme: str | None = None, saved: str | None = None) -> dict:
    return run_started_window(
        tmp_path, _READ, build=_OPEN.format(theme="" if theme is None else f", theme={theme!r}"),
        saved_settings={"ui_style": saved} if saved else None)


def test_a_theme_given_at_launch_is_the_one_shown(tmp_path):
    assert _start(tmp_path, theme="dark_teal.xml") == {"shown": "dark_teal.xml", "saved": "dark_teal.xml"}


def test_a_theme_given_at_launch_replaces_the_one_picked_before(tmp_path):
    assert _start(tmp_path, theme="dark_teal.xml", saved="light_blue.xml")["shown"] == "dark_teal.xml"


def test_without_one_the_theme_picked_before_is_shown(tmp_path):
    assert _start(tmp_path, saved="light_blue.xml")["shown"] == "light_blue.xml"


def test_without_either_the_default_is_shown(tmp_path):
    assert _start(tmp_path)["shown"] == "dark_amber.xml"

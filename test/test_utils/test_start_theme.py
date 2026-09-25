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


_COUNT_THEMES = """
applied = []
_set_style_sheet = QApplication.setStyleSheet
def _counting(self, sheet):
    applied.append(len(sheet))
    return _set_style_sheet(self, sheet)
QApplication.setStyleSheet = _counting
"""

_READ_COUNT = """
from PySide6.QtWidgets import QToolBar
for _ in range(5):
    app.processEvents()
result = {"shown": os.environ.get("QTMATERIAL_THEME"), "applied": len(applied),
          "toolbar": window.findChildren(QToolBar)[0].height()}
"""


def _count(tmp_path, theme: str | None = None, saved: str = "light_blue.xml") -> dict:
    return run_started_window(
        tmp_path, _READ_COUNT, before_window=_COUNT_THEMES,
        build=_OPEN.format(theme="" if theme is None else f", theme={theme!r}"),
        saved_settings={"ui_style": saved})


def test_the_saved_theme_is_applied_once(tmp_path):
    # The window applies the saved settings as it is built; they were applied
    # twice more after it (about 0.7 s and 0.9 s of the start)
    seen = _count(tmp_path)
    assert (seen["shown"], seen["applied"]) == ("light_blue.xml", 1)


def test_a_theme_given_at_launch_is_applied_once_over_the_saved_one(tmp_path):
    seen = _count(tmp_path, theme="dark_teal.xml")
    assert (seen["shown"], seen["applied"]) == ("dark_teal.xml", 2)


def test_the_window_looks_the_same_with_the_theme_given_or_saved(tmp_path):
    # Applied once, the theme left the toolbar 4 px taller than a theme given
    # at launch, which applies the settings again
    for folder in ("saved", "given"):
        (tmp_path / folder).mkdir()
    saved = _count(tmp_path / "saved", saved="dark_amber.xml")
    given = _count(tmp_path / "given", theme="dark_amber.xml", saved="dark_amber.xml")

    assert saved["toolbar"] == given["toolbar"]


def test_settings_that_fail_to_apply_still_leave_the_theme_given(monkeypatch):
    # The saved settings (and the files they reopen) can be anything: a bad
    # one used to stop the start before the theme was applied
    from pybreeze.pybreeze_ui.editor_main import main_ui

    applied: list = []
    logged: list = []
    monkeypatch.setitem(main_ui.user_setting_dict, "ui_style", "dark_amber.xml")
    monkeypatch.setattr(main_ui, "apply_stylesheet", lambda app, theme: applied.append((app, theme)))
    monkeypatch.setattr(main_ui.pybreeze_logger, "error", lambda *args: logged.append(args))

    class Window:
        def startup_setting(self) -> None:
            raise KeyError("font_size")

    app = object()
    main_ui._apply_given_theme(app, Window(), "dark_teal.xml")

    assert main_ui.user_setting_dict["ui_style"] == "dark_teal.xml"
    assert applied == [(app, "dark_teal.xml")]
    assert logged

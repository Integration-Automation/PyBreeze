"""Every submenu of the started IDE still has entries once garbage is collected.

A QAction added to a menu is not owned by the menu. One built with no parent and
kept only in a local variable is deleted when its builder returns, and the menu
it was added to is left empty: that is how every Run, HELP and Project submenu
of the automation menus came up empty.

JEditor's two font menus are left out: they list the platform's font families,
and the offscreen platform the tests run on has none.
"""
from __future__ import annotations

from test_utils.started_window import run_started_window

_REPORT_EMPTY_SUBMENUS = """
font_menus = [window.file_menu.font_menu, window.text_menu.font_menu]

def empty_submenus(menu, path):
    empty = []
    for action in menu.actions():
        submenu = action.menu()
        if submenu is None or submenu in font_menus:
            continue
        where = path + [action.text()]
        if not submenu.actions():
            empty.append(" > ".join(where))
        empty.extend(empty_submenus(submenu, where))
    return empty

result = {
    "automation_entries": len(window.automation_menu.actions()),
    "empty": [
        entry
        for top in window.menuBar().actions() if top.menu() is not None
        for entry in empty_submenus(top.menu(), [top.text()])
    ],
}
"""


def test_no_submenu_of_the_started_ide_is_empty(tmp_path):
    seen = run_started_window(tmp_path, _REPORT_EMPTY_SUBMENUS)

    assert seen["automation_entries"] > 0
    assert seen["empty"] == []



_REGISTER_A_BROKEN_AND_A_FINE_TAB = """
from pybreeze import EDITOR_EXTEND_TAB
from PySide6.QtWidgets import QWidget

class Broken(QWidget):
    def __init__(self):
        raise RuntimeError("a third-party tab that fails")

class Fine(QWidget):
    pass

EDITOR_EXTEND_TAB.update({"broken": Broken, "fine": Fine})
"""

_REPORT_THE_TABS = """
result = [window.tab_widget.tabText(index) for index in range(window.tab_widget.count())]
"""


def test_a_broken_extend_tab_costs_only_itself(tmp_path):
    # EDITOR_EXTEND_TAB is open to third parties: one constructor that raises
    # must not keep the IDE from starting.
    tabs = run_started_window(
        tmp_path, _REPORT_THE_TABS, before_window=_REGISTER_A_BROKEN_AND_A_FINE_TAB)

    assert "fine" in tabs
    assert "broken" not in tabs

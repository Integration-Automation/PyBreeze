"""Every tool fits a small screen: none asks for more room than a narrow window has.

A tab's least width is its widest row of controls, and a tab that does not fit
makes the whole window wider than the display. The Response Inspector's
hand-over buttons, the diagram editor's toolbar and the HAR importer's one-line
hint each asked for more than a 1280-pixel laptop has. Rows that may be long
wrap now (``design/flow_layout.py``), and this keeps it so for every tool,
counted in ems so that it holds at any font size.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QTabWidget

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.design.tokens import em
from pybreeze.pybreeze_ui.menu.tools import tools_menu

# The room a small window leaves a tool: with a 16-pixel font, 960 by 480 pixels
_MOST_WIDTH_EMS = 60
_MOST_HEIGHT_EMS = 30


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class _Main:
    """The little of the main window a tool's constructor touches."""

    def __init__(self) -> None:
        self.tab_widget = QTabWidget()
        self.current_run_code_window: list = []


@pytest.mark.parametrize("key", list(tools_menu.TOOLS))
def test_a_tool_asks_for_no_more_room_than_a_small_window_has(app, key, tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # the prompt editors and review stats live under ~
    monkeypatch.setenv("HOME", str(tmp_path))
    widget = tools_menu.build_tool_widget(_Main(), key)

    try:
        least = widget.minimumSizeHint()
        unit = em(widget)
        assert least.width() <= _MOST_WIDTH_EMS * unit, f"{key} needs {least.width() / unit:.0f} ems of width"
        assert least.height() <= _MOST_HEIGHT_EMS * unit, f"{key} needs {least.height() / unit:.0f} ems of height"
    finally:
        widget.close()
        widget.deleteLater()


def test_a_tool_gets_the_standard_gaps_around_its_content(app):
    from pybreeze.pybreeze_ui.design.tokens import Space, space

    widget = tools_menu.build_tool_widget(_Main(), "Hash")

    try:
        margins = widget.layout().contentsMargins()
        around = space(Space.NORMAL, widget)
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (around,) * 4
    finally:
        widget.close()
        widget.deleteLater()


def test_a_tool_that_fills_its_tab_keeps_its_edges(app):
    # The diagram editor's canvas runs to the edge of the tab on purpose
    widget = tools_menu.build_tool_widget(_Main(), "DiagramEditor")

    try:
        assert widget.layout().contentsMargins().isNull()
    finally:
        widget.close()
        widget.deleteLater()

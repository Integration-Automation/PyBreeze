"""Open one tool from another as a new, pre-filled tab.

Several tools hand a finding over to the tool that specialises in it — a status
code to the HTTP reference, a URL to the URL parser/builder, a header block to
the header analyzer. They all need the same three steps (find the main window's
tab widget, add the tab, focus it), so it lives here instead of in each tool.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget
from je_editor import language_wrapper

from pybreeze.utils.logging.logger import pybreeze_logger


def open_tool_tab(main_window, widget: QWidget, tab_label_key: str) -> QWidget | None:
    """Add *widget* as a new tab of *main_window* and make it the current tab.

    :param main_window: the window whose ``tab_widget`` the tab is added to;
        when it has none (or is ``None``) nothing happens
    :param widget: the tool widget to show, already pre-filled by the caller
    :param tab_label_key: language key of the new tab's label
    :return: *widget* when it was opened, otherwise ``None``
    """
    tab_widget = getattr(main_window, "tab_widget", None)
    if tab_widget is None:
        pybreeze_logger.info("tool_tabs.py no tab_widget to open the tool in")
        return None
    tab_widget.addTab(widget, language_wrapper.language_word_dict.get(tab_label_key))
    tab_widget.setCurrentWidget(widget)
    return widget

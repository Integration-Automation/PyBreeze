from __future__ import annotations

from typing import TYPE_CHECKING

from je_editor import MainBrowserWidget

from pybreeze.pybreeze_ui.busy_cursor import busy_cursor

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def open_web_browser(
        automation_editor_instance: PyBreezeMainWindow, url: str, tab_name: str) -> None:
    """Open *url* in a browser tab named *tab_name* and a number (a HELP entry's page)."""
    with busy_cursor():
        browser = MainBrowserWidget(start_url=url)
    automation_editor_instance.tab_widget.addTab(
        browser, f"{tab_name}{automation_editor_instance.tab_widget.count()}")

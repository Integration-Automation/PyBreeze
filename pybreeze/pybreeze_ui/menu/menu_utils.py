from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from je_editor import MainBrowserWidget

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def open_web_browser(
        automation_editor_instance: PyBreezeMainWindow, url: str, tab_name: str) -> None:
    """Open *url* in a browser tab named *tab_name* and a number (a HELP entry's page)."""
    with busy_cursor():
        browser = MainBrowserWidget(start_url=url)
    automation_editor_instance.tab_widget.addTab(
        browser, f"{tab_name}{automation_editor_instance.tab_widget.count()}")


@contextmanager
def busy_cursor() -> Iterator[None]:
    """Show the wait cursor while a menu entry builds its widget on the UI thread.

    The first browser tab starts Chromium (about 2.5 s), and some entries
    import their package the first time they open (the SSH client's
    paramiko, the Load Density GUI's locust): the IDE was held that long with
    nothing to show for it. The cursor goes back however the block ends.
    """
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()

"""busy_cursor: the wait cursor while something slow runs on the UI thread."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


@contextmanager
def busy_cursor() -> Iterator[None]:
    """Show the wait cursor while a slow widget is built on the UI thread.

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

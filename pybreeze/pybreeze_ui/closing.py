"""Closing a tab or a dock that may hold unsaved work: ask it first.

A widget that can lose work (the prompt editor, the diagram editor) offers
``may_close()``, which asks the user when there is something unsaved. JEditor's
tab and dock close without asking anything but its own editor tabs.
"""
from __future__ import annotations

from je_editor.pyside_ui.main_ui.dock.destroy_dock import DestroyDock

from pybreeze.utils.logging.logger import pybreeze_logger


def may_close(widget) -> bool:
    """Ask *widget* whether it may close, if it has a ``may_close()``; otherwise yes.

    A widget whose question raises (a third-party tab) counts as a yes, logged:
    it must not keep the IDE from closing.
    """
    ask = getattr(widget, "may_close", None)
    if not callable(ask):
        return True
    try:
        return bool(ask())
    except Exception as error:  # noqa: BLE001 — a third-party tab may raise anything; closing must go on
        pybreeze_logger.error("%s could not be asked whether it may close: %r", type(widget).__name__, error)
        return True


class AskingDock(DestroyDock):
    """A ``DestroyDock`` that asks its widget before closing.

    ``already_asked`` is set by the main window when the IDE closes: it asks
    every dock once, before stopping anything.
    """

    already_asked = False

    def closeEvent(self, event) -> None:
        if not self.already_asked and not may_close(self.widget()):
            event.ignore()
            return
        super().closeEvent(event)

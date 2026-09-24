"""Ctrl+Enter runs a tool: its text boxes take Enter as a new line."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractButton, QWidget

# The main keyboard's Enter and the keypad's
RUN_KEYS = ("Ctrl+Return", "Ctrl+Enter")
# How the button's tooltip names them
RUN_KEYS_SHOWN = "Ctrl+Enter"


def act_on_ctrl_enter(tool: QWidget, action: Callable[[], object]) -> None:
    """Let Ctrl+Enter anywhere in *tool* call *action*.

    The shortcuts are children of *tool*, so they go with it, and apply only
    while the focus is in it: a tool in a dock does not take the keys from the
    editor. Connect a bound method or a button's ``click``: a lambda holding
    *tool* would keep it alive.
    """
    for keys in RUN_KEYS:
        shortcut = QShortcut(QKeySequence(keys), tool)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(action)


def press_on_ctrl_enter(tool: QWidget, button: QAbstractButton) -> None:
    """Let Ctrl+Enter anywhere in *tool* press *button*, as a click would.

    A disabled button (a run still going) is not pressed. The button's tooltip
    names the keys.
    """
    act_on_ctrl_enter(tool, button.click)
    button.setToolTip(RUN_KEYS_SHOWN)

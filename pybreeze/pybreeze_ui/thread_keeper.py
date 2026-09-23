"""Let a worker QThread run out after the widget that started it has closed.

``if_alive`` lets a worker's signal reach its widget without keeping it alive.

A panel that closes while its request is still in flight has two bad options:
destroy the running QThread with it (Qt aborts the process), or wait for it on
the UI thread (the IDE freezes for as long as the request takes, up to its read
timeout). The third is to cut the thread off from the panel and keep it
referenced here until it ends.
"""
from __future__ import annotations

import warnings
import weakref
from collections.abc import Callable
from typing import TypeVar

from PySide6.QtCore import QThread

from pybreeze.utils.logging.logger import pybreeze_logger

_Widget = TypeVar("_Widget")

# Threads whose widget has gone, each kept until its finished signal
_OUTLIVING_THEIR_WIDGET: set[QThread] = set()


def let_run_out(thread: QThread, *signals) -> None:
    """Disconnect *signals* and *thread*'s own ``finished``, and keep it until it ends.

    :param thread: the worker still running
    :param signals: the worker's signals the widget was listening to
    """
    for signal in (*signals, thread.finished):
        # A signal with nothing connected is not an error here: PySide6 warns
        # about it (older versions raised), and there is nothing to cut off.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                signal.disconnect()
            except (RuntimeError, TypeError) as error:
                pybreeze_logger.debug("Worker signal had nothing connected: %r", error)
    _OUTLIVING_THEIR_WIDGET.add(thread)
    thread.finished.connect(lambda: _OUTLIVING_THEIR_WIDGET.discard(thread))


def is_kept(thread: QThread) -> bool:
    """Whether *thread* is being kept until it ends."""
    return thread in _OUTLIVING_THEIR_WIDGET


def if_alive(widget_ref: weakref.ref, act: Callable[[_Widget], None]) -> None:
    """Call *act* with the widget *widget_ref* points at, if it still exists.

    For a worker's signal whose slot needs more than a bound method can carry.
    A lambda holding the widget itself, connected to a thread the widget keeps,
    is a cycle through Qt that Python's collector cannot see: the closed and
    deleted widget stayed in memory with the thread. Connect
    ``lambda: if_alive(ref, lambda widget: ...)`` over a weak reference instead.
    """
    widget = widget_ref()
    if widget is not None:
        act(widget)

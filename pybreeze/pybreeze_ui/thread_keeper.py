"""Let a worker QThread run out after the widget that started it has closed.

A panel that closes while its request is still in flight has two bad options:
destroy the running QThread with it (Qt aborts the process), or wait for it on
the UI thread (the IDE freezes for as long as the request takes, up to its read
timeout). The third is to cut the thread off from the panel and keep it
referenced here until it ends.
"""
from __future__ import annotations

import warnings

from PySide6.QtCore import QThread

from pybreeze.utils.logging.logger import pybreeze_logger

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

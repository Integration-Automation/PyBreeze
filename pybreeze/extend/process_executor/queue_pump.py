"""Shared helper for the process-executor QTimer pump loop.

The Python task runner and the Test Pioneer runner both drain the same
``(output_queue, error_queue) → append_text`` pattern on a ~100 ms timer.
This module factors the per-tick drain into a single function so changes
(e.g., multi-message batching) can be made in one place.
"""
from __future__ import annotations

import queue
from collections.abc import Callable
from queue import Queue


def pump_message_queue(
    q: Queue,
    append_fn: Callable[[str, bool], None],
    *,
    is_error: bool,
) -> None:
    """Drain one pending message from *q* and forward it to *append_fn*.

    Silently ignores ``queue.Empty`` (the ``empty()`` check is racy) and empty
    strings after stripping.
    """
    try:
        if q.empty():
            return
        message = str(q.get_nowait()).strip()
        if message:
            append_fn(message, is_error)
    except queue.Empty:
        pass

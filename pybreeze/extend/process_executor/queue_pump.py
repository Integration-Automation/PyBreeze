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

# Drain up to this many messages per timer tick. Draining one line per ~100 ms
# tick caps throughput at ~10 lines/s and makes chatty scripts crawl; batching
# many lines per tick keeps up with bursty output while the bound keeps the UI
# thread from stalling when a process floods stdout.
MAX_MESSAGES_PER_PUMP = 256


def pump_message_queue(
    q: Queue,
    append_fn: Callable[[str, bool], None],
    *,
    is_error: bool,
    max_messages: int = MAX_MESSAGES_PER_PUMP,
) -> None:
    """Drain up to *max_messages* pending messages from *q* into *append_fn*.

    Stops early when the queue empties. Empty strings (after stripping) are
    skipped. ``queue.Empty`` from the racy non-blocking get is treated as a
    clean stop, not an error.
    """
    for _ in range(max_messages):
        try:
            message = str(q.get_nowait()).strip()
        except queue.Empty:
            return
        if message:
            append_fn(message, is_error)

"""Shared plumbing between a child process's pipes and its run window.

Every executor moves output the same way: a reader thread per pipe copies lines
into a ``Queue``, and a ~100 ms QTimer on the UI thread drains the queues into
the run window. This module holds both halves so a change (batching, EOF
handling, what counts as a line) is made in one place.
"""
from __future__ import annotations

import itertools
import queue
from collections.abc import Callable
from queue import Queue
from typing import IO

from pybreeze.utils.logging.logger import pybreeze_logger

# Drain up to this many messages per timer tick. Draining one line per ~100 ms
# tick caps throughput at ~10 lines/s and makes chatty scripts crawl; batching
# many lines per tick keeps up with bursty output while the bound keeps the UI
# thread from stalling when a process floods stdout.
MAX_MESSAGES_PER_PUMP = 256


def read_stream_into_queue(
    stream: IO,
    target_queue: Queue,
    *,
    buffer_size: int,
    encoding: str,
    keep_reading: Callable[[], bool],
) -> None:
    """Copy *stream* into *target_queue* line by line, exactly as read.

    Runs on a reader thread. Stops when *keep_reading* turns false or the pipe
    reaches EOF. Stopping on EOF (an empty read) is essential: without it the
    loop spins at 100% CPU re-reading a closed pipe until the QTimer notices the
    process exited. Lines keep their leading whitespace and line ending, and
    blank lines are kept, so the run window shows the output as it was written.
    """
    while keep_reading():
        try:
            line = stream.readline(buffer_size)
        except (OSError, ValueError) as error:
            # The pipe was closed underneath us during shutdown.
            pybreeze_logger.debug("Output reader stopped: %s", error)
            break
        if not line:
            break
        if isinstance(line, bytes):
            line = line.decode(encoding, "replace")
        target_queue.put(line)


def pump_message_queue(
    q: Queue,
    append_fn: Callable[[str, bool], None],
    *,
    is_error: bool,
    max_messages: int | None = MAX_MESSAGES_PER_PUMP,
) -> None:
    """Drain up to *max_messages* pending messages from *q* into *append_fn*.

    ``None`` drains until the queue is empty, which is what an executor wants
    once its process has exited. Messages are passed on unchanged; only empty
    strings are skipped. ``queue.Empty`` from the racy non-blocking get is
    treated as a clean stop, not an error.
    """
    budget = itertools.count() if max_messages is None else range(max_messages)
    for _ in budget:
        try:
            message = str(q.get_nowait())
        except queue.Empty:
            return
        if message:
            append_fn(message, is_error)

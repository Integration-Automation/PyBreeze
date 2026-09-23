"""Shared plumbing between a child process's pipes and its run window.

Every executor moves output the same way: a reader thread per pipe copies lines
into a ``Queue``, and a ~100 ms QTimer on the UI thread drains the queues into
the run window. This module holds both halves so a change (batching, EOF
handling, what counts as a line) is made in one place.
"""
from __future__ import annotations

import codecs
import itertools
import queue
import threading
import time
from collections.abc import Callable
from queue import Queue
from typing import IO

from pybreeze.utils.logging.logger import pybreeze_logger

# Drain up to this many messages per timer tick. Draining one line per ~100 ms
# tick caps throughput at ~10 lines/s and makes chatty scripts crawl; batching
# many lines per tick keeps up with bursty output while the bound keeps the UI
# thread from stalling when a process floods stdout.
MAX_MESSAGES_PER_PUMP = 256

# After the child exits, its readers get this long to reach end of file
READER_GRACE_SECONDS = 2.0

# Written when a process the run started still holds its output at the end
OUTPUT_STILL_HELD_NOTE = (
    "[A process started by this run still holds its output; what it writes from now on is not shown]\n")


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

    A line longer than *buffer_size* arrives in pieces, and a piece can end
    inside a multi-byte character or between the ``\\r`` and ``\\n`` of a line
    ending. The character is carried over by an incremental decoder, and a
    trailing ``\\r`` is held for the next piece: decoded on its own, the
    character showed as replacement marks, and the split line ending as a
    blank line.
    """
    decoder = _decoder_for(encoding)
    held = ""
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
            line = decoder.decode(line)
        line, held = held + line, ""
        if line.endswith("\r"):
            line, held = line[:-1], "\r"
        if line:
            target_queue.put(line)
    rest = held + decoder.decode(b"", final=True)
    if rest:
        target_queue.put(rest)


def _decoder_for(encoding: str) -> codecs.IncrementalDecoder:
    """An incremental decoder for *encoding*, or UTF-8's when there is no such codec."""
    try:
        return codecs.getincrementaldecoder(encoding)(errors="replace")
    except LookupError:
        pybreeze_logger.warning("Unknown output encoding %r; decoding as UTF-8", encoding)
        return codecs.getincrementaldecoder("utf-8")(errors="replace")


def any_alive(*readers: threading.Thread | None) -> bool:
    """True when one of *readers* is a thread still running."""
    return any(reader is not None and reader.is_alive() for reader in readers)


class ReaderGrace:
    """How long an exited child's reader threads still get before the run ends.

    A child's pipes reach end of file when the last process holding them
    exits, and that is not always the child: a process it started without
    redirecting its output keeps them open. The executors used to join each
    reader on the UI thread for up to two seconds, so such a run froze the IDE
    for four and still lost what came later. The pump now asks this, tick by
    tick, and ends the run once the readers are done or the grace is over.
    """

    def __init__(self) -> None:
        self._since: float | None = None

    def still_reading(self, *readers: threading.Thread | None) -> bool:
        """True while a reader is alive and the grace, counted from the first ask, is not over."""
        if not any_alive(*readers):
            return False
        if self._since is None:
            self._since = time.monotonic()
        return time.monotonic() - self._since < READER_GRACE_SECONDS

    def restart(self) -> None:
        """Count the next child's grace from its own exit."""
        self._since = None


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

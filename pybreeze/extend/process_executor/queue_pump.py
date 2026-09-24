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
from pybreeze.utils.terminal_text import split_unfinished_end

# Drain up to this many messages per timer tick. Draining one line per ~100 ms
# tick caps throughput at ~10 lines/s and makes chatty scripts crawl; batching
# many lines per tick keeps up with bursty output while the bound keeps the UI
# thread from stalling when a process floods stdout.
MAX_MESSAGES_PER_PUMP = 256

# After the child exits, its readers get this long to reach end of file, counted
# from the last tick that still brought output
READER_GRACE_SECONDS = 2.0
# ... and never longer than this after the exit, however much keeps coming
MAX_DRAIN_SECONDS = 30.0

# How many pieces of output wait between a reader and the window. A full queue
# makes the reader wait, and with it the child's writes to its pipe: the run
# goes at the pace the window shows it, as in a terminal. Unbounded, a script
# printing in a loop filled memory for as long as it ran, and Stop then poured
# the whole backlog into the window at once.
MAX_QUEUED_MESSAGES = 10000
# How often a reader waiting on a full queue checks whether to give up
_PUT_WAIT_SECONDS = 0.2

# Written when a process the run started still holds its output at the end
OUTPUT_STILL_HELD_NOTE = (
    "[A process started by this run still holds its output; what it writes from now on is not shown]\n")


def output_queue() -> Queue:
    """A queue for one pipe's output, holding at most ``MAX_QUEUED_MESSAGES`` pieces."""
    return Queue(maxsize=MAX_QUEUED_MESSAGES)


def _put(target_queue: Queue, message: str, keep_reading: Callable[[], bool]) -> bool:
    """Put *message* on *target_queue*, waiting while it is full; False once *keep_reading* turns false."""
    while True:
        try:
            target_queue.put(message, timeout=_PUT_WAIT_SECONDS)
            return True
        except queue.Full:
            if not keep_reading():
                return False


def read_stream_into_queue(
    stream: IO,
    target_queue: Queue,
    *,
    buffer_size: int,
    encoding: str,
    keep_reading: Callable[[], bool],
) -> None:
    """Copy *stream* into *target_queue* as it arrives, exactly as read.

    Runs on a reader thread. Stops when *keep_reading* turns false or the pipe
    reaches EOF. Stopping on EOF (an empty read) is essential: without it the
    loop spins at 100% CPU re-reading a closed pipe until the QTimer notices the
    process exited. Lines keep their leading whitespace and line ending, and
    blank lines are kept, so the run window shows the output as it was written.

    Whatever has arrived is read (``read1``), not a whole line: waiting for
    a newline hid a progress bar that rewinds with ``\\r``, and a status line
    printed without one, until the run's next newline, and then showed every
    step at once. A stream without ``read1`` (text mode) is read by line.

    A piece can end
    inside a multi-byte character or between the ``\\r`` and ``\\n`` of a line
    ending. The character is carried over by an incremental decoder, and a
    trailing ``\\r`` is held for the next piece: decoded on its own, the
    character showed as replacement marks, and the split line ending as a
    blank line. An escape sequence cut off at the end is held the same way.
    """
    decoder = _decoder_for(encoding)
    held = ""
    read = getattr(stream, "read1", None) or stream.readline
    while keep_reading():
        try:
            line = read(buffer_size)
        except (OSError, ValueError) as error:
            # The pipe was closed underneath us during shutdown.
            pybreeze_logger.debug("Output reader stopped: %s", error)
            break
        if not line:
            break
        if isinstance(line, bytes):
            line = decoder.decode(line)
        # An escape sequence cut off at the end waits for the rest: stripped
        # in two pieces, "\x1b[3" + "2m" showed "[32m" in the window
        line, held = split_unfinished_end(held + line)
        if line and not _put(target_queue, line, keep_reading):
            return
    rest = held + decoder.decode(b"", final=True)
    if rest:
        _put(target_queue, rest, keep_reading)


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
        self._exited_at: float | None = None
        self._since: float | None = None

    def still_reading(self, *readers: threading.Thread | None, progressed: bool = False) -> bool:
        """True while a reader is alive and the grace is not over.

        :param progressed: whether this tick showed any output. Output still
            coming counts the grace again, so a backlog held back by the full
            queue is shown, not taken for a process holding the pipes; but
            never past ``MAX_DRAIN_SECONDS`` after the first ask.
        """
        if not any_alive(*readers):
            return False
        now = time.monotonic()
        if self._exited_at is None:
            self._exited_at = self._since = now
        if progressed:
            self._since = now
        return (now - self._since < READER_GRACE_SECONDS
                and now - self._exited_at < MAX_DRAIN_SECONDS)

    def restart(self) -> None:
        """Count the next child's grace from its own exit."""
        self._exited_at = self._since = None


def pump_message_queue(
    q: Queue,
    append_fn: Callable[[str, bool], None],
    *,
    is_error: bool,
    max_messages: int | None = MAX_MESSAGES_PER_PUMP,
) -> int:
    """Drain up to *max_messages* pending messages from *q* into *append_fn*.

    ``None`` drains until the queue is empty, which is what an executor wants
    once its process has exited. Messages are passed on unchanged; only empty
    strings are skipped. ``queue.Empty`` from the racy non-blocking get is
    treated as a clean stop, not an error.

    :return: how many messages were taken off the queue
    """
    budget = itertools.count() if max_messages is None else range(max_messages)
    taken = 0
    for _ in budget:
        try:
            message = str(q.get_nowait())
        except queue.Empty:
            return taken
        taken += 1
        if message:
            append_fn(message, is_error)
    return taken

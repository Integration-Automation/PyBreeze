"""Read a file the user opens, refusing one too large to read on the UI thread.

The HAR tab and the diagram editor read the file they open whole, then parse
it, on the UI thread: a multi-gigabyte file froze the IDE, and the
``MemoryError`` it could end in escaped the slot unhandled.
"""
from __future__ import annotations

import errno
from pathlib import Path

#: The largest file opened: a HAR export with response bodies runs to tens of MB
MAX_OPEN_BYTES = 100 * 1024 * 1024
_MEGABYTE = 1024 * 1024


class FileTooLargeError(OSError):
    """The file is larger than it may be to be opened; ``strerror`` says so."""


def read_text_capped(path: Path, encoding: str = "utf-8", max_bytes: int | None = None) -> str:
    """The text of *path*, when it is no larger than *max_bytes* (``MAX_OPEN_BYTES`` by default).

    :raises FileTooLargeError: when it is larger (an ``OSError``, so a caller's
        read-error handling reports it, ``strerror`` included)
    :raises OSError: when it cannot be read
    :raises UnicodeDecodeError: when it is not in *encoding*
    """
    limit = MAX_OPEN_BYTES if max_bytes is None else max_bytes
    size = path.stat().st_size
    if size > limit:
        raise FileTooLargeError(
            errno.EFBIG,
            f"the file is {size / _MEGABYTE:.0f} MB; files over {limit // _MEGABYTE} MB are not opened")
    return path.read_text(encoding=encoding)

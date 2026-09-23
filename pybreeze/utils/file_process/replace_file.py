"""Write a file so that a failure part-way leaves the old one as it was.

Opening a file for writing empties it first. A full disk, a crash or a file
held open by something else then left it empty or cut short: the settings, the
prompt or the diagram it held were gone, not just the new save.
"""
from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from pathlib import Path

# Owner read and write only, for a file that holds secrets; others as the umask allows
_PRIVATE_MODE = 0o600
_SHARED_MODE = 0o666


def replace_text(path: Path, text: str, *, private: bool = False) -> None:
    """Write *text* to *path* in UTF-8, replacing the file in one step.

    The text goes to ``<name>.saving`` beside it, which then takes the file's
    place (``os.replace``). Line endings are the platform's, as with
    ``Path.write_text``.

    :param path: the file to write; its folder must exist
    :param text: what it will hold
    :param private: create the file readable by its owner only (``0600`` on
        POSIX; Windows keeps the profile's own access rules). For a file that
        holds keys or tokens, which ``write_text`` left readable by every
        local user.
    :raises OSError: when it cannot be written; *path* is then unchanged and
        the partial file removed
    """
    beside = path.with_name(path.name + ".saving")
    try:
        # A leftover from an earlier failure would keep its own permissions
        with contextlib.suppress(FileNotFoundError):
            beside.unlink()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(beside, flags, _PRIVATE_MODE if private else _SHARED_MODE)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(text)
        os.replace(beside, path)
    except OSError:
        with contextlib.suppress(OSError):
            beside.unlink()
        raise


def replace_written(path: Path, write: Callable[[Path], None]) -> None:
    """Have *write* produce the file at *path*, replacing it in one step.

    For a file something else writes (an image, an SVG): *write* is given
    ``<stem>.saving<suffix>`` beside *path*, with *path*'s extension so a
    writer that goes by it picks the same format, and that file then takes
    *path*'s place.

    :param path: the file to produce; its folder must exist
    :param write: writes the whole file to the path it is given; raises
        ``OSError`` when it cannot
    :raises OSError: when it cannot be written; *path* is then unchanged and
        the partial file removed
    """
    beside = path.with_name(f"{path.stem}.saving{path.suffix}")
    try:
        with contextlib.suppress(FileNotFoundError):
            beside.unlink()
        write(beside)
        os.replace(beside, path)
    except OSError:
        with contextlib.suppress(OSError):
            beside.unlink()
        raise

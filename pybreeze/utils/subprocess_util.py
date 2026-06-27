"""Helpers for spawning child processes cleanly across platforms."""
from __future__ import annotations

import os
import subprocess
import sys


def utf8_subprocess_env(encoding: str = "utf-8") -> dict[str, str]:
    """Return a copy of ``os.environ`` forcing a child Python's stdio *encoding*.

    On Windows a child's piped stdout defaults to the console code page (e.g.
    cp950 / cp1252), so non-ASCII output would be mis-decoded by the utf-8 reader
    in the process managers and show up garbled. Pinning ``PYTHONIOENCODING``
    makes the child emit the same encoding the manager decodes with.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = encoding
    return env


def no_window_creationflags() -> int:
    """Return ``creationflags`` that suppress a console window on Windows.

    PyBreeze is a GUI application. When it is launched without an attached
    console (packaged ``.exe`` or ``pythonw``), every console child it spawns
    (``python -m <package>``, ``pip``, a compiler) pops a transient console
    window. ``CREATE_NO_WINDOW`` prevents that; the child's piped stdout/stderr
    are unaffected. Returns ``0`` (a no-op flag) on non-Windows platforms.
    """
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0

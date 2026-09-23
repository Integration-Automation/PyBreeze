"""Helpers for spawning child processes cleanly across platforms."""
from __future__ import annotations

import os
import signal
import subprocess  # nosec B404 — fixed argument lists, never a shell
import sys

from pybreeze.utils.logging.logger import pybreeze_logger

# How long ending a process tree may take on the UI thread
_TREE_KILL_SECONDS = 10


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


def own_session_options() -> dict:
    """``Popen`` options that give the child a process group of its own (POSIX), for :func:`stop_tree`."""
    return {} if sys.platform == "win32" else {"start_new_session": True}


def stop_tree(process: subprocess.Popen) -> None:
    """Stop *process* and every process it started, if it is still running.

    Stopping only the child left the program running whenever the child was a
    launcher: ``go run``, ``cargo run``, ``dotnet run`` and ``npm start`` start
    the user's program as a grandchild, and a web run starts a browser. On
    Windows ``taskkill /T /F`` ends the tree; on POSIX the child's process
    group (see :func:`own_session_options`) is sent SIGTERM. Either failing,
    the child alone is terminated, as before.
    """
    if process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            taskkill = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
            subprocess.run(  # nosec B603 — fixed argument list, no shell
                [taskkill, "/T", "/F", "/PID", str(process.pid)],
                capture_output=True, timeout=_TREE_KILL_SECONDS, check=False, shell=False,
                creationflags=no_window_creationflags())
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (OSError, subprocess.SubprocessError) as error:
        pybreeze_logger.debug("Could not stop the process tree of %s: %r", process.pid, error)
    if process.poll() is None:
        process.terminate()


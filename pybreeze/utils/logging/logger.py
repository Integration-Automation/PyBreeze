"""The ``Pybreeze`` logger and the file it writes to.

The log file is ``~/.pybreeze/logs/PyBreeze.log`` unless ``PYBREEZE_LOG_FILE``
names another path (``os.devnull`` turns the file off). It used to be the
relative path ``PyBreeze.log``, opened for overwrite at import: every process
that imported the package left a log in whatever directory it started in, wiped
the previous process's log, and could not be imported at all from a read-only
working directory. It was also written in the locale's code page, so on a
cp1252 machine a record carrying Chinese text raised inside ``emit()`` and was
dropped.

The handler opens the file on the first record, so importing writes nothing.
Every process on the account shares the file, so it is opened for append, each
line carries the process id, and it is rotated only when a process opens it:
Windows refuses to rename a file another process holds open, and a rotation
inside ``emit()`` would then fail on every later record. This is the scheme
JEditor's and FrontEngine's logs follow (workspace X-6).
"""
from __future__ import annotations

import logging
import os
import warnings
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pybreeze.utils.app_dirs import pybreeze_data_path

# A library must not reconfigure the root logger: forcing it to DEBUG makes
# every third-party logger verbose and robs the host application of control
# over log levels. PyBreeze logs only through its own named logger below, which
# carries its own DEBUG level and file handler.
pybreeze_logger = logging.getLogger("Pybreeze")
pybreeze_logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "%(asctime)s | %(process)d | %(name)s | %(levelname)s | %(message)s"
)

#: Environment variable naming where the log file is written.
LOG_FILE_ENV = "PYBREEZE_LOG_FILE"
#: Environment variable overriding the size past which the file is rotated on open.
LOG_MAX_BYTES_ENV = "PYBREEZE_LOG_MAX_BYTES"
#: A file past this size is moved to ``<name>.1`` when a process opens it.
DEFAULT_MAX_LOG_BYTES = 100 * 1024 * 1024


def default_log_file() -> Path:
    """Return the log file's path: ``$PYBREEZE_LOG_FILE``, else ``~/.pybreeze/logs/PyBreeze.log``."""
    configured = os.environ.get(LOG_FILE_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    return pybreeze_data_path() / "logs" / "PyBreeze.log"


def _rotate_at_bytes() -> int:
    """The rotation size, from ``$PYBREEZE_LOG_MAX_BYTES`` when it is a number."""
    try:
        return int(os.environ.get(LOG_MAX_BYTES_ENV, DEFAULT_MAX_LOG_BYTES))
    except ValueError:
        return DEFAULT_MAX_LOG_BYTES


def _rotate_if_large(path: Path, limit: int) -> None:
    """Move *path* to ``<path>.1`` when it is larger than *limit* bytes.

    Best effort: while another process holds the file Windows refuses the
    rename, and the file keeps growing until a later start.
    """
    try:
        if limit <= 0 or not path.is_file() or path.stat().st_size <= limit:
            return
        os.replace(path, path.with_name(path.name + ".1"))
    except OSError as error:
        warnings.warn(f"PyBreeze log {path} not rotated: {error!r}", RuntimeWarning, stacklevel=2)


class PyBreezeLogger(RotatingFileHandler):
    """PyBreeze's file handler: ``default_log_file()`` unless told otherwise, appended, UTF-8.

    A file that cannot be opened is swapped for ``os.devnull`` with one
    ``RuntimeWarning`` rather than failing whoever logs.
    """

    def __init__(
        self,
        filename: str | None = None,
        mode: str = "a",
        max_bytes: int = 0,
        backup_count: int = 0,
        delay: bool = False,
    ):
        """
        :param filename: the log file, ``default_log_file()`` by default
        :param mode: the open mode, append by default
        :param max_bytes: rotation size inside ``emit()``; 0 rotates only on open
        :param backup_count: how many rotated files to keep
        :param delay: open the file on the first record instead of now
        """
        # encoding is explicit: on the locale codec a character outside it raises
        # inside emit(), which logging swallows, so the record vanishes.
        # backslashreplace (what the logging module's own quick setup uses)
        # because an escaped record beats a lost one.
        path = filename if filename is not None else str(default_log_file())
        super().__init__(
            filename=path,
            mode=mode,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            delay=delay,
            errors="backslashreplace",
        )
        self.setFormatter(formatter)
        self.setLevel(logging.DEBUG)

    def _open(self):
        """Create the directory and rotate before opening; fall back to ``os.devnull``."""
        path = Path(self.baseFilename)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _rotate_if_large(path, _rotate_at_bytes())
            return super()._open()
        except OSError as error:
            warnings.warn(f"PyBreeze log file {path} unavailable, file logging off: {error!r}",
                          RuntimeWarning, stacklevel=2)
            # The handler owns and closes this stream.
            return open(os.devnull, self.mode, encoding=self.encoding, errors=self.errors)  # noqa: SIM115


# The package's own handler, opened on the first record.
file_handler = PyBreezeLogger(delay=True)
pybreeze_logger.addHandler(file_handler)

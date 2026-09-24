"""Per-user PyBreeze application directories."""
from __future__ import annotations

from pathlib import Path

_DATA_DIR_NAME = ".pybreeze"
# Its owner only: it holds SSH known hosts, prompts, and the prthinker keys and tokens
DATA_DIR_MODE = 0o700


def pybreeze_data_path() -> Path:
    """Return where the user-level PyBreeze data directory is, without creating it.

    For callers that must not touch the disk yet, such as the logger at import.
    """
    return Path.home() / _DATA_DIR_NAME


def pybreeze_data_dir() -> Path:
    """Return the user-level PyBreeze data directory, creating it if needed.

    A single home-based location (``~/.pybreeze``) keeps persisted data — SSH
    known hosts, AI-review stats — stable regardless of the directory the IDE
    was launched from. Made readable by its owner only (``0700`` on POSIX;
    Windows keeps the profile's own access rules); an existing one is left as
    it is.
    """
    data_dir = pybreeze_data_path()
    data_dir.mkdir(mode=DATA_DIR_MODE, parents=True, exist_ok=True)
    return data_dir

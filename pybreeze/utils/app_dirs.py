"""Per-user PyBreeze application directories."""
from __future__ import annotations

from pathlib import Path

_DATA_DIR_NAME = ".pybreeze"


def pybreeze_data_dir() -> Path:
    """Return the user-level PyBreeze data directory, creating it if needed.

    A single home-based location (``~/.pybreeze``) keeps persisted data — SSH
    known hosts, AI-review stats — stable regardless of the directory the IDE
    was launched from.
    """
    data_dir = Path.home() / _DATA_DIR_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

"""Shared file-write helper for the prompt template editors.

The CoT and Skills prompt editors both write template text to disk on create and
save. Centralising the write keeps a single place that turns an I/O failure into
a user-facing dialog instead of an uncaught traceback.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

from pybreeze.utils.logging.logger import pybreeze_logger


def save_prompt_text(parent: QWidget, path: str, content: str, error_title: str) -> bool:
    """Write *content* to *path*; show a warning dialog on failure.

    Returns ``True`` on success, ``False`` if the write raised ``OSError`` (so the
    caller can skip its success message).
    """
    try:
        # The directory is made here rather than on every read, so a session that
        # only looks at the built-in prompts leaves nothing behind.
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Written beside the file and moved into place in one step: opening the
        # file itself for writing truncates it first, so a failure part-way left
        # the prompt empty, and the review silently fell back to the built-in.
        beside = target.with_name(target.name + ".saving")
        beside.write_text(content, encoding="utf-8")
        os.replace(beside, target)
        return True
    except OSError as error:
        pybreeze_logger.error("Prompt file write failed for %s: %r", path, error)
        Path(path).with_name(Path(path).name + ".saving").unlink(missing_ok=True)
        QMessageBox.warning(parent, error_title, error.strerror or type(error).__name__)
        return False

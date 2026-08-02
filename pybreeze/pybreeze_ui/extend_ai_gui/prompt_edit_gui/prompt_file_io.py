"""Shared file-write helper for the prompt template editors.

The CoT and Skills prompt editors both write template text to disk on create and
save. Centralising the write keeps a single place that turns an I/O failure into
a user-facing dialog instead of an uncaught traceback.
"""
from __future__ import annotations

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
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file_handle:
            file_handle.write(content)
        return True
    except OSError as error:
        pybreeze_logger.error("Prompt file write failed for %s: %r", path, error)
        QMessageBox.warning(parent, error_title, str(error))
        return False

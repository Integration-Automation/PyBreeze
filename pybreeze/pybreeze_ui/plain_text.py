"""Show text in a Qt message box or label exactly as it is, never as markup.

``QMessageBox`` and ``QLabel`` take text as rich text when its first line looks
like HTML (``Qt::AutoText``). A file name, a remote path or an error message
from an SSH server or a file the user opened could therefore carry
``<img src=...>``, which Qt then loads (a UNC path makes Windows connect out and
offer the user's credentials), or links and fake dialog text.
"""
from __future__ import annotations

from PySide6.QtGui import Qt


def as_text(text: str) -> str:
    """*text* as markup that displays it exactly: every ``<``, ``>`` and ``&`` escaped.

    For the static ``QMessageBox`` functions, which take the text as it is and
    guess its format. Line breaks are kept; runs of spaces are not.
    """
    return Qt.convertFromPlainText(text, Qt.WhiteSpaceMode.WhiteSpaceNormal)

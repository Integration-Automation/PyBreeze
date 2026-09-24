"""Terminal output written into a text view the way a terminal shows it.

Shared by the run window and the SSH terminal.
"""
from __future__ import annotations

from PySide6.QtGui import QTextCharFormat, QTextCursor


def insert_rewinding(cursor: QTextCursor, text: str, text_format: QTextCharFormat) -> bool:
    """Insert *text* at *cursor*, a lone ``\\r`` going back to the start of the line.

    As a terminal does: a progress bar that rewinds with ``\\r`` redraws its
    line instead of adding one per step. ``\\r\\n`` and ``\\n`` are line breaks.

    :return: whether *text* ended on a ``\\r`` still to be applied: it waits
        for what comes next, since rewound now, a finished progress bar's last
        line would be erased with nothing to replace it
    """
    pieces = text.replace("\r\n", "\n").split("\r")
    cursor.insertText(pieces[0], text_format)
    for index, piece in enumerate(pieces[1:], start=1):
        if not piece and index == len(pieces) - 1:
            return True
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(piece, text_format)
    return False

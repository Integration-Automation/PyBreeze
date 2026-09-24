"""Terminal output written into a text view the way a terminal shows it.

Shared by the run window and the SSH terminal.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPalette, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from pybreeze.utils.terminal_style import PLAIN, Colour, TextStyle, colour_rgb


def use_terminal_font(view: QPlainTextEdit) -> None:
    """Show *view* in the system's fixed-pitch font, at the size it had.

    Output laid out in columns (``ls -l``, ``df``, a table a script prints)
    lines up only when every character is as wide as the next; in the
    interface's proportional font it came out ragged.
    """
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSizeF(view.font().pointSizeF())
    view.setFont(font)


# Smallest size given to a program for a view squeezed to almost nothing
MIN_COLUMNS = 20
MIN_ROWS = 5


def terminal_size(view: QPlainTextEdit) -> tuple[int, int]:
    """The columns and rows of text *view* shows whole, in its font.

    What a pty is told, for programs to lay out their output (``ls``'s
    columns, a progress bar's width) to fit the view.
    """
    metrics = QFontMetricsF(view.font())
    margins = 2 * view.document().documentMargin()
    viewport = view.viewport()
    columns = int((viewport.width() - margins) // metrics.horizontalAdvance("M"))
    rows = int((viewport.height() - margins) // metrics.lineSpacing())
    return max(columns, MIN_COLUMNS), max(rows, MIN_ROWS)


# Background lightness (0–255) below which a view counts as dark
_DARK_BELOW = 128


def _qcolour(colour: Colour | None, on_dark: bool) -> QColor | None:
    return None if colour is None else QColor(*colour_rgb(colour, on_dark=on_dark))


def style_format(style: TextStyle, palette: QPalette) -> QTextCharFormat:
    """The format for text in *style* in a view with *palette*.

    The palette's background picks the dark or the light set of the 16 basic
    colours, and its colours stand in for defaults in inverse. The plain style
    is an empty format: the view's own font and colours.
    """
    text_format = QTextCharFormat()
    if style == PLAIN:
        return text_format
    on_dark = palette.color(QPalette.ColorRole.Base).lightness() < _DARK_BELOW
    foreground = _qcolour(style.foreground, on_dark)
    background = _qcolour(style.background, on_dark)
    if style.inverse:
        foreground, background = (background or palette.color(QPalette.ColorRole.Base),
                                  foreground or palette.color(QPalette.ColorRole.Text))
    if foreground is not None:
        text_format.setForeground(foreground)
    if background is not None:
        text_format.setBackground(background)
    if style.bold:
        text_format.setFontWeight(QFont.Weight.Bold)
    text_format.setFontItalic(style.italic)
    text_format.setFontUnderline(style.underline)
    return text_format


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

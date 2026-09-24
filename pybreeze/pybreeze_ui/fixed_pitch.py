"""A text view in the system's fixed-pitch font, whatever the theme names."""
from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QWidget


def use_fixed_pitch_font(view: QWidget) -> None:
    """Show *view* in the system's fixed-pitch font, at the size it had.

    Output laid out in columns (``ls -l``, ``df``, a table a script prints)
    lines up only when every character is as wide as the next; in the
    interface's proportional font it came out ragged.

    The family is also set in the view's own style sheet, which this replaces:
    a theme's sheet (qt_material names a font for every widget) overrides
    ``setFont``, and the view's sheet overrides the application's. The theme's
    size stays.
    """
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    size = view.font().pointSizeF()
    if size > 0:  # -1 when a style sheet gave the size in pixels
        font.setPointSizeF(size)
    view.setFont(font)
    view.setStyleSheet(f'font-family: "{font.family()}";')

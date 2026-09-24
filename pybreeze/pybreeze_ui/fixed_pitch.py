"""A text view in a fixed-pitch font, whatever the theme names."""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QWidget

# Tried before the system's own fixed-pitch font, which on Windows is Courier
# New: thin on a dark theme, and at the tools' size it lost the underscores.
# Consolas is what VS Code shows code in on Windows.
PREFERRED_FAMILIES = ("Consolas",)


def fixed_pitch_font() -> QFont:
    """The first installed of ``PREFERRED_FAMILIES``, else the system's fixed-pitch font."""
    for family in PREFERRED_FAMILIES:
        if QFontDatabase.hasFamily(family):
            font = QFont(family)
            font.setFixedPitch(True)
            return font
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


def use_fixed_pitch_font(view: QWidget) -> None:
    """Show *view* in :func:`fixed_pitch_font`, at the size it had.

    Output laid out in columns (``ls -l``, ``df``, a table a script prints)
    lines up only when every character is as wide as the next; in the
    interface's proportional font it came out ragged.

    The family is also set in the view's own style sheet, which this replaces:
    a theme's sheet (qt_material names a font for every widget) overrides
    ``setFont``, and the view's sheet overrides the application's. The theme's
    size stays.
    """
    font = fixed_pitch_font()
    size = view.font().pointSizeF()
    if size > 0:  # -1 when a style sheet gave the size in pixels
        font.setPointSizeF(size)
    view.setFont(font)
    view.setStyleSheet(f'font-family: "{font.family()}";')

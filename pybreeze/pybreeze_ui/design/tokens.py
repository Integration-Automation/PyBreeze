"""The sizes and colours PyBreeze's own panels are built from.

Each panel used to pick its own numbers: 11 pixels of margin here, 8 there, a
48-pixel label, a colour written out as RGB. A number of pixels is right on one
screen and one font. Everything here is counted in *ems*, the height of the
font in use, so a panel keeps its proportions when the font is larger, the
display denser or the user's theme sets another size; and a colour is one of
the theme's own, so it is readable on a dark theme and on a light one.

- :class:`Space`: the gaps between things and around them;
- :class:`TextRole`: the sizes text comes in;
- :class:`IconSize`: the sizes an icon or a tool button comes in;
- :class:`State`: what a message is (plain, good, a warning, an error), and
  the theme colour that says so.

A panel asks for a step by name and never writes a number of its own.
"""
from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QLayout, QWidget
from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict


class Space(Enum):
    """A gap, in ems."""

    HAIRLINE = 0.25   # between a label and the field it names
    TIGHT = 0.5       # between the controls of one group
    NORMAL = 1.0      # around a panel's content, and between its groups
    SECTION = 1.5     # between two panels


class TextRole(Enum):
    """A size of text, as a multiple of the application font's."""

    CAPTION = 0.9     # a note under a control
    BODY = 1.0
    TITLE = 1.15      # a panel's title
    HEADING = 1.4     # the title of a whole page


class IconSize(Enum):
    """The side of an icon or a square button, in ems."""

    SMALL = 1.0
    MEDIUM = 1.5
    LARGE = 2.0


class State(Enum):
    """What a message is; its value is the key of the theme colour that says so."""

    NEUTRAL = "normal_output_color"
    SUCCESS = "diff_added_marker_color"
    WARNING = "warning_output_color"
    ERROR = "error_output_color"


# Roles drawn in bold
_BOLD_ROLES = frozenset({TextRole.TITLE, TextRole.HEADING})


def _font_of(widget: QWidget | None) -> QFont:
    """The font sizes are counted in: *widget*'s own, or the application's."""
    return widget.font() if widget is not None else QApplication.font()


def em(widget: QWidget | None = None) -> int:
    """The height in pixels of the font *widget* uses (the application's when none is given)."""
    return QFontMetrics(_font_of(widget)).height()


def space(step: Space, widget: QWidget | None = None) -> int:
    """*step* in pixels for *widget*'s font, never less than one pixel."""
    return max(1, round(step.value * em(widget)))


def text_font(role: TextRole, widget: QWidget | None = None) -> QFont:
    """The font for text of *role*, sized from *widget*'s font."""
    font = QFont(_font_of(widget))
    base = font.pointSizeF()
    if base > 0:
        font.setPointSizeF(base * role.value)
    else:
        # A font given in pixels has no point size
        font.setPixelSize(max(1, round(font.pixelSize() * role.value)))
    font.setBold(role in _BOLD_ROLES)
    return font


def icon_size(size: IconSize, widget: QWidget | None = None) -> QSize:
    """A square of *size* for *widget*'s font."""
    side = max(1, round(size.value * em(widget)))
    return QSize(side, side)


def state_colour(state: State) -> QColor:
    """The theme's colour for *state*, or the application's text colour when the theme has none."""
    colour = actually_color_dict.get(state.value)
    if isinstance(colour, QColor) and colour.isValid():
        return QColor(colour)
    return QApplication.palette().windowText().color()


def apply_spacing(layout: QLayout, *, around: Space = Space.NORMAL, between: Space = Space.TIGHT) -> None:
    """Give *layout* the standard gaps: *around* its content, *between* its items.

    The pixels come from the font of the widget the layout belongs to.
    """
    widget = layout.parentWidget()
    margin = space(around, widget)
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(space(between, widget))

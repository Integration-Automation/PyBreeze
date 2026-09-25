"""The colours and emphasis a program's SGR escape sequences ask for.

``ESC [ … m`` (Select Graphic Rendition) sets how the text after it looks:
``ls --color``, ``git``, ``grep --color`` use it through a pty. This reads the
sequences into a :class:`TextStyle`, carried from one read to the next; the
view turns it into a text format. Other escape sequences are not read here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

# A colour: an index into the 256-colour palette, or (red, green, blue)
Colour = int | tuple[int, int, int]

# SGR with ";"-separated parameters. The ":" form (ESC [ 38:5:196 m) is left
# to strip_terminal_controls, which removes it.
SGR_PATTERN = re.compile(r'\x1B\[([0-9;]*)m')

# Parameter -> (attribute, value) for the on/off parameters
_SWITCHES = {
    1: ("bold", True), 22: ("bold", False),
    3: ("italic", True), 23: ("italic", False),
    4: ("underline", True), 24: ("underline", False),
    7: ("inverse", True), 27: ("inverse", False),
}
_DEFAULT_FOREGROUND = 39
_DEFAULT_BACKGROUND = 49
_EXTENDED_FOREGROUND = 38
_EXTENDED_BACKGROUND = 48
# Parameter runs that pick one of the 16 basic colours: first, attribute, first colour
_COLOUR_RUNS = ((30, "foreground", 0), (90, "foreground", 8), (40, "background", 0), (100, "background", 8))
_RUN_LENGTH = 8
_PALETTE_FORM = 5  # ESC[38;5;<index>m: one of 256 colours
_RGB_FORM = 2      # ESC[38;2;<red>;<green>;<blue>m

# The first 16 colours (normal, then bright) as VS Code's terminal shows them
# on a dark and on a light theme. xterm's own blue (0, 0, 238) was all but
# unreadable on the IDE's dark background.
_ON_DARK = (
    (0, 0, 0), (205, 49, 49), (13, 188, 121), (229, 229, 16),
    (36, 114, 200), (188, 63, 188), (17, 168, 205), (229, 229, 229),
    (102, 102, 102), (241, 76, 76), (35, 209, 139), (245, 245, 67),
    (59, 142, 234), (214, 112, 214), (41, 184, 219), (229, 229, 229),
)
_ON_LIGHT = (
    (0, 0, 0), (205, 49, 49), (16, 124, 16), (148, 152, 0),
    (4, 81, 165), (188, 5, 188), (5, 152, 188), (85, 85, 85),
    (102, 102, 102), (241, 76, 76), (20, 206, 20), (181, 186, 0),
    (59, 142, 234), (214, 112, 214), (41, 184, 219), (165, 165, 165),
)
_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)
_CUBE_START = 16
_GREY_START = 232
_PALETTE_SIZE = 256
_CHANNEL_MAX = 255
# Longest parameter read: a longer one (a server can send thousands of digits,
# and int() refuses more than 4300) is taken as unknown
_MAX_PARAMETER_DIGITS = 5
_UNKNOWN = -1


@dataclass(frozen=True)
class TextStyle:
    """How text looks; ``None`` colours are the view's own."""

    foreground: Colour | None = None
    background: Colour | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    inverse: bool = False


PLAIN = TextStyle()


def colour_rgb(colour: Colour, *, on_dark: bool) -> tuple[int, int, int]:
    """The (red, green, blue) of *colour*, on a dark background or a light one.

    The first 16 differ between the two; the rest of the palette (xterm's
    colour cube and greys) and a colour given as red, green and blue do not.
    """
    if isinstance(colour, tuple):
        return colour
    basic = _ON_DARK if on_dark else _ON_LIGHT
    if colour < len(basic):
        return basic[colour]
    if colour < _GREY_START:
        index = colour - _CUBE_START
        return (_CUBE_LEVELS[index // 36], _CUBE_LEVELS[index // 6 % 6], _CUBE_LEVELS[index % 6])
    grey = 8 + 10 * (colour - _GREY_START)
    return grey, grey, grey


def _extended_colour(numbers: list[int], start: int) -> tuple[Colour | None, int]:
    """The colour ``38;…``/``48;…`` gives from *start*, and where the next parameter is.

    ``None`` for one malformed or out of range, which leaves the colour as it was.
    """
    form = numbers[start] if start < len(numbers) else None
    if form == _PALETTE_FORM and start + 1 < len(numbers):
        index = numbers[start + 1]
        return (index if 0 <= index < _PALETTE_SIZE else None), start + 2
    if form == _RGB_FORM and start + 3 < len(numbers):
        rgb = tuple(numbers[start + 1:start + 4])
        return (rgb if 0 <= min(rgb) and max(rgb) <= _CHANNEL_MAX else None), start + 4
    return None, len(numbers)  # the rest cannot be read


def _colour_parameter(style: TextStyle, number: int) -> TextStyle:
    """*style* after one of the basic colour parameters (30–49, 90–107), or as it was."""
    for first, attribute, offset in _COLOUR_RUNS:
        if first <= number < first + _RUN_LENGTH:
            colour = number - first + offset
            if attribute == "foreground":
                return replace(style, foreground=colour)
            return replace(style, background=colour)
    if number == _DEFAULT_FOREGROUND:
        return replace(style, foreground=None)
    if number == _DEFAULT_BACKGROUND:
        return replace(style, background=None)
    return style


def _parameter(part: str) -> int:
    """One SGR parameter: empty is 0, one too long to be real is ``_UNKNOWN``."""
    if not part:
        return 0
    return int(part) if len(part) <= _MAX_PARAMETER_DIGITS else _UNKNOWN


def apply_sgr(style: TextStyle, parameters: str) -> TextStyle:
    """*style* after an SGR sequence with *parameters* (``"1;31"``); unknown ones are ignored."""
    numbers = [_parameter(part) for part in parameters.split(";")]
    index = 0
    while index < len(numbers):
        number = numbers[index]
        index += 1
        if number == 0:
            style = PLAIN
        elif number in _SWITCHES:
            attribute, value = _SWITCHES[number]
            style = replace(style, **{attribute: value})
        elif number in (_EXTENDED_FOREGROUND, _EXTENDED_BACKGROUND):
            colour, index = _extended_colour(numbers, index)
            if colour is not None:
                attribute = "foreground" if number == _EXTENDED_FOREGROUND else "background"
                style = replace(style, **{attribute: colour})
        else:
            style = _colour_parameter(style, number)
    return style


def split_styled(text: str, style: TextStyle) -> tuple[list[tuple[TextStyle, str]], TextStyle]:
    """*text* cut at its SGR sequences, each piece with the style it is shown in.

    *style* is what earlier text left; the style *text* leaves is returned
    with the pieces. The pieces keep every other escape sequence and control.
    """
    pieces: list[tuple[TextStyle, str]] = []
    start = 0
    for match in SGR_PATTERN.finditer(text):
        if match.start() > start:
            pieces.append((style, text[start:match.start()]))
        style = apply_sgr(style, match.group(1))
        start = match.end()
    if start < len(text):
        pieces.append((style, text[start:]))
    return pieces, style

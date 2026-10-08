"""Where things are in a JSON text: every value with its place, and what the cursor is in the middle of.

``json.loads`` says what a text means and forgets where each value was. An
editor needs the place: to underline the keyword that is wrong, to say what
the word under the cursor is, and, while a text is half written and not JSON
yet, to know that the cursor stands where a keyword's name goes.

Two readings, over one tokenizer:

- :func:`locate` reads a text that **is** JSON into :class:`Located` values,
  each with the offsets it runs between;
- :func:`context_at` reads the text **before the cursor**, JSON or not, into
  the objects and arrays that are still open there (:class:`Frame`).

Neither recurses: a text can nest as deep as it likes. Offsets are indexes
into the text; :class:`LineIndex` turns them into the protocol's positions.
"""
from __future__ import annotations

import json
import re
from bisect import bisect_right
from dataclasses import dataclass, field

from pybreeze.utils.language_service.service_adapter import Position, Range, index_at, utf16_offset

OBJECT, ARRAY, STRING, SCALAR = "object", "array", "string", "scalar"

# A string that is not closed ends at its line: JSON has no line break inside one
_TOKEN = re.compile(r"""
    (?P<space>[ \t\r\n]+)
  | (?P<punctuation>[{}\[\]:,])
  | (?P<string>"(?:[^"\\\r\n]|\\.)*")
  | (?P<open_string>"(?:[^"\\\r\n]|\\.)*)
  | (?P<scalar>[^\s{}\[\]:,"]+)
""", re.VERBOSE)
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_OPENS = {"{": OBJECT, "[": ARRAY}


@dataclass(frozen=True)
class Token:
    """One piece of a JSON text: punctuation, a string, an unfinished string, or a number or word."""

    kind: str
    start: int
    end: int
    text: str


def tokens(text: str) -> list[Token]:
    """The pieces of *text*, in order, without the space between them."""
    return [Token(match.lastgroup, match.start(), match.end(), match.group())
            for match in _TOKEN.finditer(text) if match.lastgroup != "space"]


def _said(string_token: str) -> str:
    """What a string token says; as written, between its quotes, when its escapes are not JSON's."""
    try:
        said = json.loads(string_token)
    except ValueError:
        return string_token[1:-1]
    return said if isinstance(said, str) else string_token[1:-1]


@dataclass(frozen=True)
class Located:
    """A value and where it is.

    :param kind: ``OBJECT``, ``ARRAY``, ``STRING`` or ``SCALAR`` (a number, ``true``, ``false``, ``null``)
    :param start: the offset of its first character
    :param end: the offset after its last
    :param value: what a string says, or a scalar as written
    :param items: an array's values
    :param members: an object's keys and values
    """

    kind: str
    start: int
    end: int
    value: str = ""
    items: tuple[Located, ...] = ()
    members: tuple[tuple[Located, Located], ...] = ()

    def holds(self, offset: int) -> bool:
        """Whether *offset* is in the value, its two ends included."""
        return self.start <= offset <= self.end


@dataclass
class _Open:
    """An object or array being read."""

    kind: str
    start: int
    items: list[Located] = field(default_factory=list)
    key: Located | None = None
    members: list[tuple[Located, Located]] = field(default_factory=list)

    def take(self, value: Located) -> None:
        if self.kind == ARRAY:
            self.items.append(value)
        elif self.key is None:
            self.key = value
        else:
            self.members.append((self.key, value))
            self.key = None

    def closed(self, end: int) -> Located:
        return Located(self.kind, self.start, end, items=tuple(self.items), members=tuple(self.members))


def _leaf(token: Token) -> Located | None:
    """The string or scalar *token* writes; ``None`` for punctuation."""
    if token.kind == "string":
        return Located(STRING, token.start, token.end, _said(token.text))
    if token.kind == "open_string":
        return Located(STRING, token.start, token.end, token.text[1:])
    if token.kind == "scalar":
        return Located(SCALAR, token.start, token.end, token.text)
    return None


def locate(text: str) -> Located | None:
    """The value *text* writes, with the place of everything in it.

    :param text: a text that is JSON; one that is not gives what could be made
        of it (what is still open where it ends is closed there, so a script
        being typed is read as far as it goes), or ``None``
    """
    opened: list[_Open] = []
    roots: list[Located] = []

    def place(value: Located) -> None:
        if opened:
            opened[-1].take(value)
        else:
            roots.append(value)

    for token in tokens(text):
        if token.text in _OPENS:
            opened.append(_Open(_OPENS[token.text], token.start))
        elif token.text in ("}", "]"):
            if opened:
                place(opened.pop().closed(token.end))
        else:
            leaf = _leaf(token)
            if leaf is not None:
                place(leaf)
    while opened:
        place(opened.pop().closed(len(text)))
    return roots[0] if roots else None


@dataclass(frozen=True)
class Frame:
    """An object or array that is still open at the cursor.

    :param kind: ``OBJECT`` or ``ARRAY``
    :param index: how many values of an array, or members of an object, come before the one at the cursor
    :param first: in an array, its first value when that is a finished string
    :param key: in an object, the key whose value is at the cursor; ``None`` while the cursor is where a key goes
    :param keys: in an object, the keys written before the cursor
    """

    kind: str
    index: int = 0
    first: str | None = None
    key: str | None = None
    keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class CursorContext:
    """What the cursor is in the middle of.

    :param frames: the objects and arrays open there, the outermost first
    :param in_string: whether the cursor is inside a string
    :param typed: what of that string comes before the cursor
    :param start: the offset where that string starts (its quote); the cursor's own offset outside one
    """

    frames: tuple[Frame, ...]
    in_string: bool
    typed: str
    start: int


@dataclass
class _OpenFrame:
    kind: str
    index: int = 0
    first: str | None = None
    key: str | None = None
    keys: list[str] = field(default_factory=list)

    def take_string(self, said: str) -> None:
        if self.kind == OBJECT and self.key is None:
            self.key = said
            self.keys.append(said)
        elif self.kind == ARRAY and self.index == 0:
            self.first = said

    def next_value(self) -> None:
        self.index += 1
        self.key = None

    def frozen(self) -> Frame:
        return Frame(self.kind, self.index, self.first, self.key, tuple(self.keys))


def _step(frames: list[_OpenFrame], token: Token) -> None:
    """Take *token* into the objects and arrays open so far."""
    if token.text in _OPENS:
        frames.append(_OpenFrame(_OPENS[token.text]))
    elif not frames:
        return
    elif token.text in ("}", "]"):
        frames.pop()
    elif token.text == ",":
        frames[-1].next_value()
    elif token.kind == "string":
        frames[-1].take_string(_said(token.text))
    elif token.kind == "open_string":
        frames[-1].take_string(token.text[1:])


def context_at(text: str, offset: int) -> CursorContext:
    """What the cursor at *offset* of *text* is in the middle of; *text* need not be JSON."""
    offset = max(offset, 0)
    before = tokens(text[:offset])
    # A string cut off by the cursor is the one being typed; one the line cut
    # off earlier is a mistake further up, and counts as a finished string
    typing = bool(before) and before[-1].kind == "open_string" and before[-1].end == offset
    frames: list[_OpenFrame] = []
    for token in before[:-1] if typing else before:
        _step(frames, token)
    frozen = tuple(frame.frozen() for frame in frames)
    if typing:
        return CursorContext(frozen, True, before[-1].text[1:], before[-1].start)
    return CursorContext(frozen, False, "", offset)


class LineIndex:
    """Turns offsets in a text into the protocol's positions and back.

    :param text: the text; its lines end in ``\\n``, ``\\r\\n`` or ``\\r``
    """

    def __init__(self, text: str) -> None:
        self._text = text
        self._starts = [0, *(match.end() for match in _LINE_BREAK.finditer(text))]

    def _line(self, number: int) -> str:
        end = self._starts[number + 1] if number + 1 < len(self._starts) else len(self._text)
        return self._text[self._starts[number]:end].rstrip("\r\n")

    def position(self, offset: int) -> Position:
        """The position of the character at *offset*."""
        offset = max(0, min(offset, len(self._text)))
        number = bisect_right(self._starts, offset) - 1
        return Position(number, utf16_offset(self._line(number), offset - self._starts[number]))

    def span(self, start: int, end: int) -> Range:
        """The range from *start* up to *end*."""
        return Range(self.position(start), self.position(end))

    def offset(self, position: Position) -> int:
        """The offset *position* names; one past the text or a line gives its end."""
        if position.line < 0:
            return 0
        if position.line >= len(self._starts):
            return len(self._text)
        return self._starts[position.line] + index_at(self._line(position.line), position.character)

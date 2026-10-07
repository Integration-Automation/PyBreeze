"""One JSON document that a text editor and a visual editor can both hold.

A JSON file has two faces: the text someone types and the tree someone clicks
through. Kept as two copies they drift, and whichever was written last quietly
wins. A :class:`JsonDocument` is the one copy both edit, and it settles what
each face may do:

- The **text** is the truth. It is kept exactly as given, also while it is not
  JSON: half-typed text is not thrown away and nothing raises, the document
  only says what is wrong (:attr:`JsonDocument.problem`) and has no tree
  until the text parses again.
- The **tree** is what the text says, with nothing of how it was laid out: no
  indentation, no line breaks. A number keeps its own text
  (:class:`JsonNumber`), so ``1.0`` and ``1e400`` come back as written.
- Going from a tree to text is always :func:`serialize_json` with the
  document's :class:`SerializationOptions`: layout lives there, in one place.
- Every edit names the revision it was made against. One made against an
  older revision is refused (:class:`StaleRevisionError`) instead of
  overwriting what the other face changed in between.

Pure logic: it holds no widget, and both editors reach it through the same
calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from json import JSONDecodeError, dumps, loads

from pybreeze.utils.exception.exception_tags import json_duplicate_key_error, wrong_json_data_error
from pybreeze.utils.exception.exceptions import ITEJsonException
from pybreeze.utils.json_format.json_process import DuplicateKeyError, HeldNumbers, refuse_constant, unique_pairs

# A number as JSON writes one (RFC 8259, section 6)
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


@dataclass(frozen=True)
class JsonNumber:
    """A JSON number, kept as it is written.

    A ``float`` gives ``1e400`` back as ``Infinity``, which is not JSON, and
    ``1.0`` as whatever the next writer makes of it.

    :param text: the number's text, e.g. ``-12.50``
    :raises ValueError: when *text* is not a JSON number
    """

    text: str

    def __post_init__(self) -> None:
        if not _NUMBER.fullmatch(self.text):
            raise ValueError(f"{self.text!r} is not a JSON number")


# What a document's tree is made of. An object keeps its members in the order
# the text gives them.
JsonValue = dict[str, "JsonValue"] | list["JsonValue"] | str | JsonNumber | bool | None


class JsonProblem(ITEJsonException):
    """Why a text is not JSON a document can hold, and where when the parser says.

    :param message: the reason
    :param line: the line it was found on, from 1; ``None`` when it is not about one place
    :param column: the column on that line, from 1
    """

    def __init__(self, message: str, line: int | None = None, column: int | None = None) -> None:
        super().__init__(message)
        self.line = line
        self.column = column


class StaleRevisionError(ITEJsonException):
    """An edit made against a revision the document has moved on from.

    :param base: the revision the edit was made against
    :param current: the revision the document is at
    """

    def __init__(self, base: int, current: int) -> None:
        super().__init__(f"the edit was made against revision {base}; the document is at revision {current}")
        self.base = base
        self.current = current


@dataclass(frozen=True)
class SerializationOptions:
    """How a tree is written as text.

    :param indent: spaces per level; ``None`` writes it on one line
    :param ensure_ascii: write every non-ASCII character as a ``\\uXXXX`` escape
    :param trailing_newline: end the text with a line break
    """

    indent: int | None = 4
    ensure_ascii: bool = False
    trailing_newline: bool = False


def parse_json(text: str) -> JsonValue:
    """Read *text* into a tree, numbers kept as written.

    What the JSON tools refuse is refused here too: a key given twice in one
    object (the second would silently replace the first), ``NaN`` and
    ``Infinity``. Nothing is logged: an editor asks on every keystroke.

    :raises JsonProblem: when *text* is not such JSON
    """
    try:
        return loads(
            text, parse_float=JsonNumber, parse_int=JsonNumber,
            parse_constant=refuse_constant, object_pairs_hook=unique_pairs)
    except DuplicateKeyError as error:
        raise JsonProblem(json_duplicate_key_error.format(key=error.args[0])) from error
    except JSONDecodeError as error:
        raise JsonProblem(wrong_json_data_error, error.lineno, error.colno) from error
    except (ValueError, RecursionError) as error:
        # ValueError: NaN or Infinity. RecursionError: nested deeper than the parser goes.
        raise JsonProblem(wrong_json_data_error) from error


def serialize_json(tree: JsonValue, options: SerializationOptions = SerializationOptions()) -> str:
    """Write *tree* as text laid out as *options* say.

    Characters a text view would not give back are written as escapes
    (``view_safe``), so the text survives being shown and read back.

    :raises JsonProblem: when *tree* holds something that is not JSON, or nests
        deeper than the writer goes
    """
    numbers = HeldNumbers()

    def held(value: object) -> str:
        if isinstance(value, JsonNumber):
            return numbers.hold(value.text)
        raise TypeError(f"{type(value).__name__} is not JSON")

    try:
        text = numbers.restore(dumps(
            tree, default=held, indent=options.indent, ensure_ascii=options.ensure_ascii, allow_nan=False))
    except (TypeError, ValueError, RecursionError) as error:
        raise JsonProblem(wrong_json_data_error) from error
    return text + "\n" if options.trailing_newline else text


class JsonDocument:
    """A JSON text and the tree it says, edited from either side.

    :param text: the document's text; it need not be JSON
    :param options: how a tree is written back as text
    """

    def __init__(self, text: str = "", options: SerializationOptions = SerializationOptions()) -> None:
        self._options = options
        self._revision = 0
        self._text = text
        self._tree: JsonValue = None
        self._problem: JsonProblem | None = None
        self._read()

    @property
    def text(self) -> str:
        """The text, exactly as it was last given or written."""
        return self._text

    @property
    def tree(self) -> JsonValue:
        """What the text says. ``None`` while :attr:`problem` is set, and for the text ``null``."""
        return self._tree

    @property
    def problem(self) -> JsonProblem | None:
        """Why the text has no tree, or ``None`` when it has one."""
        return self._problem

    @property
    def revision(self) -> int:
        """How many times the document has changed; an edit names the one it was made against."""
        return self._revision

    @property
    def options(self) -> SerializationOptions:
        """How a tree is written back as text."""
        return self._options

    def set_text(self, text: str, base_revision: int) -> int:
        """Replace the text, as the text editor does when it is edited.

        :param text: the new text; kept as it is even when it is not JSON
        :param base_revision: the revision the edit was made against
        :return: the new revision
        :raises StaleRevisionError: when the document has changed since *base_revision*
        """
        self._check_current(base_revision)
        self._text = text
        self._read()
        return self._changed()

    def set_tree(self, tree: JsonValue, base_revision: int) -> int:
        """Replace the tree, as the visual editor does when it is edited; the text is written from it.

        :param tree: the new tree
        :param base_revision: the revision the edit was made against
        :return: the new revision
        :raises StaleRevisionError: when the document has changed since *base_revision*
        :raises JsonProblem: when *tree* is not JSON; the document is left as it was
        """
        self._check_current(base_revision)
        self._text = serialize_json(tree, self._options)
        # Read back rather than kept: the tree handed in stays the caller's to change
        self._read()
        return self._changed()

    def _check_current(self, base_revision: int) -> None:
        if base_revision != self._revision:
            raise StaleRevisionError(base_revision, self._revision)

    def _changed(self) -> int:
        self._revision += 1
        return self._revision

    def _read(self) -> None:
        """Set the tree, or the problem, from the text."""
        try:
            self._tree, self._problem = parse_json(self._text), None
        except JsonProblem as problem:
            self._tree, self._problem = None, problem

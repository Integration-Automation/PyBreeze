"""Format and minify JSON without changing what it says.

Round-tripped through ``float``, a number came back different (``1e400`` as
``Infinity``, which is not JSON; ``12345678901234567890123.0`` as
``1.2345678901234568e+22``), a key repeated in one object kept only its last
value, and every non-ASCII character came back as a ``\\u`` escape.
"""
from __future__ import annotations

import re
import secrets
from json import dumps
from json import loads

from pybreeze.utils.exception.exception_tags import cant_reformat_json_error
from pybreeze.utils.exception.exception_tags import json_duplicate_key_error
from pybreeze.utils.exception.exception_tags import wrong_json_data_error
from pybreeze.utils.exception.exceptions import ITEJsonException
from pybreeze.utils.json_format.view_safe import escape_for_view
from pybreeze.utils.logging.logger import pybreeze_logger


class DuplicateKeyError(ValueError):
    """A key given twice in one JSON object; ``args[0]`` is the key."""


class _Numbers:
    """Keeps each number's own text while the JSON around it is re-laid out.

    A number is parsed to a placeholder string and put back, as written, once
    the rest is serialised. The placeholder carries a random marker, so no
    string in the input can be mistaken for one.
    """

    def __init__(self) -> None:
        self._marker = secrets.token_hex(8)
        self._texts: list[str] = []

    def hold(self, text: str) -> str:
        """The placeholder for the number written as *text*."""
        self._texts.append(text)
        return f"\x00{self._marker}:{len(self._texts) - 1}\x00"

    def restore(self, serialised: str) -> str:
        """*serialised* with every placeholder replaced by its number's text.

        A character the text view would not give back -- a lone surrogate
        (``"\\ud83d"`` in the input), U+2029 -- is written back as its escape:
        with ``ensure_ascii=False`` it went out raw, and ``{"a": "\\ud83d"}``
        came out as ``{"a": ""}`` (see ``view_safe``).
        """
        # How dumps writes a placeholder: quoted, the NUL escaped
        placeholder = re.compile(rf'"\\u0000{self._marker}:(\d+)\\u0000"')
        restored = placeholder.sub(lambda match: self._texts[int(match.group(1))], serialised)
        return escape_for_view(restored)


def refuse_constant(name: str) -> None:
    """``NaN`` and ``Infinity`` are Python's extensions, not JSON (``parse_constant``).

    :raises ValueError: always
    """
    raise ValueError(f"{name} is not JSON")


def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    """An object's members as a dict, refusing a key given twice (``object_pairs_hook``).

    ``json.loads`` keeps a repeated key's last value without a word.

    :raises DuplicateKeyError: for a key given twice
    """
    members: dict = {}
    for key, value in pairs:
        if key in members:
            raise DuplicateKeyError(key)
        members[key] = value
    return members


def _parse(json_string: str, numbers: _Numbers) -> object:
    """Parse *json_string*, numbers held as their text.

    :raises ValueError: when it is not JSON, repeats a key in one object
        (``DuplicateKeyError``), or uses ``NaN`` or ``Infinity``
    :raises RecursionError: when it is nested past the recursion limit
    """
    return loads(
        json_string, parse_float=numbers.hold, parse_int=numbers.hold,
        parse_constant=refuse_constant, object_pairs_hook=unique_pairs)


def _load(json_string: str, numbers: _Numbers) -> object:
    """Parse *json_string*, numbers held as their text; raise ``ITEJsonException`` when it is not JSON."""
    try:
        return _parse(json_string, numbers)
    except DuplicateKeyError as error:
        message = json_duplicate_key_error.format(key=error.args[0])
        pybreeze_logger.error(message)
        raise ITEJsonException(message) from error
    except (ValueError, RecursionError) as error:
        # A JSONDecodeError is a ValueError. RecursionError: input nested
        # deeper than the interpreter's recursion limit.
        pybreeze_logger.error(wrong_json_data_error)
        raise ITEJsonException(wrong_json_data_error) from error


def _process_json(json_string: str, **kwargs) -> str:
    if not isinstance(json_string, str):
        # Not text to parse: shown as JSON as it is
        try:
            return dumps(json_string, indent=4, sort_keys=True, **kwargs)
        except TypeError as err:
            raise ITEJsonException(wrong_json_data_error) from err
    numbers = _Numbers()
    value = _load(json_string, numbers)
    kwargs.setdefault("ensure_ascii", False)
    try:
        return numbers.restore(dumps(value, indent=4, sort_keys=True, **kwargs))
    except (TypeError, ValueError, RecursionError) as error:
        raise ITEJsonException(wrong_json_data_error) from error


def reformat_json(json_string: str, **kwargs) -> str:
    """Return *json_string* indented by four, keys sorted, numbers and characters as written.

    :raises ITEJsonException: when it is not JSON, repeats a key in one object,
        or uses ``NaN`` or ``Infinity``
    """
    try:
        return _process_json(json_string, **kwargs)
    except ITEJsonException as err:
        raise ITEJsonException(f"{cant_reformat_json_error} ({err})") from err


def pretty_json_or_none(json_string: str, *, sort_keys: bool = False) -> str | None:
    """*json_string* indented by four, numbers and characters as written; ``None`` when it is not JSON.

    For text that may be anything -- a response body, a token's segment -- so
    nothing is logged when it is not JSON. What JSON Format refuses is refused
    here too: a key repeated in one object (``json.loads`` kept its last value
    without a word), ``NaN`` and ``Infinity``. A number keeps its text, where
    ``float`` made ``1e400`` the ``Infinity`` that is not JSON.

    :param json_string: the text to lay out
    :param sort_keys: sort each object's keys; otherwise they keep their order
    """
    numbers = _Numbers()
    try:
        value = _parse(json_string, numbers)
        return numbers.restore(dumps(value, indent=4, sort_keys=sort_keys, ensure_ascii=False))
    except (ValueError, RecursionError):
        return None


# Compact separators for minified JSON: no spaces after ',' or ':'.
_MINIFY_SEPARATORS = (",", ":")


def minify_json(json_string: str) -> str:
    """Return *json_string* re-serialised with no insignificant whitespace.

    Numbers and characters stay as written, and key order is kept.

    :param json_string: the JSON text to compact
    :return: the minified JSON on a single line
    :raises ITEJsonException: when the input is not valid JSON, repeats a key
        in one object, or uses ``NaN`` or ``Infinity``
    """
    numbers = _Numbers()
    value = _load(json_string, numbers)
    try:
        return numbers.restore(dumps(value, separators=_MINIFY_SEPARATORS, ensure_ascii=False))
    except RecursionError as error:
        raise ITEJsonException(wrong_json_data_error) from error

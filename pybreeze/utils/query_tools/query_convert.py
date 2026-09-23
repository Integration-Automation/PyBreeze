"""Convert between URL query strings and JSON objects.

Form bodies and query strings (``a=1&b=2``) and JSON bodies are the two shapes an
API request most often takes. This module converts either way, URL-decoding and
-encoding as needed, so an automation engineer can reshape a captured request
without hand-editing.

Repeated keys round-trip through JSON as arrays: ``a=1&a=2`` becomes
``{"a": ["1", "2"]}`` and back.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qsl, urlencode

from pybreeze.utils.exception.exception_tags import (
    invalid_json_for_query_error,
    invalid_json_object_error,
    nested_query_value_error,
    unencodable_text_error,
)
from pybreeze.utils.exception.exceptions import QueryConvertException
from pybreeze.utils.json_format.view_safe import dumps_for_view
from pybreeze.utils.logging.logger import pybreeze_logger


def query_to_dict(query: str) -> dict[str, str | list[str]]:
    """Parse a URL query string into a dict, URL-decoding values.

    A key that appears more than once maps to a list of its values, preserving
    order; a key that appears once maps to its single value.

    :param query: a query string such as ``a=1&b=2`` (a leading ``?`` is ignored)
    :return: the parsed mapping
    """
    stripped = query.strip().lstrip("?")
    pairs = parse_qsl(stripped, keep_blank_values=True)
    result: dict[str, str | list[str]] = {}
    for key, value in pairs:
        if key in result:
            existing = result[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[key] = [existing, value]
        else:
            result[key] = value
    return result


def query_round_trips(query: str) -> bool:
    """Whether decoding *query* into pairs and encoding them again gives it back.

    The cURL and HAR import split only such a query into ``params``, and the
    URL Builder shows only such a query as a dict; any other stays the text it
    was, which ``requests`` sends as it is. Split and encoded again,
    ``?flag&q=%B0&r=/x`` went out as ``?flag=&q=%EF%BF%BD&r=%2Fx``: a
    valueless key gained ``=``, a byte that is not UTF-8 became U+FFFD, and
    ``/`` was escaped, which breaks a signed URL.
    """
    return urlencode(parse_qsl(query, keep_blank_values=True)) == query


def query_to_json(query: str) -> str:
    """Convert a URL query string into pretty-printed JSON.

    :param query: the query string to convert
    :return: a formatted JSON object string
    """
    return dumps_for_view(query_to_dict(query), indent=4, sort_keys=True)


def coerce_scalar(value: object) -> str:
    """Render a scalar JSON value as the string a query string would carry.

    ``null`` is an empty value (``a=``), not Python's ``None``; an object or a
    list inside a list has no query form and is refused rather than sent as
    its Python repr.

    :raises QueryConvertException: for an object, or a list nested in a list
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        pybreeze_logger.error(nested_query_value_error)
        raise QueryConvertException(nested_query_value_error)
    return str(value)


def json_to_query(json_text: str) -> str:
    """Convert a JSON object into a URL query string, URL-encoding values.

    List values expand to a repeated key (``{"a": [1, 2]}`` -> ``a=1&a=2``).

    :param json_text: a JSON object of key/value (or key/list) pairs
    :return: the URL-encoded query string
    :raises QueryConvertException: when the input is not valid JSON or not an object
    """
    try:
        parsed = load_json_verbatim(json_text)
    # json.JSONDecodeError derives from ValueError; RecursionError is JSON
    # nested deeper than the parser goes, which escaped the tab's slot
    except (ValueError, RecursionError) as error:
        pybreeze_logger.error(invalid_json_for_query_error)
        raise QueryConvertException(invalid_json_for_query_error) from error
    if not isinstance(parsed, dict):
        pybreeze_logger.error(invalid_json_object_error)
        raise QueryConvertException(invalid_json_object_error)

    pairs: list[tuple[str, str]] = []
    for key, value in parsed.items():
        if isinstance(value, list):
            pairs.extend((key, coerce_scalar(item)) for item in value)
        else:
            pairs.append((key, coerce_scalar(value)))
    return encode_pairs(pairs)


def encode_pairs(pairs: list[tuple[str, str]]) -> str:
    """``urlencode`` *pairs*, refusing text a URL cannot carry.

    :raises QueryConvertException: for a lone surrogate (``"\\ud83d"`` in the
        JSON), which UTF-8 cannot encode: the ``UnicodeEncodeError`` escaped the
        tab's slot, and the previous output stayed on screen, savable
    """
    try:
        return urlencode(pairs)
    except UnicodeEncodeError as error:
        pybreeze_logger.error(unencodable_text_error)
        raise QueryConvertException(unencodable_text_error) from error


def _refuse_constant(name: str) -> None:
    """``NaN`` and ``Infinity`` are Python's extensions, not JSON."""
    raise ValueError(f"{name} is not JSON")


def load_json_verbatim(json_text: str) -> object:
    """Parse *json_text* with every number kept as the text it was written as.

    Through ``float`` a query value changed: ``1E3`` became ``1000.0``, a long
    integer written with a fraction lost its digits, ``1e400`` became ``inf``,
    and ``NaN`` was accepted. ``NaN`` and ``Infinity`` are refused.

    :raises ValueError: when it is not JSON
    :raises RecursionError: when it is nested deeper than the parser goes
    """
    return json.loads(json_text, parse_float=str, parse_int=str, parse_constant=_refuse_constant)

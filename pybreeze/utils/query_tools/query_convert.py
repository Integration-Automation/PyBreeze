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
)
from pybreeze.utils.exception.exceptions import QueryConvertException
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


def query_to_json(query: str) -> str:
    """Convert a URL query string into pretty-printed JSON.

    :param query: the query string to convert
    :return: a formatted JSON object string
    """
    return json.dumps(query_to_dict(query), indent=4, ensure_ascii=False, sort_keys=True)


def _coerce_scalar(value: object) -> str:
    """Render a scalar JSON value as the string a query string would carry."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def json_to_query(json_text: str) -> str:
    """Convert a JSON object into a URL query string, URL-encoding values.

    List values expand to a repeated key (``{"a": [1, 2]}`` -> ``a=1&a=2``).

    :param json_text: a JSON object of key/value (or key/list) pairs
    :return: the URL-encoded query string
    :raises QueryConvertException: when the input is not valid JSON or not an object
    """
    try:
        parsed = json.loads(json_text)
    # json.JSONDecodeError derives from ValueError.
    except ValueError as error:
        pybreeze_logger.error(invalid_json_for_query_error)
        raise QueryConvertException(invalid_json_for_query_error) from error
    if not isinstance(parsed, dict):
        pybreeze_logger.error(invalid_json_object_error)
        raise QueryConvertException(invalid_json_object_error)

    pairs: list[tuple[str, str]] = []
    for key, value in parsed.items():
        if isinstance(value, list):
            pairs.extend((key, _coerce_scalar(item)) for item in value)
        else:
            pairs.append((key, _coerce_scalar(value)))
    return urlencode(pairs)

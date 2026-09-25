"""Decide how a parsed request's body should be sent.

Both the ``requests`` code generator and the automation-module templates need the
same decision — send the body as a JSON object or as a raw string — so it lives
here once instead of being duplicated in each generator.
"""
from __future__ import annotations

import json
import math
from decimal import Decimal

from pybreeze.utils.curl_import.curl_parser import CurlRequest, add_repeated_value
from pybreeze.utils.json_format.json_process import refuse_constant, unique_pairs

# Header that carries the body's media type
_CONTENT_TYPE_HEADER = "content-type"
# Media type that marks a JSON request body
_JSON_MEDIA_TYPE = "application/json"
# Deepest nesting a JSON body is written into a script as a Python literal.
# Writing a deeper one recursed past Python's limit (600 levels), and Python
# refuses a script nesting brackets more than 200 deep anyway
_MAX_LITERAL_DEPTH = 100

# How a body should be sent: ("json", parsed_object) or ("data", raw_string)
BodyKind = tuple[str, object]


def body_kind(request: CurlRequest) -> BodyKind | None:
    """Return how *request*'s body should be sent, or ``None`` when there is none.

    The body is treated as JSON only when the ``Content-Type`` says so **and** the
    body parses as JSON that the object sends back unchanged; otherwise it is
    sent as the raw string curl sends. A repeated key (the object keeps the
    last), a number a float cannot hold (``0.10000000000000000001``),
    ``NaN`` or JSON nested deeper than the parser goes are sent raw.

    :param request: the parsed curl request
    :return: ``("json", obj)``, ``("data", raw)``, or ``None`` when there is no body
    """
    if not request.body:
        return None
    content_type = (request.header_value(_CONTENT_TYPE_HEADER) or "").lower()
    if _JSON_MEDIA_TYPE in content_type:
        try:
            parsed = json.loads(
                request.body, parse_float=_exact_float, parse_constant=refuse_constant,
                object_pairs_hook=unique_pairs)
        # RecursionError: nesting deeper than the parser goes, which escaped
        # the cURL tab, the HAR generator and the script templates
        except (ValueError, TypeError, RecursionError):
            return "data", request.body
        if _depth(parsed) <= _MAX_LITERAL_DEPTH:
            return "json", parsed
    return "data", request.body


def _depth(value: object) -> int:
    """How deep *value*'s lists and dicts nest, counted without recursing."""
    deepest = 0
    pending: list[tuple[object, int]] = [(value, 0)]
    while pending:
        item, level = pending.pop()
        deepest = max(deepest, level)
        if isinstance(item, dict):
            pending.extend((child, level + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, level + 1) for child in item)
    return deepest


def _exact_float(text: str) -> float:
    """*text* as a float, when the float is written back as the same number.

    :raises ValueError: when it is not (too many digits, or out of range)
    """
    value = float(text)
    survives = f"{text} does not survive as a float"
    if not math.isfinite(value):
        raise ValueError(survives)
    # Decimal compares by value: "1.5" round-trips and this is false
    if Decimal(repr(value)) != Decimal(text):  # NOSONAR S2583
        raise ValueError(survives)
    return value


# Multipart form split into plain fields and file uploads (field -> filename);
# a field given more than once maps to the list of its values
FormParts = tuple[dict[str, str | list[str]], dict[str, str | list[str]]]


def form_parts(request: CurlRequest) -> FormParts:
    """Split ``-F`` form fields into plain data fields and file uploads.

    A field ``name=value`` is a plain data field; ``name=@path`` (curl's file
    syntax) is a file upload whose filename is ``path`` (any ``;type=`` suffix is
    dropped).

    :param request: the parsed curl request
    A field given more than once keeps every value, as a list: curl sends
    each ``-F``, and a dict kept only the last (two ``-F f=@...`` uploaded one
    file).

    :return: ``(data_fields, file_fields)`` where ``file_fields`` maps a field name
        to its filename, or to the list of them
    """
    data_fields: dict[str, str | list[str]] = {}
    file_fields: dict[str, str | list[str]] = {}
    for fragment in request.form_fields:
        key, separator, value = fragment.partition("=")
        if not separator:
            continue
        if value.startswith("@"):
            add_repeated_value(file_fields, key, value[1:].split(";", 1)[0])
        else:
            add_repeated_value(data_fields, key, value)
    for fragment in request.form_strings:
        key, separator, value = fragment.partition("=")
        if separator:
            add_repeated_value(data_fields, key, value)
    return data_fields, file_fields


# One multipart field as sent: its name, whether it uploads a file, and the
# file name or the text
FormEntry = tuple[str, bool, str]

# The media type every -F form is sent as
_MULTIPART_MEDIA_TYPE = "multipart/"


def form_entries(request: CurlRequest) -> list[FormEntry]:
    """Every ``-F`` field of *request*, uploads and text alike, each repeat kept.

    curl sends a form given with ``-F`` as ``multipart/form-data`` whether or
    not it uploads a file. Generated as ``data=`` when it held only text,
    ``requests`` sent it URL-encoded instead: the generators now put every
    field in ``files=``, a text field as ``(None, text)``.
    """
    data_fields, file_fields = form_parts(request)
    entries: list[FormEntry] = []
    for fields, is_file in ((data_fields, False), (file_fields, True)):
        for name, values in fields.items():
            entries.extend((name, is_file, value) for value in (values if isinstance(values, list) else [values]))
    return entries


def sent_headers(request: CurlRequest) -> dict[str, str]:
    """The headers to generate for *request*.

    A form's ``Content-Type: multipart/...`` is left out: ``requests`` writes
    its own with the boundary it chose, and does not replace one given
    explicitly, so the copied header (without a boundary, or with the browser's)
    left the server unable to read the body.
    """
    if not request.has_form:
        return dict(request.headers)
    return {
        name: value for name, value in request.headers.items()
        if not (name.lower() == _CONTENT_TYPE_HEADER and value.lower().lstrip().startswith(_MULTIPART_MEDIA_TYPE))
    }

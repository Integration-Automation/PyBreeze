"""Decide how a parsed request's body should be sent.

Both the ``requests`` code generator and the automation-module templates need the
same decision — send the body as a JSON object or as a raw string — so it lives
here once instead of being duplicated in each generator.
"""
from __future__ import annotations

import json

from pybreeze.utils.curl_import.curl_parser import CurlRequest, add_repeated_value

# Header that carries the body's media type
_CONTENT_TYPE_HEADER = "content-type"
# Media type that marks a JSON request body
_JSON_MEDIA_TYPE = "application/json"

# How a body should be sent: ("json", parsed_object) or ("data", raw_string)
BodyKind = tuple[str, object]


def body_kind(request: CurlRequest) -> BodyKind | None:
    """Return how *request*'s body should be sent, or ``None`` when there is none.

    The body is treated as JSON only when the ``Content-Type`` says so **and** the
    body actually parses as JSON; otherwise it is sent as a raw string.

    :param request: the parsed curl request
    :return: ``("json", obj)``, ``("data", raw)``, or ``None`` when there is no body
    """
    if not request.body:
        return None
    content_type = (request.header_value(_CONTENT_TYPE_HEADER) or "").lower()
    if _JSON_MEDIA_TYPE in content_type:
        try:
            return "json", json.loads(request.body)
        except (ValueError, TypeError):
            return "data", request.body
    return "data", request.body


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


def file_uploads(file_fields: dict[str, str | list[str]]) -> list[tuple[str, str]]:
    """Every ``(field, filename)`` upload, a repeated field once per file."""
    return [
        (field, name) for field, names in file_fields.items()
        for name in (names if isinstance(names, list) else [names])
    ]

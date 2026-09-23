"""Generate Python ``requests`` code from a parsed :class:`CurlRequest`.

The output is a small, ready-to-run script that mirrors the captured request,
so an automation engineer can paste a browser ``curl`` command and get working
Python instead of hand-translating headers, bodies and multipart forms.
"""
from __future__ import annotations

import json
import math
import re

from pybreeze.utils.curl_import.curl_parser import CurlRequest
from pybreeze.utils.curl_import.request_body import body_kind, form_parts

# Keyword argument passing the request body to ``requests.request``.
_DATA_KWARG = "data=data"
# Import line every generated ``requests`` script starts with
REQUESTS_IMPORT = "import requests"
# One level of indentation in generated code
_INDENT = "    "
# A UTF-16 surrogate: only ever half of a character
_SURROGATE = re.compile("[\ud800-\udfff]")


def _format_dict(name: str, mapping: dict[str, str | list[str]]) -> str | None:
    """Render ``name = { ... }`` with one entry per line, or ``None`` if empty.

    A value may be a list: a query parameter given more than once.
    """
    if not mapping:
        return None
    lines = [f"{name} = {{"]
    lines.extend(f"    {python_string(key)}: {python_literal(value, inline=True)},"
                 for key, value in mapping.items())
    lines.append("}")
    return "\n".join(lines)


def _format_files(file_fields: dict[str, str]) -> str:
    """Render a ``files = { ... }`` block that opens each upload."""
    lines = ["files = {"]
    lines.extend(
        f'    {python_string(field)}: open({python_string(filename)}, "rb"),'
        for field, filename in file_fields.items()
    )
    lines.append("}")
    return "\n".join(lines)


def data_from_file_expr(request: CurlRequest) -> str:
    """Build a Python expression reading the body from its ``@file`` reference(s).

    curl joins several data pieces with ``&``; inline data is emitted as a string
    literal and each file as ``open(...).read()``.

    :param request: the parsed curl request (must have ``data_file_refs``)
    :return: a Python expression, e.g. ``open("body.json", encoding="utf-8").read()``
    """
    pieces: list[str] = []
    if request.data_parts:
        pieces.append(python_string(request.body))
    pieces.extend(
        f'open({python_string(name)}, encoding="utf-8").read()'
        for name in request.data_file_refs
    )
    return ' + "&" + '.join(pieces)


def python_string(text: str) -> str:
    """Write *text* as a Python string literal, in double quotes.

    ``json.dumps`` by default writes a character outside the Basic Multilingual
    Plane -- an emoji, a rare CJK character -- as a pair of ``\\uXXXX``
    surrogates: one character to JSON, two to Python, which then cannot send
    them. Written as itself it is one character to both. A lone surrogate,
    which cannot be written to a UTF-8 file, falls back to ``repr``.
    """
    if _SURROGATE.search(text):
        return repr(text)
    return json.dumps(text, ensure_ascii=False)


def python_literal(value: object, *, inline: bool = False, level: int = 0) -> str:
    """Write a decoded JSON value as Python source that evaluates back to it.

    ``json.dumps`` is not Python: ``true``, ``false`` and ``null`` are names that
    do not exist there, so a JSON body written with it made the generated script
    fail with ``NameError``. Strings go through :func:`python_string`.

    :param value: what ``json.loads`` returned
    :param inline: all on one line, for a keyword argument inside a call
    :param level: how deep *value* is, for the indentation of a nested block
    """
    if isinstance(value, dict):
        items = [f"{python_string(key)}: {python_literal(item, inline=inline, level=level + 1)}"
                 for key, item in value.items()]
        return _python_container("{", items, "}", inline, level)
    if isinstance(value, list):
        items = [python_literal(item, inline=inline, level=level + 1) for item in value]
        return _python_container("[", items, "]", inline, level)
    if isinstance(value, str):
        return python_string(value)
    if isinstance(value, float) and not math.isfinite(value):
        return f'float("{value}")'
    return repr(value)  # bool, None, int, finite float: repr is their literal


def _python_container(opening: str, items: list[str], closing: str, inline: bool, level: int) -> str:
    """Lay out *items* between *opening* and *closing*, as ``json.dumps(indent=4)`` would."""
    if not items:
        return opening + closing
    if inline:
        return opening + ", ".join(items) + closing
    inner = _INDENT * (level + 1)
    body = ",\n".join(inner + item for item in items)
    return f"{opening}\n{body}\n{_INDENT * level}{closing}"


def payload_python_parts(request: CurlRequest) -> tuple[list[str], list[str]]:
    """Return the assignment lines and call kwargs for the request payload.

    Multipart form fields (``-F``) take precedence, then a file-based body
    (``-d @file``), then a plain body; the result covers ``data`` / ``files`` for
    forms or ``json`` / ``data`` for a body.

    :param request: the parsed curl request
    :return: ``(assignment_lines, keyword_arguments)``
    """
    if request.has_form:
        data_fields, file_fields = form_parts(request)
        sections: list[str] = []
        kwargs: list[str] = []
        data_block = _format_dict("data", data_fields)
        if data_block is not None:
            sections.append(data_block)
            kwargs.append(_DATA_KWARG)
        if file_fields:
            sections.append(_format_files(file_fields))
            kwargs.append("files=files")
        return sections, kwargs

    if request.data_file_refs:
        return [f"data = {data_from_file_expr(request)}"], [_DATA_KWARG]

    kind = body_kind(request)
    if kind is None:
        return [], []
    if kind[0] == "json":
        return [f"json_body = {python_literal(kind[1])}"], ["json=json_body"]
    return [f"data = {python_string(kind[1])}"], [_DATA_KWARG]


def _call_keyword_arguments(request: CurlRequest, payload_kwargs: list[str]) -> list[str]:
    """Build the keyword arguments passed to ``requests.request``."""
    arguments = ["url"]
    if request.headers:
        arguments.append("headers=headers")
    if request.params:
        arguments.append("params=params")
    if request.cookies:
        arguments.append("cookies=cookies")
    arguments.extend(payload_kwargs)
    if request.username is not None:
        arguments.append("auth=auth")
    if request.timeout is not None:
        # timeout is validated as numeric by the parser, so it is safe inline.
        arguments.append(f"timeout={request.timeout}")
    return arguments


def request_statements(request: CurlRequest) -> list[str]:
    """Return the ``requests`` statements from ``url = ...`` to ``response = ...``.

    Shared by the plain script and the pytest generators; each element may itself
    be a multi-line block (a dict literal).

    :param request: the parsed curl request
    :return: the statement blocks in order
    """
    payload_sections, payload_kwargs = payload_python_parts(request)
    statements: list[str] = [f"url = {python_string(request.url)}"]

    headers_block = _format_dict("headers", request.headers)
    if headers_block is not None:
        statements.append(headers_block)
    params_block = _format_dict("params", request.params)
    if params_block is not None:
        statements.append(params_block)
    cookies_block = _format_dict("cookies", request.cookies)
    if cookies_block is not None:
        statements.append(cookies_block)
    statements.extend(payload_sections)
    if request.username is not None:
        statements.append(
            f"auth = ({python_string(request.username)}, {python_string(request.password or '')})")

    arguments = ", ".join(_call_keyword_arguments(request, payload_kwargs))
    statements.append(
        f'response = requests.request({python_string(request.method)}, {arguments})')
    return statements


def to_requests_code(request: CurlRequest) -> str:
    """Generate a runnable ``requests`` script for *request*.

    :param request: the parsed curl request
    :return: Python source using the ``requests`` library
    """
    lines = [REQUESTS_IMPORT, ""]
    lines.extend(request_statements(request))
    lines.append("print(response.status_code)")
    lines.append("print(response.text)")
    return "\n".join(lines) + "\n"

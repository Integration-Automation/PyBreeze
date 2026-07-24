"""Generate Python ``requests`` code from a parsed :class:`CurlRequest`.

The output is a small, ready-to-run script that mirrors the captured request,
so an automation engineer can paste a browser ``curl`` command and get working
Python instead of hand-translating headers, bodies and multipart forms.
"""
from __future__ import annotations

import json

from pybreeze.utils.curl_import.curl_parser import CurlRequest
from pybreeze.utils.curl_import.request_body import body_kind, form_parts

# Keyword argument passing the request body to ``requests.request``.
_DATA_KWARG = "data=data"


def _format_dict(name: str, mapping: dict[str, str]) -> str | None:
    """Render ``name = { ... }`` with one entry per line, or ``None`` if empty."""
    if not mapping:
        return None
    lines = [f"{name} = {{"]
    lines.extend(f"    {json.dumps(key)}: {json.dumps(value)}," for key, value in mapping.items())
    lines.append("}")
    return "\n".join(lines)


def _format_files(file_fields: dict[str, str]) -> str:
    """Render a ``files = { ... }`` block that opens each upload."""
    lines = ["files = {"]
    lines.extend(
        f'    {json.dumps(field)}: open({json.dumps(filename)}, "rb"),'
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
        pieces.append(json.dumps(request.body))
    pieces.extend(
        f'open({json.dumps(name)}, encoding="utf-8").read()'
        for name in request.data_file_refs
    )
    return ' + "&" + '.join(pieces)


def payload_python_parts(request: CurlRequest) -> tuple[list[str], list[str]]:
    """Return the assignment lines and call kwargs for the request payload.

    Multipart form fields (``-F``) take precedence, then a file-based body
    (``-d @file``), then a plain body; the result covers ``data`` / ``files`` for
    forms or ``json`` / ``data`` for a body.

    :param request: the parsed curl request
    :return: ``(assignment_lines, keyword_arguments)``
    """
    if request.form_fields:
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
        return [f"json_body = {json.dumps(kind[1], indent=4)}"], ["json=json_body"]
    return [f"data = {json.dumps(kind[1])}"], [_DATA_KWARG]


def _call_keyword_arguments(request: CurlRequest, payload_kwargs: list[str]) -> list[str]:
    """Build the keyword arguments passed to ``requests.request``."""
    arguments = ["url"]
    if request.headers:
        arguments.append("headers=headers")
    if request.params:
        arguments.append("params=params")
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
    statements: list[str] = [f"url = {json.dumps(request.url)}"]

    headers_block = _format_dict("headers", request.headers)
    if headers_block is not None:
        statements.append(headers_block)
    params_block = _format_dict("params", request.params)
    if params_block is not None:
        statements.append(params_block)
    statements.extend(payload_sections)
    if request.username is not None:
        statements.append(
            f"auth = ({json.dumps(request.username)}, {json.dumps(request.password or '')})")

    arguments = ", ".join(_call_keyword_arguments(request, payload_kwargs))
    statements.append(
        f'response = requests.request({json.dumps(request.method)}, {arguments})')
    return statements


def to_requests_code(request: CurlRequest) -> str:
    """Generate a runnable ``requests`` script for *request*.

    :param request: the parsed curl request
    :return: Python source using the ``requests`` library
    """
    lines = ["import requests", ""]
    lines.extend(request_statements(request))
    lines.append("print(response.status_code)")
    lines.append("print(response.text)")
    return "\n".join(lines) + "\n"

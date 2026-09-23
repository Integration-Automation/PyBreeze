"""Analyse a pasted HTTP response, pulling together the other tools.

Paste a raw response (status line + headers + body, or just a JSON body) and this
module works out what is in it: the status code (looked up in the HTTP reference),
the headers, a pretty-printed JSON body when the body is JSON, and any JWTs found
in the text (decoded via the JWT tool).

It reuses the existing utilities rather than re-implementing them, so the response
inspector stays consistent with the standalone tools.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from pybreeze.utils.curl_import.curl_parser import add_repeated_value
from pybreeze.utils.header_tools.header_analyzer import FOLDED_LINE_START, HEADER_LINE_RE
from pybreeze.utils.http_reference.status_codes import StatusInfo, lookup
from pybreeze.utils.jwt_tools.jwt_decoder import DecodedJwt, decode_jwt, find_tokens
from pybreeze.utils.exception.exceptions import JwtDecodeException
from pybreeze.utils.json_format.view_safe import dumps_for_view

# Matches the response status line, e.g. "HTTP/1.1 200 OK"
_STATUS_LINE_RE = re.compile(r"^HTTP/\d(?:\.\d)?\s+(\d{3})\b")
# An HTTP/2 or HTTP/3 pseudo-header as browsers' tools copy it, e.g. ":status: 200"
_PSEUDO_HEADER_RE = re.compile(r"^:([a-z]+):[ \t]?(.*)$")


@dataclass
class JwtFinding:
    """A JWT discovered in the response text and its decoded form.

    :param token: the raw token as it appeared
    :param decoded: the decoded header/payload/signature
    """

    token: str
    decoded: DecodedJwt


@dataclass
class ResponseAnalysis:
    """The structured result of inspecting a response.

    :param status: the looked-up status, or ``None`` when no status line was found
    :param headers: parsed response headers; a name sent more than once (``Set-Cookie``)
        maps to the list of its values, which cannot be joined into one
    :param body: the raw response body
    :param pretty_body: the body pretty-printed when it is JSON, else ``None``
    :param is_json_body: whether the body parsed as JSON
    :param jwt_findings: JWTs found anywhere in the text, decoded
    """

    status: StatusInfo | None = None
    headers: dict[str, str | list[str]] = field(default_factory=dict)
    body: str = ""
    pretty_body: str | None = None
    is_json_body: bool = False
    jwt_findings: list[JwtFinding] = field(default_factory=list)


def _normalise(text: str) -> str:
    """Normalise line endings to ``\\n``."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _parse_head_and_body(text: str) -> tuple[int | None, dict[str, str], str]:
    """Split *text* into the final response's status code, headers and body.

    ``curl -i`` prints every response it read: ``100 Continue``, a proxy's
    ``200 Connection established``, each redirect with ``-L``. The first status
    line used to be taken, and the real response read as its body; while a
    body starts with a status line, it is parsed again from there.
    """
    lines = _normalise(text).split("\n")
    if len(lines) == 1 and not _STATUS_LINE_RE.match(lines[0]):
        # One line and no status line is a body: "Error: invalid token" is
        # not a header
        return None, {}, text.strip()
    status_code, headers, body = _parse_one_response(lines)
    while _STATUS_LINE_RE.match(body):
        status_code, headers, body = _parse_one_response(body.split("\n"))
    return status_code, headers, body


def _parse_one_response(lines: list[str]) -> tuple[int | None, dict[str, str], str]:
    """Split *lines* into a status code, headers and body.

    Headers run from an optional status line until a blank line or the first line
    that is not a ``Name: Value`` header; everything after is the body.
    """
    index = 0
    status_code: int | None = None
    if lines and _STATUS_LINE_RE.match(lines[0]):
        status_code = int(_STATUS_LINE_RE.match(lines[0]).group(1))
        index = 1

    headers: dict[str, str | list[str]] = {}
    last_name: str | None = None
    while index < len(lines):
        line = lines[index]
        if line.strip() == "":
            index += 1
            break
        if line.startswith(FOLDED_LINE_START) and last_name is not None:
            # A folded continuation of the header above; it ended the headers
            # and began the body, which then no longer read as JSON
            _continue_value(headers, last_name, line.strip())
        elif (pseudo := _PSEUDO_HEADER_RE.match(line)) is not None:
            # It ended the headers, and the rest was read as the body
            if pseudo.group(1) == "status" and status_code is None and pseudo.group(2).strip().isdigit():
                status_code = int(pseudo.group(2).strip())
        elif (match := HEADER_LINE_RE.match(line)) is not None:
            last_name = _same_name(headers, match.group(1))
            add_repeated_value(headers, last_name, match.group(2).strip())
        else:
            break
        index += 1

    body = "\n".join(lines[index:]).strip()
    return status_code, headers, body


def _same_name(headers: dict[str, str | list[str]], name: str) -> str:
    """The spelling *name* is already kept under, header names being case-insensitive.

    ``Set-Cookie`` and ``set-cookie`` were two entries instead of one list.
    """
    lowered = name.lower()
    return next((known for known in headers if known.lower() == lowered), name)


def _continue_value(headers: dict[str, str | list[str]], name: str, more: str) -> None:
    """Join *more* to the last value kept under *name*, with one space."""
    value = headers[name]
    if isinstance(value, list):
        value[-1] = f"{value[-1]} {more}".strip()
    else:
        headers[name] = f"{value} {more}".strip()


def _pretty_json(body: str) -> str | None:
    """Return *body* pretty-printed if it is JSON, else ``None`` (key order kept)."""
    try:
        return dumps_for_view(json.loads(body), indent=4)
    # RecursionError: a body nested past the recursion limit
    except (ValueError, TypeError, RecursionError):
        return None


def _find_jwts(text: str) -> list[JwtFinding]:
    """Find and decode every JWT-looking token in *text*."""
    findings: list[JwtFinding] = []
    for token in find_tokens(text):
        try:
            findings.append(JwtFinding(token=token, decoded=decode_jwt(token)))
        except JwtDecodeException:
            # A token that looks like a JWT but does not decode is simply skipped.
            continue
    return findings


def analyze_response(text: str) -> ResponseAnalysis:
    """Inspect a pasted HTTP response and report what it contains.

    :param text: the raw response text (status line + headers + body, or just a body)
    :return: the structured analysis
    """
    status_code, headers, body = _parse_head_and_body(text)
    pretty_body = _pretty_json(body)
    return ResponseAnalysis(
        status=lookup(status_code) if status_code is not None else None,
        headers=headers,
        body=body,
        pretty_body=pretty_body,
        is_json_body=pretty_body is not None,
        jwt_findings=_find_jwts(text),
    )

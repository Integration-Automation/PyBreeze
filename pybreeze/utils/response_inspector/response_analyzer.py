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

from pybreeze.utils.header_tools.header_analyzer import HEADER_LINE_RE
from pybreeze.utils.http_reference.status_codes import StatusInfo, lookup
from pybreeze.utils.jwt_tools.jwt_decoder import DecodedJwt, decode_jwt, find_tokens
from pybreeze.utils.exception.exceptions import JwtDecodeException

# Matches the response status line, e.g. "HTTP/1.1 200 OK"
_STATUS_LINE_RE = re.compile(r"^HTTP/\d(?:\.\d)?\s+(\d{3})\b")


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
    :param headers: parsed response headers
    :param body: the raw response body
    :param pretty_body: the body pretty-printed when it is JSON, else ``None``
    :param is_json_body: whether the body parsed as JSON
    :param jwt_findings: JWTs found anywhere in the text, decoded
    """

    status: StatusInfo | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    pretty_body: str | None = None
    is_json_body: bool = False
    jwt_findings: list[JwtFinding] = field(default_factory=list)


def _normalise(text: str) -> str:
    """Normalise line endings to ``\\n``."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _parse_head_and_body(text: str) -> tuple[int | None, dict[str, str], str]:
    """Split *text* into a status code, headers and body.

    Headers run from an optional status line until a blank line or the first line
    that is not a ``Name: Value`` header; everything after is the body.
    """
    lines = _normalise(text).split("\n")
    index = 0
    status_code: int | None = None
    if lines and _STATUS_LINE_RE.match(lines[0]):
        status_code = int(_STATUS_LINE_RE.match(lines[0]).group(1))
        index = 1

    headers: dict[str, str] = {}
    while index < len(lines):
        line = lines[index]
        if line.strip() == "":
            index += 1
            break
        match = HEADER_LINE_RE.match(line)
        if match is None:
            break
        headers[match.group(1)] = match.group(2).strip()
        index += 1

    body = "\n".join(lines[index:]).strip()
    return status_code, headers, body


def _pretty_json(body: str) -> str | None:
    """Return *body* pretty-printed if it is JSON, else ``None`` (key order kept)."""
    try:
        parsed = json.loads(body)
    except (ValueError, TypeError):
        return None
    return json.dumps(parsed, indent=4, ensure_ascii=False)


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

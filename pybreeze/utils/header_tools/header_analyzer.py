"""Analyse a block of HTTP headers.

Paste the headers of a request or a response — copied from browser dev tools, a
``curl -i`` run, or a proxy log — and this module reports what is in them: every
header line, names that appear more than once, and the things worth knowing
about while debugging an API (cookie flags, a wildcard CORS policy, a weak HSTS
policy, headers that carry credentials, missing response security headers).

It is the companion of the response inspector, which decodes one whole response;
this looks only at the headers, and looks harder. Pure logic — no Qt, no network.
Findings carry a stable *code* rather than a sentence, so the UI can translate
them; values that could be secrets are never copied into a finding's detail.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

# Severity of a finding: something to fix, or something merely worth knowing.
LEVEL_WARNING = "warning"
LEVEL_INFO = "info"

# Matches one header line, e.g. "Content-Type: application/json"
HEADER_LINE_RE = re.compile(r"^([A-Za-z0-9!#$%&'*+.^_`|~-]+):[ \t]?(.*)$")
# Matches a leading response status line, e.g. "HTTP/1.1 200 OK"
_STATUS_LINE_RE = re.compile(r"^\s*HTTP/\d(?:\.\d)?\s+\d{3}\b")
# Matches the max-age directive of an HSTS policy
_MAX_AGE_RE = re.compile(r"max-age\s*=\s*(\d+)", re.IGNORECASE)

# Header names referenced from more than one table below
_HSTS_HEADER = "strict-transport-security"
_CSP_HEADER = "content-security-policy"
_CONTENT_TYPE_OPTIONS_HEADER = "x-content-type-options"
_CORS_ORIGIN_HEADER = "access-control-allow-origin"
_CORS_CREDENTIALS_HEADER = "access-control-allow-credentials"
_SET_COOKIE_HEADER = "set-cookie"

# An HSTS policy shorter than 180 days is too short to survive a browser restart
# cycle and is below what the preload list accepts.
_MIN_HSTS_MAX_AGE = 15_552_000

# Headers that are legitimately sent more than once, so a repeat is not a finding
_REPEATABLE_HEADERS = frozenset({
    _SET_COOKIE_HEADER, "www-authenticate", "proxy-authenticate", "via", "link", "warning",
})

# Headers only a server sends. Without one of these (or a status line) the block
# is treated as a request, where the missing-response-header checks make no sense.
_RESPONSE_ONLY_HEADERS = frozenset({
    _SET_COOKIE_HEADER, _CSP_HEADER, _HSTS_HEADER, _CONTENT_TYPE_OPTIONS_HEADER,
    _CORS_ORIGIN_HEADER, "server", "x-powered-by", "x-frame-options", "referrer-policy",
    "permissions-policy", "www-authenticate", "location", "etag", "last-modified",
    "age", "retry-after", "content-encoding",
})

# Response security headers, as (lower-case name, canonical name, finding code)
_RESPONSE_SECURITY_HEADERS: tuple[tuple[str, str, str], ...] = (
    (_HSTS_HEADER, "Strict-Transport-Security", "missing_hsts"),
    (_CSP_HEADER, "Content-Security-Policy", "missing_csp"),
    (_CONTENT_TYPE_OPTIONS_HEADER, "X-Content-Type-Options", "missing_content_type_options"),
    ("x-frame-options", "X-Frame-Options", "missing_frame_options"),
    ("referrer-policy", "Referrer-Policy", "missing_referrer_policy"),
)

# Headers whose value is a credential; their presence is reported, never the value
_SENSITIVE_HEADERS = frozenset({
    "authorization", "proxy-authorization", "cookie", "x-api-key", "api-key", "x-auth-token",
})

# CSP directives that give back much of what the policy is meant to take away
_UNSAFE_CSP_DIRECTIVES = ("unsafe-inline", "unsafe-eval")


@dataclass(frozen=True)
class HeaderField:
    """One header line as it was written.

    :param name: the header name, in its original casing
    :param value: the header value, stripped of surrounding whitespace
    """

    name: str
    value: str


@dataclass(frozen=True)
class HeaderFinding:
    """Something worth reporting about a header block.

    :param code: stable slug the UI turns into a translated message
    :param level: :data:`LEVEL_WARNING` or :data:`LEVEL_INFO`
    :param header: the header the finding is about
    :param detail: an untranslated fragment for the message (a value, a count,
        a cookie name); never a credential
    """

    code: str
    level: str
    header: str
    detail: str = ""


@dataclass
class HeaderAnalysis:
    """The result of analysing a header block.

    :param fields: every header line found, in the order they appeared
    :param duplicates: lower-case name -> how often it appeared (repeats only)
    :param findings: what was noticed, warnings first
    :param looks_like_response: whether the block came from a server response,
        which is when the missing-security-header checks apply
    """

    fields: list[HeaderField] = field(default_factory=list)
    duplicates: dict[str, int] = field(default_factory=dict)
    findings: list[HeaderFinding] = field(default_factory=list)
    looks_like_response: bool = False


def parse_headers(text: str) -> list[HeaderField]:
    """Pull the header lines out of *text*.

    Accepts a bare header block or a whole request/response: a start line does
    not parse as a header and is skipped, and a blank line after the headers ends
    the block so a pasted body is not read as more headers.

    :param text: the pasted text
    :return: the headers found, in order, duplicates kept
    """
    fields: list[HeaderField] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not line.strip():
            if fields:
                break  # the blank line between the headers and the body
            continue
        match = HEADER_LINE_RE.match(line)
        if match is not None:
            fields.append(HeaderField(name=match.group(1), value=match.group(2).strip()))
    return fields


def _first_value(fields: list[HeaderField], name: str) -> str | None:
    """Return the first value of the header called *name*, or ``None``."""
    for header in fields:
        if header.name.lower() == name:
            return header.value
    return None


def _duplicate_counts(fields: list[HeaderField]) -> dict[str, int]:
    """Count the header names that appear more than once, case-insensitively."""
    counts: dict[str, int] = {}
    for header in fields:
        lowered = header.name.lower()
        counts[lowered] = counts.get(lowered, 0) + 1
    return {name: count for name, count in counts.items() if count > 1}


def _duplicate_findings(duplicates: dict[str, int]) -> list[HeaderFinding]:
    """Report repeated headers, except the ones HTTP expects to repeat."""
    return [
        HeaderFinding("duplicate_header", LEVEL_WARNING, name, str(count))
        for name, count in duplicates.items()
        if name not in _REPEATABLE_HEADERS
    ]


def _check_content_type_options(header: HeaderField) -> list[HeaderFinding]:
    """``X-Content-Type-Options`` does nothing unless its value is ``nosniff``."""
    if header.value.strip().lower() == "nosniff":
        return []
    return [HeaderFinding(
        "content_type_options_not_nosniff", LEVEL_WARNING, header.name, header.value)]


def _check_hsts(header: HeaderField) -> list[HeaderFinding]:
    """Flag an HSTS policy whose ``max-age`` is missing or too short to matter."""
    match = _MAX_AGE_RE.search(header.value)
    max_age = int(match.group(1)) if match is not None else 0
    if max_age >= _MIN_HSTS_MAX_AGE:
        return []
    return [HeaderFinding("hsts_weak_max_age", LEVEL_WARNING, header.name, str(max_age))]


def _check_csp(header: HeaderField) -> list[HeaderFinding]:
    """Flag the CSP directives that re-allow what the policy is meant to block."""
    lowered = header.value.lower()
    return [
        HeaderFinding("csp_unsafe_directive", LEVEL_WARNING, header.name, directive)
        for directive in _UNSAFE_CSP_DIRECTIVES if directive in lowered
    ]


def _check_cors_origin(header: HeaderField) -> list[HeaderFinding]:
    """Note a CORS policy that allows every origin."""
    if header.value.strip() != "*":
        return []
    return [HeaderFinding("cors_wildcard_origin", LEVEL_INFO, header.name)]


def _check_set_cookie(header: HeaderField) -> list[HeaderFinding]:
    """Check one ``Set-Cookie`` for the attributes that keep it from leaking."""
    segments = header.value.split(";")
    attributes = [segment.strip().lower() for segment in segments[1:]]
    cookie_name = segments[0].split("=", 1)[0].strip() or header.name
    findings: list[HeaderFinding] = []
    if "secure" not in attributes:
        findings.append(HeaderFinding("cookie_not_secure", LEVEL_WARNING, header.name, cookie_name))
    if "httponly" not in attributes:
        findings.append(
            HeaderFinding("cookie_not_httponly", LEVEL_WARNING, header.name, cookie_name))
    if not any(attribute.startswith("samesite") for attribute in attributes):
        findings.append(HeaderFinding("cookie_no_samesite", LEVEL_INFO, header.name, cookie_name))
    return findings


def _check_content_type(header: HeaderField) -> list[HeaderFinding]:
    """Note a textual media type left without a charset, where it still matters."""
    lowered = header.value.lower()
    if not lowered.startswith("text/") or "charset=" in lowered:
        return []
    return [HeaderFinding("content_type_no_charset", LEVEL_INFO, header.name, header.value)]


def _check_banner(header: HeaderField) -> list[HeaderFinding]:
    """Note a product banner: it tells a visitor what software to look up."""
    if not header.value.strip():
        return []
    return [HeaderFinding("server_banner", LEVEL_INFO, header.name, header.value)]


def _check_deprecated(header: HeaderField) -> list[HeaderFinding]:
    """Note a header browsers no longer honour."""
    return [HeaderFinding("deprecated_header", LEVEL_INFO, header.name, header.value)]


# lower-case header name -> the check that applies to it. A table keeps
# _field_findings flat instead of a branch per header.
_FIELD_CHECKS: dict[str, Callable[[HeaderField], list[HeaderFinding]]] = {
    _CONTENT_TYPE_OPTIONS_HEADER: _check_content_type_options,
    _HSTS_HEADER: _check_hsts,
    _CSP_HEADER: _check_csp,
    _CORS_ORIGIN_HEADER: _check_cors_origin,
    _SET_COOKIE_HEADER: _check_set_cookie,
    "content-type": _check_content_type,
    "server": _check_banner,
    "x-powered-by": _check_banner,
    "x-xss-protection": _check_deprecated,
}


def _field_findings(fields: list[HeaderField]) -> list[HeaderFinding]:
    """Run the per-header checks over every field."""
    findings: list[HeaderFinding] = []
    for header in fields:
        lowered = header.name.lower()
        check = _FIELD_CHECKS.get(lowered)
        if check is not None:
            findings.extend(check(header))
        if lowered in _SENSITIVE_HEADERS:
            # The value is a credential, so it is deliberately not reported.
            findings.append(HeaderFinding("sensitive_header", LEVEL_INFO, header.name))
    return findings


def _cors_credentials_findings(fields: list[HeaderField]) -> list[HeaderFinding]:
    """Flag a wildcard origin combined with credentials.

    Browsers reject that combination outright, so a policy that sends both never
    worked the way its author expected.
    """
    origin = _first_value(fields, _CORS_ORIGIN_HEADER)
    credentials = _first_value(fields, _CORS_CREDENTIALS_HEADER)
    if origin is None or origin.strip() != "*":
        return []
    if credentials is None or credentials.strip().lower() != "true":
        return []
    return [HeaderFinding("cors_wildcard_with_credentials", LEVEL_WARNING, _CORS_ORIGIN_HEADER)]


def _missing_security_findings(fields: list[HeaderField]) -> list[HeaderFinding]:
    """Report the response security headers that are not present."""
    present = {header.name.lower() for header in fields}
    return [
        HeaderFinding(code, LEVEL_INFO, canonical)
        for name, canonical, code in _RESPONSE_SECURITY_HEADERS if name not in present
    ]


def _looks_like_response(text: str, fields: list[HeaderField]) -> bool:
    """Whether the block came from a response rather than a request."""
    if _STATUS_LINE_RE.match(text):
        return True
    return any(header.name.lower() in _RESPONSE_ONLY_HEADERS for header in fields)


def analyze_headers(text: str) -> HeaderAnalysis:
    """Analyse a pasted block of HTTP headers.

    :param text: the headers, optionally with a start line and a body after them
    :return: the parsed fields, repeated names, and the findings, warnings first
    """
    fields = parse_headers(text)
    duplicates = _duplicate_counts(fields)
    from_response = _looks_like_response(text, fields)

    findings = _duplicate_findings(duplicates)
    findings.extend(_field_findings(fields))
    findings.extend(_cors_credentials_findings(fields))
    if from_response:
        findings.extend(_missing_security_findings(fields))
    # Stable sort: warnings first, each group still in the order it was found.
    findings.sort(key=lambda finding: 0 if finding.level == LEVEL_WARNING else 1)

    return HeaderAnalysis(
        fields=fields, duplicates=duplicates, findings=findings,
        looks_like_response=from_response)

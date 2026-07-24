"""Parse a ``curl`` command line into a structured request.

Copying a request as ``curl`` from browser dev tools is the fastest way to
capture an API call. This module turns that command string into a
:class:`CurlRequest`, so the rest of PyBreeze can format it, generate request
code, or drive an automation module without re-typing headers by hand.

The parser is pure logic (no Qt, no network) and never executes the command.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from urllib.parse import quote

from pybreeze.utils.exception.exception_tags import (
    empty_curl_command_error,
    malformed_curl_command_error,
    not_a_curl_command_error,
)
from pybreeze.utils.exception.exceptions import CurlParseException
from pybreeze.utils.logging.logger import pybreeze_logger

# HTTP method used when none is given and no body is present
_DEFAULT_METHOD = "GET"
# HTTP method implied when a body is present but no method is given
_METHOD_WITH_BODY = "POST"
# Header name that carries a request body's media type
_CONTENT_TYPE_HEADER = "content-type"
# Matches a backslash or caret line continuation before a newline
_LINE_CONTINUATION_RE = re.compile(r"[\\^]\r?\n")


@dataclass
class CurlRequest:
    """A structured HTTP request extracted from a ``curl`` command.

    :param method: HTTP method (upper-case), e.g. ``GET`` or ``POST``
    :param url: request URL, or an empty string when none was found
    :param headers: request headers as ``name -> value`` (names kept as written)
    :param params: query parameters collected from ``-G`` / ``--data`` pairs
    :param data_parts: raw body fragments in the order they appeared
    :param username: basic-auth user, or ``None``
    :param password: basic-auth password, or ``None``
    :param send_data_as_params: ``True`` when ``-G`` moves the body to the query
    :param form_fields: multipart form fragments from ``-F`` / ``--form``
    :param data_file_refs: filenames whose content forms the body (``-d @file``)
    """

    method: str = _DEFAULT_METHOD
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    data_parts: list[str] = field(default_factory=list)
    username: str | None = None
    password: str | None = None
    send_data_as_params: bool = False
    form_fields: list[str] = field(default_factory=list)
    data_file_refs: list[str] = field(default_factory=list)

    @property
    def has_body(self) -> bool:
        """Whether the request carries any body, form or file payload."""
        return bool(self.data_parts or self.form_fields or self.data_file_refs)

    @property
    def body(self) -> str:
        """Return the body fragments joined the way ``curl`` sends them."""
        return "&".join(self.data_parts)

    def header_value(self, name: str) -> str | None:
        """Return a header's value by case-insensitive *name*, or ``None``."""
        lowered = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lowered:
                return value
        return None


# Flags that take a value and how each value is applied to the request.
# Keeping this as data (not a branch per flag) keeps parse_curl's complexity low.
_VALUE_FLAGS: dict[str, str] = {
    "-X": "method", "--request": "method",
    "-H": "header", "--header": "header",
    # ``-d`` and friends honour curl's ``@file`` syntax; ``--data-raw`` /
    # ``--data-urlencode`` are always literal (a leading ``@`` is data, not a file).
    "-d": "data_file", "--data": "data_file",
    "--data-ascii": "data_file", "--data-binary": "data_file",
    "--data-raw": "data", "--data-urlencode": "data_urlencode",
    "--json": "json_flag",
    "-F": "form", "--form": "form", "--form-string": "form",
    "-u": "user", "--user": "user",
    "-b": "cookie", "--cookie": "cookie",
    "-A": "user_agent", "--user-agent": "user_agent",
    "-e": "referer", "--referer": "referer",
    "--url": "url",
}

# Value-less flags that still change behaviour.
_GET_FLAGS = frozenset({"-G", "--get"})

# Value-less flags to accept and skip (they do not affect the generated request).
_VALUELESS_FLAGS = frozenset({
    "--compressed", "-L", "--location", "-k", "--insecure", "-s", "--silent",
    "-S", "--show-error", "-q", "--disable",
    "-v", "--verbose", "-i", "--include", "-I", "--head", "-f", "--fail",
    "--fail-with-body", "-g", "--globoff", "-O", "--remote-name",
    "-J", "--remote-header-name", "-#", "--progress-bar", "-N", "--no-buffer",
    "-j", "--junk-session-cookies", "--no-keepalive", "--no-progress-meter",
    "--http0.9", "--http1.0", "--http1.1", "--http2", "--http2-prior-knowledge",
    "--http3", "-0", "--tlsv1", "--tlsv1.0", "--tlsv1.1", "--tlsv1.2", "--tlsv1.3",
    "--raw", "--path-as-is", "-a", "--append", "--anyauth", "--basic", "--digest",
    "--ntlm", "--negotiate", "-B", "--use-ascii", "--no-alpn", "--no-npn",
    "--tcp-nodelay", "--tr-encoding", "-4", "-6", "-Z", "--parallel",
})

# Flags that take a value we do not use; the value is consumed so it cannot be
# mistaken for the URL (this is what makes ``--max-time 30 https://x`` parse right).
_IGNORED_VALUE_FLAGS = frozenset({
    "-o", "--output", "--max-time", "-m", "--connect-timeout", "--retry",
    "--retry-delay", "--retry-max-time", "-w", "--write-out", "-x", "--proxy",
    "--proxy-user", "-U", "--cacert", "--capath", "-E", "--cert", "--key",
    "--cert-type", "--key-type", "--pass", "-T", "--upload-file", "--limit-rate",
    "-r", "--range", "-c", "--cookie-jar", "--resolve", "--interface",
    "--dns-servers", "--local-port", "--ciphers", "-y", "--speed-time",
    "-Y", "--speed-limit", "--keepalive-time", "--oauth2-bearer", "--aws-sigv4",
    "-C", "--continue-at", "-z", "--time-cond", "-D", "--dump-header",
    "-K", "--config",
})


def _short_flags(*tables: object) -> frozenset[str]:
    """Collect the single-dash, single-letter flags found in *tables*."""
    return frozenset(
        flag for table in tables for flag in table
        if len(flag) == 2 and flag[0] == "-" and flag[1] != "-"
    )


# Short flags derived from the tables above so a bundled cluster like
# ``-sXPOST`` can split into ``-s`` and ``-X`` + ``POST`` without a second list.
_SHORT_VALUE_FLAGS = _short_flags(_VALUE_FLAGS, _IGNORED_VALUE_FLAGS)
_SHORT_VALUELESS_FLAGS = _short_flags(_VALUELESS_FLAGS, _GET_FLAGS)


def _is_short_flag_cluster(token: str) -> bool:
    """Whether *token* is a single-dash flag bundling more than one character."""
    return len(token) > 2 and token[0] == "-" and token[1] != "-"


def _expand_short_flag_cluster(token: str) -> list[str] | None:
    """Split a bundled short-flag token into canonical tokens.

    ``-sXPOST`` becomes ``["-s", "-X", "POST"]`` and ``-fsSL`` becomes
    ``["-f", "-s", "-S", "-L"]``. A value-taking flag ends the cluster: anything
    glued after it is that flag's value. Returns ``None`` when an unknown short
    flag is met, so the caller keeps the original token untouched.
    """
    expanded: list[str] = []
    body = token[1:]
    for position, letter in enumerate(body):
        flag = f"-{letter}"
        if flag in _SHORT_VALUE_FLAGS:
            expanded.append(flag)
            attached = body[position + 1:]
            if attached:  # value glued to the flag, e.g. the POST in -XPOST
                expanded.append(attached)
            return expanded
        if flag not in _SHORT_VALUELESS_FLAGS:
            return None  # an unknown short flag: do not rewrite the cluster
        expanded.append(flag)
    return expanded


def _expand_short_flags(tokens: list[str]) -> list[str]:
    """Expand bundled/attached short-flag tokens; pass everything else through."""
    expanded: list[str] = []
    for token in tokens:
        cluster = _expand_short_flag_cluster(token) if _is_short_flag_cluster(token) else None
        expanded.extend(cluster if cluster is not None else [token])
    return expanded


def _normalise_command(command: str) -> str:
    """Strip continuations so a multi-line pasted command tokenises as one."""
    return _LINE_CONTINUATION_RE.sub(" ", command.strip())


def _tokenize(command: str) -> list[str]:
    """Split *command* into shell tokens, raising on unbalanced quotes."""
    try:
        return shlex.split(command, posix=True)
    except ValueError as error:
        pybreeze_logger.error(malformed_curl_command_error)
        raise CurlParseException(malformed_curl_command_error) from error


def _apply_header(request: CurlRequest, raw_header: str) -> None:
    """Record a ``Name: Value`` header, ignoring malformed fragments."""
    name, separator, value = raw_header.partition(":")
    if separator:
        request.headers[name.strip()] = value.strip()


def _urlencode_data_part(value: str) -> str:
    """URL-encode a ``--data-urlencode`` fragment the way curl does.

    ``name=content`` keeps ``name`` literal and encodes ``content``; ``=content``
    or a bare ``content`` encodes the whole thing. ``@file`` / ``name@file`` forms
    read a file, which we cannot do here, so they are left literal.

    :param value: the raw ``--data-urlencode`` fragment
    :return: the fragment with its content URL-encoded
    """
    name, separator, content = value.partition("=")
    if separator:
        return f"{name}={quote(content, safe='')}" if name else quote(content, safe="")
    if "@" in value:
        return value  # a file form (@file / name@file) — cannot read it here
    return quote(value, safe="")


def _apply_value_flag(request: CurlRequest, kind: str, value: str) -> None:
    """Apply one value-taking flag to *request* according to its *kind*."""
    if kind == "method":
        request.method = value.upper()
    elif kind == "header":
        _apply_header(request, value)
    elif kind == "data":
        request.data_parts.append(value)
    elif kind == "data_urlencode":
        request.data_parts.append(_urlencode_data_part(value))
    elif kind == "data_file":
        if value.startswith("@"):
            request.data_file_refs.append(value[1:])
        else:
            request.data_parts.append(value)
    elif kind == "json_flag":
        # curl --json is shorthand for --data + JSON Content-Type and Accept.
        request.data_parts.append(value)
        request.headers.setdefault("Content-Type", "application/json")
        request.headers.setdefault("Accept", "application/json")
    elif kind == "form":
        request.form_fields.append(value)
    elif kind == "cookie":
        request.headers.setdefault("Cookie", value)
    elif kind == "user_agent":
        request.headers.setdefault("User-Agent", value)
    elif kind == "referer":
        request.headers.setdefault("Referer", value)
    elif kind == "url":
        request.url = value
    elif kind == "user":
        request.username, _sep, request.password = value.partition(":")


def _consume_tokens(tokens: list[str], request: CurlRequest) -> None:
    """Walk *tokens*, filling *request*; positional tokens become the URL.

    Value-taking flags consume their following token, so a flag's value (like the
    ``30`` in ``--max-time 30``) is never mistaken for the URL.
    """
    index = 0
    while index < len(tokens):
        token = tokens[index]
        kind = _VALUE_FLAGS.get(token)
        if kind is not None:
            index += 1
            if index < len(tokens):
                _apply_value_flag(request, kind, tokens[index])
        elif token in _IGNORED_VALUE_FLAGS:
            index += 1  # consume and discard the value
        elif token in _GET_FLAGS:
            request.send_data_as_params = True
        elif token in _VALUELESS_FLAGS:
            pass  # a known valueless flag: nothing to do
        elif not token.startswith("-") and not request.url:
            request.url = token
        # An unknown flag (starts with '-') is treated as valueless and skipped.
        index += 1


def _finalise_method(request: CurlRequest) -> None:
    """Infer the method and move the body to the query when ``-G`` was given."""
    if request.method == _DEFAULT_METHOD and request.has_body and not request.send_data_as_params:
        request.method = _METHOD_WITH_BODY
    if request.send_data_as_params:
        request.params.update(parse_query_pairs(request.data_parts))
        request.data_parts = []


def parse_query_pairs(parts: list[str]) -> dict[str, str]:
    """Parse ``key=value`` fragments into a dict, ignoring pieces without ``=``.

    :param parts: body fragments such as ``["a=1", "b=2"]``
    :return: the parsed ``key -> value`` mapping
    """
    pairs: dict[str, str] = {}
    for part in parts:
        key, separator, value = part.partition("=")
        if separator:
            pairs[key] = value
    return pairs


def parse_curl(command: str) -> CurlRequest:
    """Parse a ``curl`` command string into a :class:`CurlRequest`.

    :param command: the full command, e.g. ``curl -X POST https://api/x -d '...'``
    :return: the structured request
    :raises CurlParseException: when the command is empty, is not a curl command,
        or cannot be tokenised (for example, unbalanced quotes)
    """
    normalised = _normalise_command(command)
    if not normalised:
        pybreeze_logger.error(empty_curl_command_error)
        raise CurlParseException(empty_curl_command_error)

    tokens = _tokenize(normalised)
    if not tokens or tokens[0] != "curl":
        pybreeze_logger.error(not_a_curl_command_error)
        raise CurlParseException(not_a_curl_command_error)

    request = CurlRequest()
    _consume_tokens(_expand_short_flags(tokens[1:]), request)
    _finalise_method(request)
    return request

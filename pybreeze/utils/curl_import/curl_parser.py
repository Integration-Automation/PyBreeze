"""Parse a ``curl`` command line into a structured request.

Copying a request as ``curl`` from browser dev tools is the fastest way to
capture an API call. This module turns that command string into a
:class:`CurlRequest`, so the rest of PyBreeze can format it, generate request
code, or drive an automation module without re-typing headers by hand.

The parser is pure logic (no Qt, no network) and never executes the command.
"""
from __future__ import annotations

import math
import re
import shlex
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, quote, urlencode

from pybreeze.utils.exception.exception_tags import (
    empty_curl_command_error,
    invalid_http_method_error,
    malformed_curl_command_error,
    not_a_curl_command_error,
)
from pybreeze.utils.exception.exceptions import CurlParseException
from pybreeze.utils.header_tools.header_merge import (
    add_header, set_default_header, stored_header_name
)
from pybreeze.utils.logging.logger import pybreeze_logger

# HTTP method used when none is given and no body is present
_DEFAULT_METHOD = "GET"
# HTTP method implied when a body is present but no method is given
_METHOD_WITH_BODY = "POST"
# Matches a backslash or caret line continuation before a newline
_LINE_CONTINUATION_RE = re.compile(r"[\\^]\r?\n")
# An HTTP method is a token (RFC 9110, section 5.6.2)
_METHOD_TOKEN_RE = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")


def http_method(value: str) -> str:
    """Return *value* as an upper-case HTTP method.

    Generated scripts put the method into code -- a function name, a comment --
    so anything that is not a token (a space, a newline, a parenthesis) is
    refused here rather than written into a script.

    :raises ValueError: when *value* is not an HTTP method
    """
    method = value.strip().upper()
    if not _METHOD_TOKEN_RE.fullmatch(method):
        raise ValueError(f"{invalid_http_method_error}: {value!r}")
    return method


@dataclass
class CurlRequest:
    """A structured HTTP request extracted from a ``curl`` command.

    :param method: HTTP method (upper-case), e.g. ``GET`` or ``POST``
    :param url: request URL, or an empty string when none was found
    :param headers: request headers as ``name -> value`` (names kept as written)
    :param params: query parameters from the URL and from ``-G`` / ``--data``
        pairs; a key given more than once maps to the list of its values
    :param data_parts: raw body fragments in the order they appeared
    :param username: basic-auth user, or ``None``
    :param password: basic-auth password, or ``None``
    :param send_data_as_params: ``True`` when ``-G`` moves the body to the query
    :param form_fields: multipart form fragments from ``-F`` / ``--form``, in
        curl's syntax: a value starting with ``@`` is a file to upload
    :param form_strings: multipart ``name=value`` fields taken literally, from
        ``--form-string`` or a recorded text field; ``@`` means nothing there
    :param data_file_refs: filenames whose content forms the body (``-d @file``)
    :param timeout: request timeout in seconds from ``--max-time`` / ``-m``, or
        ``None`` when the command sets none
    :param cookies: cookies parsed from ``-b`` / ``--cookie`` name=value pairs
    """

    method: str = _DEFAULT_METHOD
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str | list[str]] = field(default_factory=dict)
    data_parts: list[str] = field(default_factory=list)
    username: str | None = None
    password: str | None = None
    send_data_as_params: bool = False
    form_fields: list[str] = field(default_factory=list)
    form_strings: list[str] = field(default_factory=list)
    data_file_refs: list[str] = field(default_factory=list)
    timeout: str | None = None
    cookies: dict[str, str] = field(default_factory=dict)

    @property
    def has_form(self) -> bool:
        """Whether the request carries a multipart form."""
        return bool(self.form_fields or self.form_strings)

    @property
    def has_body(self) -> bool:
        """Whether the request carries any body, form or file payload."""
        return bool(self.data_parts or self.has_form or self.data_file_refs)

    @property
    def body(self) -> str:
        """Return the body fragments joined the way ``curl`` sends them."""
        return "&".join(self.data_parts)

    @property
    def full_url(self) -> str:
        """The URL with any collected query params reattached, as curl sends it.

        After parsing, a query string embedded in the URL is moved into
        :attr:`params`; this rebuilds the original address for consumers (such as
        the load-test template) that drive purely by URL.
        """
        if not self.params:
            return self.url
        joiner = "&" if "?" in self.url else "?"
        return f"{self.url}{joiner}{urlencode(self.params, doseq=True)}"

    def header_value(self, name: str) -> str | None:
        """Return a header's value by case-insensitive *name*, or ``None``."""
        stored = stored_header_name(self.headers, name)
        return None if stored is None else self.headers[stored]


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
    "-F": "form", "--form": "form", "--form-string": "form_string",
    "-u": "user", "--user": "user",
    "-b": "cookie", "--cookie": "cookie",
    "-A": "user_agent", "--user-agent": "user_agent",
    "-e": "referer", "--referer": "referer",
    "--url": "url",
    "-m": "timeout", "--max-time": "timeout",
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
    "-o", "--output", "--connect-timeout", "--retry",
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


# One escape inside bash's $'...' quoting
_ANSI_C_ESCAPE_RE = re.compile(
    r"\\(x[0-9a-fA-F]{1,2}|u[0-9a-fA-F]{1,4}|U[0-9a-fA-F]{1,8}|[0-7]{1,3}|.)", re.DOTALL)
# What the single-character escapes stand for
_ANSI_C_SIMPLE = {
    "n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b",
    "f": "\f", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?",
}


def _ansi_c_character(match: re.Match) -> str:
    """The character one ``$'...'`` escape stands for; an unknown one stays as written."""
    code = match.group(1)
    if code[0] in "xuU" and len(code) > 1:
        return chr(min(int(code[1:], 16), sys.maxunicode))
    if code[0] in "01234567":
        return chr(int(code, 8) & 0xFF)
    return _ANSI_C_SIMPLE.get(code, match.group(0))


def _ansi_c_end(command: str, start: int) -> int:
    """Index of the quote closing the ``$'...'`` whose body starts at *start*."""
    index = start
    while index < len(command):
        if command[index] == "\\":
            index += 2
            continue
        if command[index] == "'":
            return index
        index += 1
    pybreeze_logger.error(malformed_curl_command_error)
    raise CurlParseException(malformed_curl_command_error)


def _expand_ansi_c_quotes(command: str) -> str:
    """Rewrite bash ``$'...'`` strings as the plain quoted text they stand for.

    Copy as cURL (bash) in the browsers writes a body holding a newline or a
    quote as ``$'...'``, which ``shlex`` does not know: it left a ``$`` in
    front of the body, or refused an escaped quote as unbalanced. Only a ``$'``
    outside other quotes starts one, as in bash.
    """
    pieces: list[str] = []
    index = 0
    quote = ""
    while index < len(command):
        char = command[index]
        if quote:
            if char == quote:
                quote = ""
            elif char == "\\" and quote == '"':
                pieces.append(command[index:index + 2])
                index += 2
                continue
        elif char == "\\":
            pieces.append(command[index:index + 2])
            index += 2
            continue
        elif command.startswith("$'", index):
            end = _ansi_c_end(command, index + 2)
            pieces.append(shlex.quote(_ANSI_C_ESCAPE_RE.sub(_ansi_c_character, command[index + 2:end])))
            index = end + 1
            continue
        elif char in "'\"":
            quote = char
        pieces.append(char)
        index += 1
    return "".join(pieces)


def _tokenize(command: str) -> list[str]:
    """Split *command* into shell tokens, raising on unbalanced quotes."""
    try:
        return shlex.split(_expand_ansi_c_quotes(command), posix=True)
    except ValueError as error:
        pybreeze_logger.error(malformed_curl_command_error)
        raise CurlParseException(malformed_curl_command_error) from error


def _apply_header(request: CurlRequest, raw_header: str) -> None:
    """Record a ``Name: Value`` header, combining repeats of the same name.

    curl sends every ``-H`` it is given, so a repeated name is not a mistake: the
    receiver combines those field lines into one value, which is what the
    generated code should carry. Fragments with no colon or an empty name are
    ignored.
    """
    name, separator, value = raw_header.partition(":")
    name, value = name.strip(), value.strip()
    if not separator or not name:
        return
    add_header(request.headers, name, value)


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


def _apply_timeout(request: CurlRequest, value: str) -> None:
    """Record a numeric timeout (seconds); ignore a non-numeric value."""
    try:
        seconds = float(value)
    except ValueError:
        return
    # float() also takes "nan" and "inf", which would be written into the
    # script as an undefined name.
    if not math.isfinite(seconds):
        return
    request.timeout = value


def _apply_data_or_file(request: CurlRequest, value: str) -> None:
    """Record a ``-d`` value as an ``@file`` reference or an inline body part."""
    if value.startswith("@"):
        request.data_file_refs.append(value[1:])
    else:
        request.data_parts.append(value)


def _apply_cookie(request: CurlRequest, value: str) -> None:
    """Parse a ``-b`` cookie string into ``name=value`` pairs.

    ``curl -b 'a=1; b=2'`` yields inline cookies; a value with no ``=`` is a
    cookie *file* curl would read, which we keep as a ``Cookie`` header instead.
    """
    if "=" not in value:
        set_default_header(request.headers, "Cookie", value)
        return
    for segment in value.split(";"):
        name, separator, cookie_value = segment.strip().partition("=")
        if separator and name:
            request.cookies[name] = cookie_value


def _apply_method(request: CurlRequest, value: str) -> None:
    try:
        request.method = http_method(value)
    except ValueError as error:
        raise CurlParseException(str(error)) from None


def _apply_json_flag(request: CurlRequest, value: str) -> None:
    # curl --json is shorthand for --data + JSON Content-Type and Accept.
    request.data_parts.append(value)
    set_default_header(request.headers, "Content-Type", "application/json")
    set_default_header(request.headers, "Accept", "application/json")


def _apply_user(request: CurlRequest, value: str) -> None:
    request.username, _separator, request.password = value.partition(":")


def _set_url(request: CurlRequest, value: str) -> None:
    request.url = value


# What each kind of value-taking flag does to the request
_VALUE_FLAG_HANDLERS: dict[str, Callable[[CurlRequest, str], None]] = {
    "method": _apply_method,
    "header": _apply_header,
    "data": lambda request, value: request.data_parts.append(value),
    "data_urlencode": lambda request, value: request.data_parts.append(_urlencode_data_part(value)),
    "data_file": _apply_data_or_file,
    "json_flag": _apply_json_flag,
    "form": lambda request, value: request.form_fields.append(value),
    "form_string": lambda request, value: request.form_strings.append(value),
    "cookie": _apply_cookie,
    "user_agent": lambda request, value: set_default_header(request.headers, "User-Agent", value),
    "referer": lambda request, value: set_default_header(request.headers, "Referer", value),
    "url": _set_url,
    "timeout": _apply_timeout,
    "user": _apply_user,
}


def _apply_value_flag(request: CurlRequest, kind: str, value: str) -> None:
    """Apply one value-taking flag to *request* according to its *kind*."""
    handler = _VALUE_FLAG_HANDLERS.get(kind)
    if handler is not None:
        handler(request, value)


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
        # With -G, curl appends the data to the URL exactly as given, joined by
        # '&': each fragment is query text already, so it is split on '&' and
        # decoded here, or full_url would encode it a second time.
        for part in request.data_parts:
            for key, value in parse_qsl(part, keep_blank_values=True):
                add_query_value(request.params, key, value)
        request.data_parts = []


def add_query_value(params: dict[str, str | list[str]], key: str, value: str) -> None:
    """Add *value* under *key*, keeping the values already there.

    ``?id=1&id=2`` sends both; a plain dict kept only one of them. A key seen
    once maps to its value, a repeated one to the list of its values, which is
    what ``requests`` and ``urlencode(doseq=True)`` both expand back.
    """
    if key not in params:
        params[key] = value
        return
    existing = params[key]
    if isinstance(existing, list):
        existing.append(value)
    else:
        params[key] = [existing, value]


def _split_url_query(request: CurlRequest) -> None:
    """Move a query string embedded in the URL into ``params``.

    Browser "copy as cURL" keeps the query in the URL; splitting it out lets it
    show up alongside ``-G`` / ``-d`` query pairs, while
    :attr:`CurlRequest.full_url` can still rebuild the original address. Values
    are URL-decoded, and a key given more than once keeps every value.
    """
    base, separator, query = request.url.partition("?")
    if not separator:
        return
    request.url = base
    for key, value in parse_qsl(query, keep_blank_values=True):
        add_query_value(request.params, key, value)


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
    # The URL's own query first: curl appends -G data after it.
    _split_url_query(request)
    _finalise_method(request)
    return request

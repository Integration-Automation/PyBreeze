"""Bounded HTTP response reading helpers.

User-configured endpoints (AI code-review services, skill webhooks) are only
semi-trusted: a hostile or buggy server can return a multi-gigabyte body that
``requests`` would buffer entirely into memory. ``read_capped_text`` streams the
body and aborts once it crosses a size cap, and ``truncate_for_display`` keeps an
oversized body from being pasted whole into an error dialog.
"""
from __future__ import annotations

from email.message import Message

import requests

from pybreeze.utils.network.url_validation import UnsafeURLError

DEFAULT_MAX_RESPONSE_BYTES = 16 * 1024 * 1024  # 16 MB
DISPLAY_TRUNCATE_CHARS = 2000
_CHUNK_SIZE = 65536

# Seconds to wait for the TCP/TLS connection to establish. Use it as a literal
# tuple ``timeout=(CONNECT_TIMEOUT, read)`` at call sites so an unreachable
# endpoint fails fast — and so Bandit's B113 recognises the timeout (it does not
# follow a helper function, only literal/constant values).
CONNECT_TIMEOUT = 10


class ResponseTooLargeError(Exception):
    """Raised when a streamed response body exceeds the configured cap."""


def read_capped_text(
    response: requests.Response,
    *,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    default_encoding: str = "utf-8",
) -> str:
    """Read a streamed response body up to *max_bytes* and decode it to text.

    The request must be issued with ``stream=True`` so the body is read here
    under the cap instead of being buffered in full by ``requests``. Raises
    ``ResponseTooLargeError`` once the accumulated body exceeds *max_bytes*. The
    response is always closed before returning. The charset the response names
    in its ``Content-Type`` is used when Python knows it, and *default_encoding*
    otherwise: a server can name anything, and an unknown one would raise
    ``LookupError`` here.
    """
    total = 0
    chunks: list[bytes] = []
    try:
        for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ResponseTooLargeError(
                    f"Response body exceeds the {max_bytes}-byte limit."
                )
            chunks.append(chunk)
    finally:
        response.close()
    body = b"".join(chunks)
    try:
        return body.decode(named_charset(response) or default_encoding, "replace")
    except LookupError:
        return body.decode(default_encoding, "replace")


def named_charset(response: requests.Response) -> str | None:
    """The charset *response*'s ``Content-Type`` names, or ``None`` when it names none.

    Not ``response.encoding``: requests gives every ``text/*`` answer without
    a charset ISO-8859-1 (RFC 2616's old default), so a UTF-8 review sent as
    ``text/plain`` or ``text/markdown`` came out garbled.
    """
    content_type = (getattr(response, "headers", None) or {}).get("Content-Type", "")
    if not content_type:
        return None
    message = Message()
    message["Content-Type"] = content_type
    charset = message.get_param("charset")
    return charset.strip() if isinstance(charset, str) and charset.strip() else None


# What a failed request is called for the user, most specific first: a connect
# timeout is both a Timeout and a ConnectionError
_REQUEST_FAILURES: tuple[tuple[type[Exception], str], ...] = (
    (requests.Timeout, "the request timed out"),
    (requests.exceptions.SSLError, "the secure connection could not be made"),
    (requests.ConnectionError, "could not connect to the server"),
    (requests.TooManyRedirects, "too many redirects"),
    (requests.exceptions.InvalidURL, "the URL is not valid"),
    (requests.exceptions.MissingSchema, "the URL is not valid"),
    (requests.exceptions.InvalidSchema, "the URL is not valid"),
)


def describe_request_error(error: Exception) -> str:
    """Say what went wrong with a request, for the user, without its URL.

    A ``requests`` error's text quotes the URL, path and query included, and
    an API URL may carry a token: shown as it was, the panels displayed it.
    The size cap's and the SSRF check's own messages name no path or query
    and are kept.
    """
    if isinstance(error, (ResponseTooLargeError, UnsafeURLError)):
        return str(error)
    for kind, reason in _REQUEST_FAILURES:
        if isinstance(error, kind):
            return f"{reason} ({type(error).__name__})"
    return type(error).__name__


def succeeded(response) -> bool:
    """Whether *response* answered with a 2xx status.

    Not ``response.ok``: that is true for every status below 400, so a redirect
    -- which these requests do not follow -- would pass for an answer, usually
    an empty one.
    """
    return 200 <= response.status_code < 300


def truncate_for_display(text: str, limit: int = DISPLAY_TRUNCATE_CHARS) -> str:
    """Shorten *text* for safe embedding in an error message / dialog."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… [truncated, {len(text)} chars total]"

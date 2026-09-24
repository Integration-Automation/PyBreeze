"""Bounded HTTP response reading helpers.

User-configured endpoints (AI code-review services, skill webhooks) are only
semi-trusted: a hostile or buggy server can return a multi-gigabyte body that
``requests`` would buffer entirely into memory. ``read_capped_text`` streams the
body and aborts once it crosses a size cap, and ``truncate_for_display`` keeps an
oversized body from being pasted whole into an error dialog.
"""
from __future__ import annotations

import threading
import time
from email.message import Message

import requests

from pybreeze.utils.exception.exception_tags import (
    request_invalid_url_error,
    request_no_connection_error,
    request_timed_out_error,
    request_tls_failed_error,
    request_too_many_redirects_error,
    response_too_large_error,
)
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.network.url_validation import UnsafeURLError

DEFAULT_MAX_RESPONSE_BYTES = 16 * 1024 * 1024  # 16 MB
DISPLAY_TRUNCATE_CHARS = 2000
# The longest a whole answer may take to arrive. The read timeout bounds each
# wait for a chunk only: a server sending a byte every 25 s kept a request, and
# the panel's greyed-out Send, going for as long as it liked.
DEFAULT_MAX_READ_SECONDS = 300
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
    max_seconds: float = DEFAULT_MAX_READ_SECONDS,
) -> str:
    """Read a streamed response body up to *max_bytes* and decode it to text.

    The request must be issued with ``stream=True`` so the body is read here
    under the cap instead of being buffered in full by ``requests``. Raises
    ``ResponseTooLargeError`` once the accumulated body exceeds *max_bytes*. The
    response is always closed before returning. The charset the response names
    in its ``Content-Type`` is used when Python knows it, and *default_encoding*
    otherwise: a server can name anything, and an unknown one would raise
    ``LookupError`` here. Raises ``requests.exceptions.ReadTimeout`` once the
    body has taken more than *max_seconds*: a watchdog shuts the connection
    down then, which ends a read that is still waiting. Checked only as each
    chunk arrived, a server sending a byte every 25 s held a single chunk's
    read for weeks, each byte restarting the read timeout.
    """
    total = 0
    chunks: list[bytes] = []
    deadline = time.monotonic() + max_seconds
    watchdog = _Watchdog(response, max_seconds)
    try:
        for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
            if watchdog.fired or time.monotonic() > deadline:
                break
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ResponseTooLargeError(response_too_large_error.format(limit=max_bytes))
            chunks.append(chunk)
    # What a read cut off by the watchdog raises depends on where it was
    except (requests.exceptions.RequestException, OSError, ValueError, AttributeError):
        if not watchdog.fired:
            raise
    finally:
        watchdog.cancel()
        response.close()
    if watchdog.fired or time.monotonic() > deadline:
        raise requests.exceptions.ReadTimeout(f"The response took more than {max_seconds:g} seconds.")
    body = b"".join(chunks)
    try:
        return body.decode(named_charset(response) or default_encoding, "replace")
    except LookupError:
        return body.decode(default_encoding, "replace")


class _Watchdog:
    """Shuts *response*'s connection down after *seconds*, unless cancelled first."""

    def __init__(self, response: requests.Response, seconds: float) -> None:
        self._response = response
        self._lock = threading.Lock()
        self._cancelled = False
        self.fired = False
        self._timer = threading.Timer(seconds, self._fire)
        self._timer.daemon = True
        self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            if self._cancelled:
                return
            self.fired = True
        # urllib3 2.3+: ends a read blocked on another thread. Closing is the
        # fallback: it ends the next read, if not the one waiting now
        shutdown = getattr(self._response.raw, "shutdown", None)
        try:
            (shutdown or self._response.close)()
        except (OSError, AttributeError) as error:
            pybreeze_logger.debug("Response watchdog could not shut the connection down: %r", error)

    def cancel(self) -> None:
        """Stop the watchdog; after this it does nothing."""
        with self._lock:
            self._cancelled = True
        self._timer.cancel()


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
    (requests.Timeout, request_timed_out_error),
    (requests.exceptions.SSLError, request_tls_failed_error),
    (requests.ConnectionError, request_no_connection_error),
    (requests.TooManyRedirects, request_too_many_redirects_error),
    (requests.exceptions.InvalidURL, request_invalid_url_error),
    (requests.exceptions.MissingSchema, request_invalid_url_error),
    (requests.exceptions.InvalidSchema, request_invalid_url_error),
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

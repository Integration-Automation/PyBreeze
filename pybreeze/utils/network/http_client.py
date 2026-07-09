"""Bounded HTTP response reading helpers.

User-configured endpoints (AI code-review services, skill webhooks) are only
semi-trusted: a hostile or buggy server can return a multi-gigabyte body that
``requests`` would buffer entirely into memory. ``read_capped_text`` streams the
body and aborts once it crosses a size cap, and ``truncate_for_display`` keeps an
oversized body from being pasted whole into an error dialog.
"""
from __future__ import annotations

import requests

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
    response is always closed before returning.
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
    encoding = response.encoding or default_encoding
    return b"".join(chunks).decode(encoding, "replace")


def truncate_for_display(text: str, limit: int = DISPLAY_TRUNCATE_CHARS) -> str:
    """Shorten *text* for safe embedding in an error message / dialog."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… [truncated, {len(text)} chars total]"

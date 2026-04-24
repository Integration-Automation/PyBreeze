"""Network utilities for the diagram editor with security hardening.

Security measures:
  - Only ``http`` and ``https`` schemes are allowed (blocks ``file://``, ``ftp://``, etc.)
  - Resolved IPs are checked against private/loopback ranges to prevent SSRF
  - Downloads are capped at ``MAX_DOWNLOAD_BYTES`` to prevent memory exhaustion
  - Connection timeout is enforced
"""
from __future__ import annotations

from urllib.request import Request, urlopen

from pybreeze.utils.network.url_validation import UnsafeURLError, validate_url

MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
TIMEOUT_SECONDS = 15


class ImageDownloadError(Exception):
    pass


def _validate_url(url: str) -> str:
    """Validate URL scheme and resolve hostname to block private/loopback IPs."""
    try:
        return validate_url(url)
    except UnsafeURLError as exc:
        raise ImageDownloadError(str(exc)) from exc


def safe_download_image(url: str) -> bytes:
    """Download image data from *url* with security and size guards.

    Raises ``ImageDownloadError`` on validation failure or oversized response.
    """
    url = _validate_url(url)

    req = Request(url, headers={"User-Agent": "PyBreeze-DiagramEditor/1.0"})
    resp = urlopen(req, timeout=TIMEOUT_SECONDS)  # nosec B310 # noqa: S310 — URL validated above by _validate_url

    # Check Content-Length header if available
    content_length = resp.headers.get("Content-Length")
    if content_length is not None and int(content_length) > MAX_DOWNLOAD_BYTES:
        raise ImageDownloadError(
            f"Image too large ({int(content_length)} bytes, max {MAX_DOWNLOAD_BYTES})."
        )

    # Read with size limit
    data = resp.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ImageDownloadError(
            f"Image exceeds {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB limit."
        )

    return data

"""Network utilities for the diagram editor with security hardening.

Security measures:
  - Only ``http`` and ``https`` schemes are allowed (blocks ``file://``, ``ftp://``, etc.)
  - Resolved IPs are checked against private/loopback ranges to prevent SSRF
  - Downloads are capped at ``MAX_DOWNLOAD_BYTES`` to prevent memory exhaustion
  - Connection timeout is enforced
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
TIMEOUT_SECONDS = 15
_ALLOWED_SCHEMES = {"http", "https"}


class ImageDownloadError(Exception):
    pass


def _validate_url(url: str) -> str:
    """Validate URL scheme and resolve hostname to block private/loopback IPs."""
    parsed = urlparse(url)

    # Scheme check
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ImageDownloadError(
            f"Scheme '{parsed.scheme}' is not allowed. Use http or https."
        )

    # Hostname check
    hostname = parsed.hostname
    if not hostname:
        raise ImageDownloadError("URL has no hostname.")

    # Resolve and check for private/loopback IPs (SSRF prevention)
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ImageDownloadError(f"Cannot resolve hostname '{hostname}': {e}") from e

    for family, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ImageDownloadError(
                f"Access to private/internal address {ip} is blocked."
            )

    return url


def safe_download_image(url: str) -> bytes:
    """Download image data from *url* with security and size guards.

    Raises ``ImageDownloadError`` on validation failure or oversized response.
    """
    url = _validate_url(url)

    req = Request(url, headers={"User-Agent": "PyBreeze-DiagramEditor/1.0"})
    resp = urlopen(req, timeout=TIMEOUT_SECONDS)  # noqa: S310 — URL validated above

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

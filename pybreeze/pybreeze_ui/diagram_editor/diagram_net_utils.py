"""Network utilities for the diagram editor with security hardening.

Security measures:
  - Only ``http`` and ``https`` schemes are allowed (blocks ``file://``, ``ftp://``, etc.)
  - Resolved IPs are checked against private/loopback ranges to prevent SSRF
  - Downloads are capped at ``MAX_DOWNLOAD_BYTES`` to prevent memory exhaustion
  - Connection timeout is enforced
"""
from __future__ import annotations

from urllib.request import HTTPRedirectHandler, Request, build_opener

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


class _ValidatingRedirectHandler(HTTPRedirectHandler):
    """Re-validate every redirect hop to prevent redirect-based SSRF.

    ``urlopen`` follows 3xx redirects by default; without this the initial URL
    could be a public host that 302-redirects to an internal address (e.g. the
    cloud metadata service). Each redirect target is run through the same SSRF
    validation before the request is allowed to proceed.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = build_opener(_ValidatingRedirectHandler())


def _parse_content_length(raw: str | None) -> int | None:
    """Return a non-negative ``Content-Length``, or ``None`` if absent/malformed.

    A hostile or buggy server can send a non-numeric or negative header; the
    real cap is still enforced by the bounded ``read`` below, so an unparseable
    header is treated as "unknown" rather than crashing with ``ValueError``.
    """
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def _is_text_content_type(content_type: str) -> bool:
    """True for a declared ``text/*`` response (e.g. an HTML error page).

    Only obvious text types are rejected so an image served as a generic binary
    type (``application/octet-stream``) or with no header still passes through to
    the pixmap validation.
    """
    return content_type.split(";")[0].strip().lower().startswith("text/")


def safe_download_image(url: str) -> bytes:
    """Download image data from *url* with security and size guards.

    Raises ``ImageDownloadError`` on validation failure or oversized response.
    """
    url = _validate_url(url)

    req = Request(url, headers={"User-Agent": "PyBreeze-DiagramEditor/1.0"})
    with _OPENER.open(req, timeout=TIMEOUT_SECONDS) as resp:  # nosec B310 # noqa: S310 — URL + redirects validated by _ValidatingRedirectHandler
        content_type = resp.headers.get("Content-Type", "")
        if _is_text_content_type(content_type):
            raise ImageDownloadError(
                f"Expected an image but the server returned '{content_type.strip()}'."
            )
        declared_length = _parse_content_length(resp.headers.get("Content-Length"))
        if declared_length is not None and declared_length > MAX_DOWNLOAD_BYTES:
            raise ImageDownloadError(
                f"Image too large ({declared_length} bytes, max {MAX_DOWNLOAD_BYTES})."
            )
        # Read one byte past the cap so an undersized/absent header can't smuggle
        # an oversized body past the check.
        data = resp.read(MAX_DOWNLOAD_BYTES + 1)

    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ImageDownloadError(
            f"Image exceeds {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB limit."
        )

    return data

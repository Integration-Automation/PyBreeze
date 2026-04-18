from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsafeURLError(Exception):
    """Raised when a URL fails security validation."""


def validate_url(url: str) -> str:
    """Validate a user-supplied URL against SSRF rules.

    Checks:
      1. Scheme must be ``http`` or ``https``
      2. Hostname must be present
      3. Resolved IP must not be private, loopback, link-local or reserved

    Returns the original *url* on success; raises ``UnsafeURLError`` on failure.
    """
    parsed = urlparse(url)

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(
            f"Scheme '{parsed.scheme}' is not allowed. Use http or https."
        )

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL has no hostname.")

    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Cannot resolve hostname '{hostname}': {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise UnsafeURLError(
                f"Access to private/internal address {ip} is blocked."
            )

    return url

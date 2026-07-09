from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})

# RFC 6598 shared address space (Carrier-Grade NAT). Not covered by
# ``is_private`` / ``is_reserved`` yet routinely abused for SSRF in cloud
# environments, so it is blocked explicitly.
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

# RFC 6052 NAT64 well-known prefix. The trailing 32 bits embed an IPv4 target
# that a NAT64 gateway routes to, so it must be decoded and re-checked.
_NAT64_NETWORK = ipaddress.ip_network("64:ff9b::/96")


class UnsafeURLError(Exception):
    """Raised when a URL fails security validation."""


def _embedded_ipv4(ip: ipaddress.IPv6Address) -> list[ipaddress.IPv4Address]:
    """Return any IPv4 addresses tunnelled inside an IPv6 transition form.

    Dual-stack and translated networks route these wrappers to the underlying
    IPv4 endpoint, so an attacker can reach a blocked IPv4 (e.g. the cloud
    metadata service) by wrapping it as IPv4-mapped, 6to4, Teredo or NAT64.
    Each embedded address is returned so the caller can re-validate it.
    """
    embedded: list[ipaddress.IPv4Address] = []
    for candidate in (ip.ipv4_mapped, ip.sixtofour):
        if candidate is not None:
            embedded.append(candidate)
    teredo = ip.teredo
    if teredo is not None:
        embedded.append(teredo[1])
    if ip in _NAT64_NETWORK:
        embedded.append(ipaddress.ip_address(int(ip) & 0xFFFFFFFF))
    return embedded


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return ``True`` when *ip* (or an IPv4 it tunnels to) is non-public."""
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return True
    if isinstance(ip, ipaddress.IPv4Address):
        return ip in _CGNAT_NETWORK
    return any(_is_blocked_ip(embedded) for embedded in _embedded_ipv4(ip))


def validate_url(url: str) -> str:
    """Validate a user-supplied URL against SSRF rules.

    Checks:
      1. Scheme must be ``http`` or ``https``
      2. Hostname must be present
      3. Every resolved IP must be a public address. Private, loopback,
         link-local, reserved, multicast, unspecified and Carrier-Grade NAT
         ranges are blocked, as are IPv6 transition forms (IPv4-mapped, 6to4,
         Teredo, NAT64) that tunnel to a blocked IPv4 endpoint.

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

    for *_unused, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_blocked_ip(ip):
            raise UnsafeURLError(
                f"Access to non-public address {ip} is blocked."
            )

    return url

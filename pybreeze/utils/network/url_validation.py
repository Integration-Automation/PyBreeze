from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from urllib3.exceptions import LocationParseError
from urllib3.util import parse_url

from pybreeze.utils.exception.exception_tags import (
    address_not_public_error,
    hostname_unresolved_error,
    hostname_without_address_error,
    url_ambiguous_host_error,
    url_no_hostname_error,
    url_scheme_not_allowed_error,
    url_unparsable_error,
    url_unsafe_characters_error,
)

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
    # fec0::/10 site-local: deprecated, yet still routed inside some networks,
    # and neither is_private nor is_global says so
    if ip.is_site_local:
        return True
    return any(_is_blocked_ip(embedded) for embedded in _embedded_ipv4(ip))


def _check_one_reading(url: str) -> None:
    """Refuse a URL whose host ``urlparse`` and ``urllib3`` would read differently.

    The check below reads the host with ``urlparse``; ``requests`` connects to
    the host ``urllib3`` reads. They disagree over a backslash:
    ``http://127.0.0.1\\@example.com/`` is ``example.com`` to the first, which
    passed, and ``127.0.0.1`` to the second, which was then connected to.
    Whitespace and control characters are refused for the same reason, and the
    two readings of the host are compared whatever the URL holds.
    """
    if any(character == "\\" or character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
           for character in url):
        raise UnsafeURLError(url_unsafe_characters_error)
    # Not the parsers' messages: they quote the whole URL, which may hold a token
    try:
        connected_host = (parse_url(url).host or "").strip("[]").lower()
    except LocationParseError:
        raise UnsafeURLError(url_unparsable_error) from None
    try:
        checked_host = (urlparse(url).hostname or "").lower()
    except ValueError:
        raise UnsafeURLError(url_unparsable_error) from None
    if _as_ascii(connected_host) != _as_ascii(checked_host):
        raise UnsafeURLError(url_ambiguous_host_error)


def _as_ascii(host: str) -> str:
    """*host* as it goes on the wire: urllib3 IDNA-encodes a Unicode name, urlparse does not.

    Encoded the way urllib3 encodes it (IDNA 2008 through the ``idna``
    package). Python's own ``idna`` codec is IDNA 2003, which maps ``ß`` to
    ``ss``: ``straße.de`` became ``strasse.de``, another domain, so a valid
    name was refused as ambiguous and the check resolved a name it would not
    connect to. A name that cannot be encoded is returned as it is, and then
    fails the comparison or the lookup.
    """
    if host.isascii():
        return host.lower()
    try:
        import idna
        return idna.encode(host.lower(), strict=True, std3_rules=True).decode("ascii")
    except (ImportError, UnicodeError, ValueError):
        # idna.IDNAError is a UnicodeError
        return host


def validate_url(url: str) -> str:
    """Validate a user-supplied URL against SSRF rules.

    Checks:
      1. Scheme must be ``http`` or ``https``
      2. Hostname must be present
      3. Every resolved IP must be a public address. Private, loopback,
         link-local, reserved, multicast, unspecified, IPv6 site-local and
         Carrier-Grade NAT ranges are blocked, as are IPv6 transition forms
         (IPv4-mapped, 6to4, Teredo, NAT64) that tunnel to a blocked IPv4
         endpoint.

    The host checked must be the host connected to, so a URL the parsers can
    read two ways is refused before anything else: see ``_check_one_reading``.

    Returns the original *url* on success; raises ``UnsafeURLError`` on failure.
    """
    _check_one_reading(url)
    parsed = urlparse(url)

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(url_scheme_not_allowed_error.format(scheme=parsed.scheme))

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError(url_no_hostname_error)

    # The name urllib3 will look up, not Python's reading of a Unicode one
    public_address(_as_ascii(hostname))
    return url


def public_address(hostname: str) -> str:
    """The first address :func:`public_addresses` returns for *hostname*."""
    return public_addresses(hostname)[0]


def public_addresses(hostname: str) -> list[str]:
    """Resolve *hostname* and return the addresses to connect to, if every address it has is public.

    In the order the resolver gave them, each once. A connection tries them in
    turn, as a plain one would: dialling only the first, a host with a broken
    IPv6 route (common behind a VPN) or a first A record that is down failed
    though another address would have answered.

    ``validate_url`` checks with this, and the connections in ``public_http``
    call it again as they connect and connect to the address it returns, so a
    name that answers differently the second time (DNS rebinding) is checked
    on the answer actually used.

    Raises ``UnsafeURLError`` when the name does not resolve or any of its
    addresses is blocked.
    """
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        # UnicodeError: the name cannot even be encoded for a lookup (a label
        # over 63 characters, or an empty one). Callers catch UnsafeURLError, so
        # anything else here would escape into a Qt slot.
        raise UnsafeURLError(hostname_unresolved_error.format(hostname=hostname, detail=exc)) from exc
    if not infos:
        raise UnsafeURLError(hostname_without_address_error.format(hostname=hostname))

    addresses: list[str] = []
    for *_unused, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_blocked_ip(ip):
            raise UnsafeURLError(address_not_public_error.format(address=ip))
        if sockaddr[0] not in addresses:
            addresses.append(sockaddr[0])
    return addresses

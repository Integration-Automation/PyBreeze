"""HTTP connections that connect only to the address they have just checked.

``validate_url`` resolves the host and checks every address, then the request
resolves it again to connect. A name whose answer changes between the two
(DNS rebinding: a short TTL, public the first time, private the second) passed
the check and reached the private address. The connections here resolve and
check once more as they connect, and connect to that address; the name stays
the connection's host, so TLS still checks the certificate against it (SNI)
and the ``Host`` header still carries it.

Only direct connections are pinned. Through a proxy it is the proxy that
resolves and connects, and the connection made here is to the proxy, which may
well be on the local network.
"""
from __future__ import annotations

import http.client
import socket
import urllib.request
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NewConnectionError

from pybreeze.utils.network.url_validation import UnsafeURLError, public_addresses


class AddressNotPublicError(OSError):
    """The host resolved to a blocked address when the connection was made."""


class _PinnedConnectionMixin:
    """A urllib3 connection that opens its socket to an address ``public_addresses`` returns.

    urllib3 connects to ``_dns_host`` and takes ``host`` (TLS server name,
    ``Host`` header) from it. It holds a checked address only while the
    socket is opened, and the name again once it is. The checked addresses
    are tried in turn; the last failure is raised when none answers.
    """

    _dns_host: str

    def _new_conn(self) -> socket.socket:
        name = self._dns_host
        try:
            addresses = public_addresses(name)
        except UnsafeURLError as error:
            raise NewConnectionError(self, f"Refused: {error}") from None
        failure: Exception | None = None
        try:
            for address in addresses:
                self._dns_host = address
                try:
                    return super()._new_conn()  # type: ignore[misc]
                except (NewConnectionError, ConnectTimeoutError) as error:
                    failure = error
        finally:
            self._dns_host = name
        raise failure  # type: ignore[misc]  # public_addresses never returns none


class _PinnedHTTPConnection(_PinnedConnectionMixin, HTTPConnection):
    pass


class _PinnedHTTPSConnection(_PinnedConnectionMixin, HTTPSConnection):
    pass


class _PinnedHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _PinnedHTTPConnection


class _PinnedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _PinnedHTTPSConnection


class PublicAddressAdapter(HTTPAdapter):
    """A ``requests`` adapter whose direct connections go only to checked public addresses."""

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        super().init_poolmanager(*args, **kwargs)
        # A new dict: the pool manager's default is urllib3's module-wide one
        self.poolmanager.pool_classes_by_scheme = {
            "http": _PinnedHTTPConnectionPool,
            "https": _PinnedHTTPSConnectionPool,
        }


def public_session() -> requests.Session:
    """A ``requests.Session`` for user-supplied URLs; still pass each URL through ``validate_url``."""
    session = requests.Session()
    adapter = PublicAddressAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _create_public_connection(address: tuple[str, int], *args: Any, **kwargs: Any) -> socket.socket:
    """``socket.create_connection`` to a checked address of *address*'s host, each tried in turn."""
    host, port = address
    try:
        checked = public_addresses(host)
    except UnsafeURLError as error:
        raise AddressNotPublicError(str(error)) from None
    failure: OSError | None = None
    for candidate in checked:
        try:
            return socket.create_connection((candidate, port), *args, **kwargs)
        except OSError as error:
            failure = error
    raise failure  # type: ignore[misc]  # public_addresses never returns none


class _PinnedHTTPClientConnection(http.client.HTTPConnection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = _create_public_connection


class _PinnedHTTPSClientConnection(http.client.HTTPSConnection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = _create_public_connection


def _through_a_proxy(request: urllib.request.Request) -> bool:
    """True when ``ProxyHandler`` pointed *request* at a proxy instead of its own host."""
    return request.host != urllib.request.Request(request.full_url).host


class PublicHTTPHandler(urllib.request.HTTPHandler):
    """``urllib``'s HTTP handler, connecting directly only to checked public addresses."""

    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        if _through_a_proxy(req):
            return super().http_open(req)
        return self.do_open(_PinnedHTTPClientConnection, req)


class PublicHTTPSHandler(urllib.request.HTTPSHandler):
    """``urllib``'s HTTPS handler, connecting directly only to checked public addresses."""

    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        if _through_a_proxy(req):
            return super().https_open(req)
        return self.do_open(_PinnedHTTPSClientConnection, req, context=self._context)

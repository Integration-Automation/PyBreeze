"""The address a request connects to is the address that was checked.

``validate_url`` resolved the name and the request resolved it again. A name
that answered a public address the first time and a private one the second
(DNS rebinding) passed the check and reached the private address.
"""
from __future__ import annotations

import socket
import ssl
import threading
import urllib.error
import urllib.request

import pytest
import requests

from pybreeze.pybreeze_ui.diagram_editor import diagram_net_utils
from pybreeze.utils.network import url_validation
from pybreeze.utils.network.public_http import (
    PublicHTTPHandler,
    PublicHTTPSHandler,
    public_session,
)
from pybreeze.utils.network.url_validation import validate_url

_PUBLIC_IP = "93.184.215.14"
_real_getaddrinfo = socket.getaddrinfo


def _answer(ip: str, port) -> list:
    # The port asked for: a connection made from this answer goes to it
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, int(port or 0)))]


@pytest.fixture()
def dns(monkeypatch):
    """Names ending in ``.test`` answer from a table; ``rebind.test`` public first, then loopback."""
    rebind_answers = [_PUBLIC_IP]
    table = {"service.test": "127.0.0.1"}

    def getaddrinfo(host, port=None, *args, **kwargs):
        if host == "rebind.test":
            return _answer(rebind_answers.pop(0) if rebind_answers else "127.0.0.1", port)
        if host in table:
            return _answer(table[host], port)
        return _real_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@pytest.fixture()
def loopback_allowed(monkeypatch):
    """Let the checks pass loopback, so a local server can stand in for a public one."""
    monkeypatch.setattr(url_validation, "_is_blocked_ip", lambda _ip: False)


def _complete(data: bytes) -> bool:
    """True once *data* holds a request's headers, or a whole TLS record (the ClientHello)."""
    if data.startswith(b"\x16") and len(data) >= 5:
        return len(data) >= 5 + int.from_bytes(data[3:5], "big")
    return b"\r\n\r\n" in data


class _Listener:
    """A loopback server that records the first request it gets, and what it answers."""

    def __init__(self, reply: bytes = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"):
        self.received: list[bytes] = []
        self._reply = reply
        self._socket = socket.socket()
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(1)
        self._socket.settimeout(5)
        self.port = self._socket.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        try:
            connection, _address = self._socket.accept()
        except OSError:
            return
        with connection:
            connection.settimeout(5)
            data = b""
            try:
                while not _complete(data):
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            except OSError:
                pass
            self.received.append(data)
            if not data.startswith(b"\x16"):
                connection.sendall(self._reply)

    def close(self) -> None:
        self._socket.close()
        self._thread.join(5)


def _session() -> requests.Session:
    """``public_session()``, ignoring any proxy this machine has set."""
    session = public_session()
    session.trust_env = False
    return session


@pytest.fixture()
def listener():
    server = _Listener()
    yield server
    server.close()


class TestRequestsSession:
    def test_a_name_that_rebinds_to_loopback_is_not_reached(self, dns, listener):
        url = f"http://rebind.test:{listener.port}/"
        validate_url(url)  # the first answer is public

        with _session() as session, pytest.raises(requests.ConnectionError) as raised:
            session.get(url, timeout=(3, 3), allow_redirects=False)

        assert "non-public address 127.0.0.1" in str(raised.value)
        listener.close()
        assert listener.received == []

    def test_it_connects_to_the_checked_address_under_the_name(self, dns, loopback_allowed, listener):
        with _session() as session:
            response = session.get(f"http://service.test:{listener.port}/path", timeout=(3, 3))

        assert response.text == "ok"
        request = listener.received[0]
        assert request.startswith(b"GET /path HTTP/1.1\r\n")
        assert f"Host: service.test:{listener.port}\r\n".encode() in request

    def test_tls_names_the_host_not_the_address(self, dns, loopback_allowed, listener):
        with _session() as session, pytest.raises(requests.RequestException):
            session.get(f"https://service.test:{listener.port}/", timeout=(3, 3))

        listener.close()
        # The ClientHello's server name
        assert b"service.test" in listener.received[0]

    def test_a_proxy_on_the_local_network_is_still_used(self, dns, listener):
        proxy = f"http://127.0.0.1:{listener.port}"

        with _session() as session:
            response = session.get(
                "http://rebind.test/", proxies={"http": proxy}, timeout=(3, 3))

        assert response.text == "ok"
        assert listener.received[0].startswith(b"GET http://rebind.test/ HTTP/1.1\r\n")


class TestUrllibOpener:
    """The opener the diagram editor downloads images with."""

    def test_a_name_that_rebinds_to_loopback_is_not_reached(self, dns, listener):
        url = f"http://rebind.test:{listener.port}/image.png"
        validate_url(url)

        with pytest.raises(urllib.error.URLError) as raised:
            diagram_net_utils._OPENER.open(url, timeout=3)

        assert "non-public address 127.0.0.1" in str(raised.value)
        listener.close()
        assert listener.received == []

    def test_a_rebinding_image_fails_as_a_download_error_the_canvas_catches(self, dns, listener):
        with pytest.raises(OSError):
            diagram_net_utils.safe_download_image(f"http://rebind.test:{listener.port}/image.png")

        listener.close()
        assert listener.received == []

    def test_it_connects_to_the_checked_address_under_the_name(self, dns, loopback_allowed, listener):
        with diagram_net_utils._OPENER.open(f"http://service.test:{listener.port}/i.png", timeout=3) as reply:
            assert reply.read() == b"ok"

        assert f"Host: service.test:{listener.port}\r\n".encode() in listener.received[0]

    def test_tls_names_the_host_not_the_address(self, dns, loopback_allowed, listener):
        opener = urllib.request.build_opener(PublicHTTPHandler(), PublicHTTPSHandler())

        with pytest.raises((urllib.error.URLError, ssl.SSLError, ConnectionError)):
            opener.open(f"https://service.test:{listener.port}/", timeout=3)

        listener.close()
        assert b"service.test" in listener.received[0]

    def test_a_proxy_on_the_local_network_is_still_used(self, dns, listener):
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": f"http://127.0.0.1:{listener.port}"}),
            PublicHTTPHandler(), PublicHTTPSHandler())

        with opener.open("http://rebind.test/i.png", timeout=3) as reply:
            assert reply.read() == b"ok"

        assert listener.received[0].startswith(b"GET http://rebind.test/i.png HTTP/1.1\r\n")


@pytest.fixture()
def two_addresses(monkeypatch):
    """``two.test`` answers an address nothing listens on first, then loopback."""
    def getaddrinfo(host, port=None, *args, **kwargs):
        if host == "two.test":
            return _answer("127.0.0.2", port) + _answer("127.0.0.1", port)
        return _real_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


class TestEveryCheckedAddressIsTried:
    """A plain connection tries each address; the pinned one dialled only the first."""

    def test_requests_goes_on_to_the_next_address(self, two_addresses, loopback_allowed, listener):
        with _session() as session:
            response = session.get(f"http://two.test:{listener.port}/", timeout=(3, 3))

        assert response.text == "ok"

    def test_urllib_goes_on_to_the_next_address(self, two_addresses, loopback_allowed, listener):
        opener = urllib.request.build_opener(PublicHTTPHandler())

        with opener.open(f"http://two.test:{listener.port}/", timeout=3) as response:
            assert response.read() == b"ok"

    def test_one_blocked_address_still_refuses_the_name(self, two_addresses, listener):
        with _session() as session, pytest.raises(requests.ConnectionError):
            session.get(f"http://two.test:{listener.port}/", timeout=(3, 3))
        listener.close()
        assert listener.received == []


class TestInternationalNames:
    def test_a_name_is_checked_as_it_will_be_looked_up(self, monkeypatch):
        # Python's idna codec made straße.de into strasse.de, another domain:
        # the URL was refused as ambiguous
        looked_up: list = []

        def getaddrinfo(host, port=None, *args, **kwargs):
            looked_up.append(host)
            return _answer(_PUBLIC_IP, port)

        monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)

        assert validate_url("http://straße.de/") == "http://straße.de/"
        assert looked_up == ["xn--strae-oqa.de"]

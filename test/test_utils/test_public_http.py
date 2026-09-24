"""The address a request connects to is the address that was checked.

``validate_url`` resolved the name and the request resolved it again. A name
that answered a public address the first time and a private one the second
(DNS rebinding) passed the check and reached the private address.
"""
from __future__ import annotations

import http.client
import socket
import ssl
import threading
import time
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

    def test_https_through_a_proxy_is_left_to_the_proxy(self, dns, listener):
        # The proxy connects to the name; there is no address here to pin
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": f"http://127.0.0.1:{listener.port}"}),
            PublicHTTPHandler(), PublicHTTPSHandler())

        with pytest.raises((urllib.error.URLError, ssl.SSLError, ConnectionError, http.client.HTTPException)):
            opener.open("https://rebind.test/i.png", timeout=3)

        listener.close()
        assert listener.received[0].startswith(b"CONNECT rebind.test:443 HTTP/1.")


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

    @staticmethod
    def _closed_port() -> int:
        """A loopback port nothing listens on any more."""
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        return port

    def test_requests_fails_when_no_address_answers(self, two_addresses, loopback_allowed):
        # After the last address the error is the connection's own, not a hang or a None raised
        with _session() as session, pytest.raises(requests.ConnectionError):
            session.get(f"http://two.test:{self._closed_port()}/", timeout=(3, 3))

    def test_urllib_fails_when_no_address_answers(self, two_addresses, loopback_allowed):
        opener = urllib.request.build_opener(PublicHTTPHandler())

        with pytest.raises(urllib.error.URLError):
            opener.open(f"http://two.test:{self._closed_port()}/", timeout=3)

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


class TestTheDeadlineItself:
    """What ``overall_deadline`` promises in the cases no request above runs into."""

    @staticmethod
    def _passed(seconds: float = 0.0):
        from pybreeze.utils.network.public_http import _Deadline

        deadline = _Deadline(seconds)
        limit = time.monotonic() + 5
        while not deadline.passed and time.monotonic() < limit:
            time.sleep(0.01)
        return deadline

    def test_a_block_that_ends_after_the_time_is_up_still_times_out(self):
        # A read cut off where no length was announced returns normally: the block must not
        from pybreeze.utils.network.public_http import overall_deadline

        with pytest.raises(requests.exceptions.ReadTimeout), overall_deadline(0.01):
            time.sleep(0.2)

    def test_a_socket_watched_after_the_time_is_up_is_shut_at_once(self):
        deadline = self._passed()
        mine, theirs = socket.socketpair()
        with mine, theirs:
            deadline.watch(mine)
            theirs.settimeout(2)
            assert theirs.recv(1) == b""  # the other end sees it closed
        deadline.end()

    def test_nothing_is_shut_once_the_request_is_over(self):
        from pybreeze.utils.network.public_http import _Deadline

        deadline = _Deadline(60)
        mine, theirs = socket.socketpair()
        with mine, theirs:
            deadline.watch(mine)
            deadline.end()
            deadline._pass()  # the timer firing late, after end()
            assert not deadline.passed
            mine.sendall(b"x")
            theirs.settimeout(2)
            assert theirs.recv(1) == b"x"

    def test_no_socket_is_nothing_to_watch(self):
        deadline = self._passed()
        deadline.watch(None)
        deadline.end()


class TestTheOverallDeadline:
    """A read timeout restarts with every byte; the deadline bounds the whole request."""

    @staticmethod
    def _trickling_headers(stop: threading.Event) -> tuple[socket.socket, threading.Thread]:
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)

        def serve() -> None:
            try:
                connection, _address = server.accept()
            except OSError:
                return
            with connection:
                connection.recv(65536)
                for byte in b"HTTP/1.1 200 OK\r\nX-Slow: " + b"y" * 1000:
                    if stop.wait(0.2):
                        return
                    try:
                        connection.sendall(bytes([byte]))
                    except OSError:
                        return

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        return server, thread

    def test_headers_sent_a_byte_at_a_time_are_cut_off(self, dns, loopback_allowed):
        import time

        from pybreeze.utils.network.public_http import overall_deadline

        stop = threading.Event()
        server, thread = self._trickling_headers(stop)
        started = time.monotonic()
        try:
            with pytest.raises(requests.exceptions.ReadTimeout), overall_deadline(1), _session() as session:
                session.get(f"http://service.test:{server.getsockname()[1]}/", timeout=(3, 3), stream=True)
            assert time.monotonic() - started < 4
        finally:
            stop.set()
            server.close()
            thread.join(5)

    def test_a_timely_answer_is_not_touched(self, dns, loopback_allowed, listener):
        from pybreeze.utils.network.public_http import overall_deadline

        with overall_deadline(5), _session() as session:
            response = session.get(f"http://service.test:{listener.port}/", timeout=(3, 3))

        assert response.text == "ok"

    def test_the_urllib_opener_is_cut_off_too(self, dns, loopback_allowed):
        # The diagram editor's image downloads: 15 s per wait, restarted by every byte
        import time

        from pybreeze.utils.network.public_http import overall_deadline

        stop = threading.Event()
        server, thread = self._trickling_headers(stop)
        opener = urllib.request.build_opener(PublicHTTPHandler())
        started = time.monotonic()
        try:
            with pytest.raises(requests.exceptions.ReadTimeout), overall_deadline(1):
                opener.open(f"http://service.test:{server.getsockname()[1]}/", timeout=3).read()
            assert time.monotonic() - started < 4
        finally:
            stop.set()
            server.close()
            thread.join(5)

    def test_a_body_cut_short_without_a_length_is_not_taken_as_whole(self, dns, loopback_allowed):
        # Shut down mid-body with no Content-Length, the read ends as if the body had
        import time

        from pybreeze.utils.network.public_http import overall_deadline

        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        stop = threading.Event()

        def serve() -> None:
            connection, _address = server.accept()
            with connection:
                connection.recv(65536)
                connection.sendall(b"HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n")
                while not stop.wait(0.2):
                    try:
                        connection.sendall(b"x")
                    except OSError:
                        return

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        opener = urllib.request.build_opener(PublicHTTPHandler())
        started = time.monotonic()
        try:
            with pytest.raises(requests.exceptions.ReadTimeout), overall_deadline(1):
                opener.open(f"http://service.test:{server.getsockname()[1]}/", timeout=3).read()
            assert time.monotonic() - started < 4
        finally:
            stop.set()
            server.close()
            thread.join(5)


class TestARedirectIsNotLookedInto:
    """Nothing follows a redirect through these; its body and Location stay unread."""

    @pytest.mark.parametrize("location", ["http://[bad/x", "http://elsewhere.test/"])
    def test_the_session_hands_the_redirect_back_unread(self, dns, loopback_allowed, location):
        # Session.send prepared Response.next even with allow_redirects=False:
        # it read the whole body and parsed Location, raising ValueError for [bad
        server = _Listener(
            f"HTTP/1.1 302 Found\r\nLocation: {location}\r\nContent-Length: 1000000000\r\n"
            f"Connection: close\r\n\r\npartial".encode())
        try:
            with _session() as session:
                response = session.get(f"http://service.test:{server.port}/", timeout=(3, 3),
                                       allow_redirects=False, stream=True)

            assert response.status_code == 302
            assert response.next is None
            assert not response._content_consumed
            response.close()
        finally:
            server.close()

    def test_the_image_opener_does_not_read_the_redirect_body(self, dns, loopback_allowed):
        # http_error_302 read the redirect's whole body before following it
        image = _Listener(b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: 3\r\n"
                          b"Connection: close\r\n\r\nPNG")
        redirect = _Listener(
            f"HTTP/1.1 302 Found\r\nLocation: http://service.test:{image.port}/i.png\r\n"
            f"Content-Length: 1000000000\r\nConnection: close\r\n\r\npartial".encode())
        try:
            data = diagram_net_utils.safe_download_image(f"http://service.test:{redirect.port}/")

            assert data == b"PNG"
        finally:
            redirect.close()
            image.close()

"""The diagram editor's image download refuses what is not a public image of a bounded size.

The scene's tests stand in for ``safe_download_image``, so none of its own
checks ran: a text page posing as an image, a size over the cap (declared or
not), an unsafe URL, a redirect to a private address.
"""
from __future__ import annotations

import ipaddress
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pybreeze.pybreeze_ui.diagram_editor import diagram_net_utils
from pybreeze.pybreeze_ui.diagram_editor.diagram_net_utils import ImageDownloadError, safe_download_image
from pybreeze.utils.network import url_validation

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
_LOOPBACK = ipaddress.ip_address("127.0.0.1")


class _Server:
    """Serves ``routes[path] = (status, headers, body)`` on loopback."""

    def __init__(self, routes: dict[str, tuple[int, dict[str, str], bytes]]) -> None:
        self.requests: list[str] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"  # a body with no length ends when the connection does

            def do_GET(self):  # noqa: N802 — the name http.server calls
                server.requests.append(self.path)
                status, headers, body = routes[self.path]
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                """Quiet."""

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def loopback_only(monkeypatch):
    """127.0.0.1 may stand in for a public server; every other private address stays refused."""
    blocked = url_validation._is_blocked_ip
    monkeypatch.setattr(url_validation, "_is_blocked_ip", lambda ip: ip != _LOOPBACK and blocked(ip))


@pytest.fixture
def serve():
    servers: list[_Server] = []

    def start(routes):
        server = _Server(routes)
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.close()


def test_an_image_comes_back_whole(loopback_only, serve):
    server = serve({"/a.png": (200, {"Content-Type": "image/png", "Content-Length": str(len(_PNG))}, _PNG)})
    assert safe_download_image(server.url("/a.png")) == _PNG


def test_a_text_page_is_not_an_image(loopback_only, serve):
    server = serve({"/a.png": (200, {"Content-Type": "text/html; charset=utf-8"}, b"<html>not found</html>")})
    url = server.url("/a.png")
    with pytest.raises(ImageDownloadError, match="text/html"):
        safe_download_image(url)


def test_a_declared_size_over_the_cap_is_refused_unread(loopback_only, serve, monkeypatch):
    monkeypatch.setattr(diagram_net_utils, "MAX_DOWNLOAD_BYTES", 100)
    server = serve({"/big.png": (200, {"Content-Type": "image/png", "Content-Length": "1000"}, b"\x00" * 1000)})
    url = server.url("/big.png")
    with pytest.raises(ImageDownloadError):
        safe_download_image(url)


def test_a_body_over_the_cap_with_no_length_is_refused(loopback_only, serve, monkeypatch):
    # An absent or low Content-Length must not let a larger body through
    monkeypatch.setattr(diagram_net_utils, "MAX_DOWNLOAD_BYTES", 100)
    server = serve({"/big.png": (200, {"Content-Type": "image/png"}, b"\x00" * 500)})
    url = server.url("/big.png")
    with pytest.raises(ImageDownloadError):
        safe_download_image(url)


def test_an_unsafe_url_is_refused_as_a_download_error(serve):
    # The canvas catches ImageDownloadError; an UnsafeURLError would escape it
    server = serve({"/a.png": (200, {"Content-Type": "image/png"}, _PNG)})
    url = server.url("/a.png")
    with pytest.raises(ImageDownloadError):
        safe_download_image(url)
    assert server.requests == []


def test_a_redirect_to_a_private_address_is_not_followed(loopback_only, serve):
    server = serve({"/a.png": (302, {"Location": "http://169.254.169.254/latest/meta-data/"}, b"")})
    url = server.url("/a.png")
    with pytest.raises(ImageDownloadError):
        safe_download_image(url)
    assert server.requests == ["/a.png"]


def test_a_redirect_to_a_public_address_is_followed(loopback_only, serve):
    server = serve({
        "/old.png": (301, {"Location": "/new.png"}, b""),
        "/new.png": (200, {"Content-Type": "image/png", "Content-Length": str(len(_PNG))}, _PNG),
    })
    assert safe_download_image(server.url("/old.png")) == _PNG
    assert server.requests == ["/old.png", "/new.png"]


@pytest.mark.parametrize("length", ["abc", "-5"])
def test_a_length_that_is_no_length_leaves_the_read_to_decide(loopback_only, serve, length):
    # A hostile or broken header is not trusted either way: the bounded read still caps it
    server = serve({"/a.png": (200, {"Content-Type": "image/png", "Content-Length": length}, _PNG)})
    assert safe_download_image(server.url("/a.png")) == _PNG

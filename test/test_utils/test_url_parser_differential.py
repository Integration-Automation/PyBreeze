"""The host validate_url checks is the host requests connects to.

The check read the host with ``urlparse``; ``requests`` connects to the host
``urllib3`` reads. A URL the two read differently got a public host checked
and a private one connected to.
"""
from __future__ import annotations

import socket
import threading

import pytest
import requests

from pybreeze.utils.network import url_validation
from pybreeze.utils.network.url_validation import UnsafeURLError, validate_url

_PUBLIC = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 0))]


@pytest.fixture
def public_dns(monkeypatch):
    """Every name resolves to a public address, so only the parsing decides."""
    monkeypatch.setattr(url_validation.socket, "getaddrinfo", lambda *_a, **_k: _PUBLIC)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1\\@example.com/",
    "http://127.0.0.1:8080\\@example.com/",
    "http://169.254.169.254\\@example.com/latest/meta-data/",
    "http://exam\nple.com/",
    "http://example.com\t/",
    "http://example.com/\x00",
])
def test_a_url_read_two_ways_is_refused(public_dns, url):
    with pytest.raises(UnsafeURLError):
        validate_url(url)


@pytest.mark.parametrize("url", [
    "https://example.com/path?q=1#frag",
    "https://user:secret@example.com/",
    "https://EXAMPLE.com/",
    "https://bücher.example/",
    "https://api.example.com:8443/v1",
])
def test_an_ordinary_url_still_passes(public_dns, url):
    assert validate_url(url) == url


def test_the_parser_error_does_not_quote_the_url(public_dns):
    with pytest.raises(UnsafeURLError) as raised:
        validate_url("http://[::1/api?token=sk-live-not-a-real-key")

    assert "sk-live" not in str(raised.value)


def test_the_loopback_listener_is_never_reached(public_dns):
    """The reported attack, end to end: the check passed and requests got the secret."""
    served: list = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(3)
        port = listener.getsockname()[1]
        url = f"http://127.0.0.1:{port}\\@example.com/"

        def serve() -> None:
            try:
                connection, _address = listener.accept()
            except OSError:
                return
            with connection:
                served.append(connection.recv(1024))
                connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nSECRET")

        server = threading.Thread(target=serve)
        server.start()
        try:
            validate_url(url)
            requests.get(url, timeout=(3, 3), allow_redirects=False)
        except UnsafeURLError:
            pass
        finally:
            listener.close()
            server.join(5)

    assert served == []


def test_the_two_readings_are_compared_past_the_character_check(public_dns):
    # Every URL above stops at the character check; this one passes it, and only
    # the comparison sees that urllib3 decodes the zone ID and urlparse does not
    from pybreeze.utils.exception.exception_tags import url_ambiguous_host_error

    with pytest.raises(UnsafeURLError) as raised:
        validate_url("http://[fe80::1%25eth0]/")

    assert str(raised.value) == url_ambiguous_host_error


def test_a_url_only_urlparse_refuses_is_refused_without_quoting_it(public_dns, monkeypatch):
    # No URL urllib3 takes is known to fail urlparse, but one would have escaped
    # into the Qt slot as a ValueError quoting the whole URL
    from pybreeze.utils.exception.exception_tags import url_unparsable_error

    def refuse(url):
        raise ValueError(f"netloc {url!r} contains invalid characters")

    monkeypatch.setattr(url_validation, "urlparse", refuse)

    with pytest.raises(UnsafeURLError) as raised:
        validate_url("https://example.com/?token=sk-live-not-a-real-key")

    assert str(raised.value) == url_unparsable_error


def test_a_name_idna_cannot_encode_is_left_as_it_is():
    # It then fails the comparison or the lookup; it is not changed into another name
    assert url_validation._as_ascii("a☕b.com") == "a☕b.com"

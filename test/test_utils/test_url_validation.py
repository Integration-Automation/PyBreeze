from __future__ import annotations

import pytest

from pybreeze.utils.network.url_validation import UnsafeURLError, validate_url


class TestSchemeValidation:
    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "gopher://example.com/",
        "data:text/plain;base64,AAAA",
    ])
    def test_non_http_schemes_rejected(self, url):
        with pytest.raises(UnsafeURLError):
            validate_url(url)

    def test_missing_hostname_rejected(self):
        with pytest.raises(UnsafeURLError):
            validate_url("http:///nohost")


class TestPrivateAddressBlocking:
    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/",          # loopback
        "http://10.0.0.1/",           # RFC1918
        "http://192.168.1.1/",        # RFC1918
        "http://172.16.0.1/",         # RFC1918
        "http://169.254.169.254/",    # link-local / cloud metadata
        "http://0.0.0.0/",            # unspecified
        "http://100.64.0.1/",         # RFC6598 CGNAT
        "http://224.0.0.1/",          # multicast
        "http://[::1]/",              # IPv6 loopback
        "http://[fe80::1]/",          # IPv6 link-local
        "http://[fec0::1]/",          # IPv6 site-local (deprecated, still routed in places)
    ])
    def test_blocked(self, url):
        with pytest.raises(UnsafeURLError):
            validate_url(url)


class TestIPv6TransitionForms:
    """IPv6 wrappers that route to the blocked cloud-metadata IPv4 (169.254.169.254)."""

    @pytest.mark.parametrize("url", [
        "http://[::ffff:169.254.169.254]/",   # IPv4-mapped
        "http://[2002:a9fe:a9fe::1]/",         # 6to4 wrapping 169.254.169.254
        "http://[64:ff9b::a9fe:a9fe]/",        # NAT64 well-known prefix
    ])
    def test_transition_form_to_metadata_blocked(self, url):
        with pytest.raises(UnsafeURLError):
            validate_url(url)


class TestPublicAddressAllowed:
    @pytest.mark.parametrize("url", [
        "http://8.8.8.8/",
        "https://1.1.1.1/path?q=1",
        "http://[2606:4700:4700::1111]/",  # Cloudflare public IPv6
    ])
    def test_public_ip_allowed(self, url):
        assert validate_url(url) == url


class TestHostnamesThatCannotBeLookedUp:
    """Whatever a hostname is, the answer is an UnsafeURLError, not a stray exception.

    A caller catches ``UnsafeURLError``; anything else escapes its handler and,
    in a Qt slot, takes the application with it.
    """

    @pytest.mark.parametrize("url", [
        "http://" + "a" * 70 + ".example",
        "http://.example",
        "http://exa mple.example",
        "http://" + "b" * 300,
    ], ids=["label too long", "empty label", "space in hostname", "name too long"])
    def test_an_impossible_hostname_is_refused_like_any_other(self, url):
        with pytest.raises(UnsafeURLError):
            validate_url(url)


class TestTheAddressesOfAName:
    @staticmethod
    def _resolving(monkeypatch, *addresses):
        import socket

        from pybreeze.utils.network import url_validation

        answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0)) for address in addresses]
        monkeypatch.setattr(url_validation.socket, "getaddrinfo", lambda *_a, **_k: answer)

    def test_a_name_with_no_address_is_refused(self, monkeypatch):
        from pybreeze.utils.network.url_validation import public_addresses

        self._resolving(monkeypatch)
        with pytest.raises(UnsafeURLError, match="Cannot resolve hostname 'example.com'"):
            public_addresses("example.com")

    def test_each_address_comes_once_in_the_resolvers_order(self, monkeypatch):
        # The resolver repeats an address once per socket type it was not asked to filter
        from pybreeze.utils.network.url_validation import public_addresses

        self._resolving(monkeypatch, "93.184.215.14", "93.184.215.14", "8.8.8.8", "93.184.215.14")
        assert public_addresses("example.com") == ["93.184.215.14", "8.8.8.8"]


class TestTheIPv4InsideAnIPv6Wrapper:
    """The standard library already refuses Teredo (private) and NAT64 (reserved) addresses.

    ``_embedded_ipv4`` is the check behind that, should a Python version class
    them otherwise, as 3.12 and 3.13 reclassified other ranges: it must find
    the IPv4 each wrapper routes to, and the suite never reached it.
    """

    @pytest.mark.parametrize(("wrapped", "inside"), [
        ("::ffff:169.254.169.254", "169.254.169.254"),                  # IPv4-mapped
        ("2002:a9fe:a9fe::1", "169.254.169.254"),                       # 6to4
        ("2001:0:0:0:0:0:5601:5601", "169.254.169.254"),                # Teredo: the client, inverted
        ("64:ff9b::a9fe:a9fe", "169.254.169.254"),                      # NAT64 well-known prefix
    ])
    def test_the_address_it_routes_to_is_found(self, wrapped, inside):
        import ipaddress

        from pybreeze.utils.network.url_validation import _embedded_ipv4

        assert ipaddress.ip_address(inside) in _embedded_ipv4(ipaddress.ip_address(wrapped))

    def test_a_plain_ipv6_address_wraps_nothing(self):
        import ipaddress

        from pybreeze.utils.network.url_validation import _embedded_ipv4

        assert _embedded_ipv4(ipaddress.ip_address("2606:4700:4700::1111")) == []

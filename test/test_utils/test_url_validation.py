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

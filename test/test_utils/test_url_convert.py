"""Tests for URL <-> JSON parsing and building."""
from __future__ import annotations

import json

import pytest

from pybreeze.utils.exception.exceptions import UrlConvertException
from pybreeze.utils.url_tools.url_convert import (
    build_url,
    json_to_url,
    parse_url,
    url_to_json,
)


class TestParseUrl:
    def test_full_url(self):
        parts = parse_url("https://user:pass@example.com:8080/api/v1?a=1&b=2#frag")
        assert parts["scheme"] == "https"
        assert parts["host"] == "example.com"
        assert parts["port"] == 8080
        assert parts["path"] == "/api/v1"
        assert parts["query"] == {"a": "1", "b": "2"}
        assert parts["fragment"] == "frag"
        assert parts["username"] == "user"
        assert parts["password"] == "pass"

    def test_minimal_url(self):
        parts = parse_url("https://example.com")
        assert parts["scheme"] == "https"
        assert parts["host"] == "example.com"
        assert parts["port"] is None
        assert parts["path"] == ""
        assert parts["query"] == {}
        assert "username" not in parts

    def test_query_values_url_decoded(self):
        parts = parse_url("https://x/?q=hello%20world")
        assert parts["query"]["q"] == "hello world"

    def test_whitespace_is_stripped(self):
        assert parse_url("  https://x/api  ")["path"] == "/api"

    def test_out_of_range_port_is_none(self):
        assert parse_url("https://x:99999/")["port"] is None


class TestUrlToJson:
    def test_returns_valid_json(self):
        data = json.loads(url_to_json("https://x/api?a=1"))
        assert data["host"] == "x"
        assert data["query"] == {"a": "1"}


class TestBuildUrl:
    def test_full_components(self):
        url = build_url({
            "scheme": "https", "host": "example.com", "port": 8080,
            "path": "/api", "query": {"a": "1"}, "fragment": "f",
            "username": "user", "password": "pass",
        })
        assert url == "https://user:pass@example.com:8080/api?a=1#f"

    def test_minimal_components(self):
        assert build_url({"scheme": "https", "host": "x"}) == "https://x"

    def test_missing_parts_default_empty(self):
        assert build_url({"host": "x"}) == "//x"

    def test_ipv6_host_is_bracketed(self):
        assert build_url({"scheme": "http", "host": "::1", "port": 8080}) == "http://[::1]:8080"

    def test_username_without_password(self):
        assert build_url({"scheme": "https", "host": "x", "username": "user"}) == "https://user@x"


class TestRoundTrip:
    @pytest.mark.parametrize("url", [
        "https://example.com/api/v1?a=1&b=2#section",
        "http://user:pass@host:8080/p",
        "https://example.com",
        "https://x/?flag=",
    ])
    def test_parse_then_build_is_stable(self, url):
        assert build_url(parse_url(url)) == url


class TestJsonToUrl:
    def test_builds_from_json(self):
        assert json_to_url('{"scheme": "https", "host": "x", "path": "/a"}') == "https://x/a"

    def test_invalid_json_raises(self):
        with pytest.raises(UrlConvertException):
            json_to_url("not json")

    def test_non_object_raises(self):
        with pytest.raises(UrlConvertException):
            json_to_url('["a", "b"]')

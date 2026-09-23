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
        parts = parse_url("https://x/?q=hello+world&t=a%2Bb")
        assert parts["query"] == {"q": "hello world", "t": "a+b"}

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


class TestAUrlThatCannotBeSplit:
    def test_an_unclosed_ipv6_bracket_is_a_convert_error(self):
        from pybreeze.utils.exception.exceptions import UrlConvertException
        from pybreeze.utils.url_tools.url_convert import url_to_json

        with pytest.raises(UrlConvertException):
            url_to_json("http://[::1")


class TestARepeatedKey:
    def test_every_value_is_kept(self):
        from pybreeze.utils.url_tools.url_convert import parse_url

        assert parse_url("https://x/?tag=a&tag=b")["query"] == {"tag": ["a", "b"]}

    def test_the_round_trip_keeps_them(self):
        from pybreeze.utils.url_tools.url_convert import build_url, parse_url

        assert build_url(parse_url("https://x/?tag=a&tag=b&one=1")) == "https://x/?tag=a&tag=b&one=1"

    def test_a_key_that_repeats_after_another_keeps_its_place(self):
        # Grouped into a dict, a=1&b=2&a=3 came back as a=1&a=3&b=2: a signed URL breaks
        parts = parse_url("https://x/?a=1&b=2&a=3")

        assert parts["query"] == "a=1&b=2&a=3"
        assert build_url(parts) == "https://x/?a=1&b=2&a=3"


class TestAPortOfOtherDigits:
    @pytest.mark.parametrize("port", ["²", "٣"])
    def test_it_is_refused(self, port):
        # "²".isdigit() holds: int() raised past the builder, and "٣" became port 3
        with pytest.raises(UrlConvertException):
            json_to_url(json.dumps({"scheme": "http", "host": "h", "port": port}))


class TestAPortOutOfRange:
    def test_it_is_reported_rather_than_dropped(self):
        from pybreeze.utils.url_tools.url_convert import url_to_json

        with pytest.raises(UrlConvertException):
            url_to_json("http://host:99999/")

    @pytest.mark.parametrize("url", [
        "http://host/", "http://host:8080/", "http://[::1]:8080/", "http://[::1]/",
        "http://user:pa:ss@host/"])
    def test_urls_without_a_bad_port_still_convert(self, url):
        from pybreeze.utils.url_tools.url_convert import url_to_json

        assert json.loads(url_to_json(url))["scheme"] == "http"


class TestAnEmptyPort:
    def test_the_colon_alone_names_no_port(self):
        # RFC 3986 allows it; it was refused as a port out of range
        assert json.loads(url_to_json("http://example.com:/p"))["port"] is None


class TestPartsThatAreNotText:
    def test_null_parts_are_empty_not_none(self):
        url = json_to_url('{"scheme": "http", "host": "h", "path": null, "fragment": null}')

        assert url == "http://h"

    def test_a_null_query_value_is_empty_as_in_the_query_tool(self):
        assert json_to_url('{"scheme": "http", "host": "h", "query": {"a": null, "b": true}}') == "http://h?a=&b=true"

    def test_an_object_as_a_query_value_is_refused_not_flattened(self):
        # {"x": 1} went into the URL as its keys: b=x
        with pytest.raises(UrlConvertException):
            json_to_url('{"scheme": "http", "host": "h", "query": {"b": {"x": 1}}}')

    @pytest.mark.parametrize("port", ['"abc"', "70000", "-1", "true", "8.5"])
    def test_a_port_that_is_no_port_is_refused(self, port):
        # "abc" went into the URL as h:abc
        with pytest.raises(UrlConvertException):
            json_to_url(f'{{"scheme": "http", "host": "h", "port": {port}}}')

    @pytest.mark.parametrize(("port", "expected"), [("8080", "http://h:8080"), ('"8080"', "http://h:8080"),
                                                    ("null", "http://h"), ('""', "http://h")])
    def test_a_port_given_as_text_or_left_out_still_builds(self, port, expected):
        assert json_to_url(f'{{"scheme": "http", "host": "h", "port": {port}}}') == expected


class TestJsonNestedTooDeep:
    def test_it_is_reported_not_raised_out_of_the_tab(self):
        # json.loads raises RecursionError, which the tab did not catch
        with pytest.raises(UrlConvertException):
            json_to_url("[" * 100000)


class TestAQueryThatWouldNotComeBackAsWritten:
    @pytest.mark.parametrize("url", [
        "http://h/p?%zz=1&x=%ff", "http://h/p?flag", "http://h/p?a=b/c;d", "https://h/p?q=a%20b",
    ])
    def test_it_is_kept_as_text_and_rebuilt_unchanged(self, url):
        # Decoded and encoded again, %zz became %25zz, %ff U+FFFD, flag flag=, / %2F
        parts = json.loads(url_to_json(url))

        assert isinstance(parts["query"], str)
        assert json_to_url(url_to_json(url)) == url

    def test_one_that_does_is_still_a_dict_to_edit(self):
        assert json.loads(url_to_json("https://h/p?a=1&b=x+y"))["query"] == {"a": "1", "b": "x y"}


class TestQueryValuesAsWritten:
    def test_a_number_goes_into_the_url_as_written(self):
        url = json_to_url('{"scheme": "http", "host": "h", "query": {"v": 1E3, "p": 1.10}}')

        assert url == "http://h?v=1E3&p=1.10"

    def test_a_port_is_still_a_number(self):
        assert json_to_url('{"scheme": "http", "host": "h", "port": 8080}') == "http://h:8080"
        with pytest.raises(UrlConvertException):
            json_to_url('{"scheme": "http", "host": "h", "port": 8080.5}')

    def test_nan_is_refused(self):
        with pytest.raises(UrlConvertException):
            json_to_url('{"scheme": "http", "host": "h", "query": {"x": NaN}}')

    def test_a_lone_surrogate_is_refused_not_raised(self):
        with pytest.raises(UrlConvertException):
            json_to_url('{"scheme": "http", "host": "h", "query": {"q": "\ud83d"}}')

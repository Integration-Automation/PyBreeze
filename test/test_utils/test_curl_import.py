"""Tests for the cURL command parser and requests-code generator."""
from __future__ import annotations

import json

import pytest

from pybreeze.utils.curl_import.curl_parser import (
    CurlRequest,
    parse_curl,
    parse_query_pairs,
)
from pybreeze.utils.curl_import.request_codegen import to_requests_code
from pybreeze.utils.exception.exceptions import CurlParseException


class TestParseCurlBasics:
    def test_simple_get(self):
        request = parse_curl("curl https://example.com/api")
        assert request.method == "GET"
        assert request.url == "https://example.com/api"

    def test_explicit_method(self):
        request = parse_curl("curl -X DELETE https://example.com/x")
        assert request.method == "DELETE"

    def test_method_is_uppercased(self):
        request = parse_curl("curl -X post https://example.com/x")
        assert request.method == "POST"

    def test_long_request_flag(self):
        request = parse_curl("curl --request PUT https://example.com/x")
        assert request.method == "PUT"

    def test_url_flag(self):
        request = parse_curl("curl --url https://example.com/x")
        assert request.url == "https://example.com/x"

    def test_data_implies_post(self):
        request = parse_curl("curl https://example.com/x -d 'a=1'")
        assert request.method == "POST"
        assert request.body == "a=1"


class TestParseCurlHeaders:
    def test_single_header(self):
        request = parse_curl("curl -H 'Accept: application/json' https://x")
        assert request.headers["Accept"] == "application/json"

    def test_multiple_headers(self):
        request = parse_curl(
            "curl -H 'Accept: application/json' -H 'X-Token: abc' https://x")
        assert request.headers == {"Accept": "application/json", "X-Token": "abc"}

    def test_header_value_with_colon(self):
        request = parse_curl("curl -H 'Referer: https://a.com/b' https://x")
        assert request.headers["Referer"] == "https://a.com/b"

    def test_malformed_header_ignored(self):
        request = parse_curl("curl -H 'no-colon-here' https://x")
        assert request.headers == {}

    def test_header_value_lookup_is_case_insensitive(self):
        request = parse_curl("curl -H 'Content-Type: application/json' https://x")
        assert request.header_value("content-type") == "application/json"

    def test_user_agent_flag(self):
        request = parse_curl("curl -A 'my-agent' https://x")
        assert request.headers["User-Agent"] == "my-agent"

    def test_cookie_flag(self):
        request = parse_curl("curl -b 'session=1' https://x")
        assert request.headers["Cookie"] == "session=1"


class TestParseCurlBodyAndAuth:
    def test_multiple_data_joined(self):
        request = parse_curl("curl https://x -d 'a=1' -d 'b=2'")
        assert request.body == "a=1&b=2"

    def test_data_raw(self):
        request = parse_curl("curl https://x --data-raw '{\"a\": 1}'")
        assert request.body == '{"a": 1}'

    def test_basic_auth(self):
        request = parse_curl("curl -u user:pass https://x")
        assert request.username == "user"
        assert request.password == "pass"

    def test_auth_without_password(self):
        request = parse_curl("curl -u user https://x")
        assert request.username == "user"
        assert request.password == ""

    def test_get_flag_moves_data_to_params(self):
        request = parse_curl("curl -G https://x -d 'a=1' -d 'b=2'")
        assert request.method == "GET"
        assert request.params == {"a": "1", "b": "2"}
        assert request.body == ""


class TestParseCurlRobustness:
    def test_line_continuations(self):
        command = "curl https://x \\\n  -H 'Accept: application/json' \\\n  -d 'a=1'"
        request = parse_curl(command)
        assert request.url == "https://x"
        assert request.headers["Accept"] == "application/json"

    def test_caret_continuation(self):
        command = "curl https://x ^\n  -H 'Accept: application/json'"
        request = parse_curl(command)
        assert request.headers["Accept"] == "application/json"

    def test_leading_and_trailing_whitespace(self):
        request = parse_curl("   curl https://x   ")
        assert request.url == "https://x"

    def test_empty_command_raises(self):
        with pytest.raises(CurlParseException):
            parse_curl("   ")

    def test_non_curl_command_raises(self):
        with pytest.raises(CurlParseException):
            parse_curl("wget https://x")

    def test_unbalanced_quotes_raise(self):
        with pytest.raises(CurlParseException):
            parse_curl("curl 'https://x")

    def test_missing_flag_value_is_ignored(self):
        # A trailing flag with no value must not crash the parser.
        request = parse_curl("curl https://x -H")
        assert request.url == "https://x"


class TestParseCurlFlagArity:
    def test_ignored_value_flag_does_not_leak_to_url(self):
        # Regression: '--max-time 30' must not make the URL "30".
        request = parse_curl("curl --max-time 30 https://api.example.com/x")
        assert request.url == "https://api.example.com/x"

    def test_connect_timeout_consumed(self):
        request = parse_curl("curl --connect-timeout 5 https://x")
        assert request.url == "https://x"

    def test_output_flag_consumed(self):
        request = parse_curl("curl -o result.json https://x")
        assert request.url == "https://x"

    def test_valueless_flags_skipped(self):
        request = parse_curl("curl --compressed -L -k -s https://x -H 'Accept: application/json'")
        assert request.url == "https://x"
        assert request.headers["Accept"] == "application/json"

    def test_remote_name_is_valueless(self):
        # -O (remote name) takes no value; the URL is the next token.
        request = parse_curl("curl -O https://x/file.zip")
        assert request.url == "https://x/file.zip"

    def test_unknown_flag_is_treated_valueless(self):
        request = parse_curl("curl --totally-unknown-flag https://x")
        assert request.url == "https://x"

    def test_multiple_ignored_flags(self):
        request = parse_curl(
            "curl -s --compressed --max-time 30 -o out -H 'X: 1' https://x -d 'a=1'")
        assert request.url == "https://x"
        assert request.method == "POST"
        assert request.headers == {"X": "1"}
        assert request.body == "a=1"


class TestParseCurlJsonFlag:
    def test_json_flag_does_not_leak_to_url(self):
        # Regression: '--json {...}' must not become the URL.
        request = parse_curl("curl --json '{\"a\": 1}' https://api.example.com/x")
        assert request.url == "https://api.example.com/x"

    def test_json_flag_sets_body(self):
        request = parse_curl("curl --json '{\"a\": 1}' https://x")
        assert request.body == '{"a": 1}'

    def test_json_flag_sets_content_type_and_accept(self):
        request = parse_curl("curl --json '{\"a\": 1}' https://x")
        assert request.header_value("content-type") == "application/json"
        assert request.header_value("accept") == "application/json"

    def test_json_flag_implies_post(self):
        request = parse_curl("curl --json '{}' https://x")
        assert request.method == "POST"

    def test_explicit_headers_win_over_json_defaults(self):
        # setdefault: an explicit Content-Type is not overwritten by --json.
        request = parse_curl("curl -H 'Content-Type: text/plain' --json '{}' https://x")
        assert request.header_value("content-type") == "text/plain"


class TestParseCurlDataFile:
    def test_data_at_file_becomes_file_ref(self):
        request = parse_curl("curl -d @body.json https://x")
        assert request.data_file_refs == ["body.json"]
        assert request.body == ""

    def test_data_file_does_not_leak_to_url(self):
        request = parse_curl("curl -d @body.json https://x")
        assert request.url == "https://x"

    def test_data_file_implies_post(self):
        request = parse_curl("curl -d @body.json https://x")
        assert request.method == "POST"

    def test_data_raw_at_is_literal_not_file(self):
        # --data-raw never reads a file, even with a leading '@'.
        request = parse_curl("curl --data-raw '@literal' https://x")
        assert request.data_file_refs == []
        assert request.body == "@literal"

    def test_data_binary_file(self):
        request = parse_curl("curl --data-binary @payload.bin https://x")
        assert request.data_file_refs == ["payload.bin"]

    def test_inline_data_still_works(self):
        request = parse_curl("curl -d 'a=1' https://x")
        assert request.data_file_refs == []
        assert request.body == "a=1"


class TestParseCurlDataUrlencode:
    def test_encodes_value_part(self):
        request = parse_curl("curl --data-urlencode 'q=hello world' https://x")
        assert request.body == "q=hello%20world"

    def test_keeps_name_literal(self):
        request = parse_curl("curl --data-urlencode 'name=a b' https://x")
        assert request.body == "name=a%20b"

    def test_encodes_slash_in_content(self):
        request = parse_curl("curl --data-urlencode 'q=a/b' https://x")
        assert request.body == "q=a%2Fb"

    def test_leading_equals_encodes_all(self):
        request = parse_curl("curl --data-urlencode '=a b' https://x")
        assert request.body == "a%20b"

    def test_no_equals_encodes_whole(self):
        request = parse_curl("curl --data-urlencode 'hello world' https://x")
        assert request.body == "hello%20world"

    def test_at_in_content_is_encoded(self):
        request = parse_curl("curl --data-urlencode 'q=a@b.com' https://x")
        assert request.body == "q=a%40b.com"

    def test_file_form_left_literal(self):
        # 'name@file' (no '=') is a file form curl reads; we cannot, so leave it.
        request = parse_curl("curl --data-urlencode 'field@data.txt' https://x")
        assert request.body == "field@data.txt"


class TestParseCurlForm:
    def test_form_field_recorded(self):
        request = parse_curl("curl -F 'name=widget' https://x")
        assert request.form_fields == ["name=widget"]

    def test_form_implies_post(self):
        request = parse_curl("curl -F 'name=widget' https://x")
        assert request.method == "POST"

    def test_form_does_not_leak_to_url(self):
        # Regression: '-F photo=@a.jpg' must not become the URL.
        request = parse_curl("curl -F 'photo=@a.jpg' https://up.example.com")
        assert request.url == "https://up.example.com"

    def test_multiple_form_fields(self):
        request = parse_curl("curl -F 'a=1' -F 'b=@f.txt' https://x")
        assert request.form_fields == ["a=1", "b=@f.txt"]

    def test_form_string_flag(self):
        request = parse_curl("curl --form-string 'a=1' https://x")
        assert request.form_fields == ["a=1"]


class TestParseQueryPairs:
    def test_parses_pairs(self):
        assert parse_query_pairs(["a=1", "b=2"]) == {"a": "1", "b": "2"}

    def test_ignores_fragments_without_equals(self):
        assert parse_query_pairs(["a=1", "bad"]) == {"a": "1"}

    def test_empty(self):
        assert parse_query_pairs([]) == {}


class TestToRequestsCode:
    def test_simple_get(self):
        code = to_requests_code(parse_curl("curl https://example.com/api"))
        assert "import requests" in code
        assert 'url = "https://example.com/api"' in code
        assert 'requests.request("GET"' in code

    def test_headers_rendered(self):
        code = to_requests_code(parse_curl("curl -H 'Accept: application/json' https://x"))
        assert "headers = {" in code
        assert "headers=headers" in code

    def test_json_body_uses_json_kwarg(self):
        command = "curl -H 'Content-Type: application/json' -d '{\"a\": 1}' https://x"
        code = to_requests_code(parse_curl(command))
        assert "json=json_body" in code
        assert "json_body = {" in code

    def test_non_json_body_uses_data_kwarg(self):
        code = to_requests_code(parse_curl("curl -d 'a=1&b=2' https://x"))
        assert "data=data" in code
        assert "json=" not in code

    def test_auth_rendered(self):
        code = to_requests_code(parse_curl("curl -u user:pass https://x"))
        assert "auth = (" in code
        assert "auth=auth" in code

    def test_params_rendered(self):
        code = to_requests_code(parse_curl("curl -G https://x -d 'a=1'"))
        assert "params = {" in code
        assert "params=params" in code

    def test_generated_code_is_valid_python(self):
        command = (
            "curl -X POST https://example.com/api "
            "-H 'Content-Type: application/json' "
            "-H 'Authorization: Bearer tok' "
            "-d '{\"name\": \"a\"}'"
        )
        code = to_requests_code(parse_curl(command))
        # Must at least compile as valid Python source.
        compile(code, "<generated>", "exec")

    def test_json_body_is_pretty_printed(self):
        command = "curl -H 'Content-Type: application/json' -d '{\"a\":1,\"b\":2}' https://x"
        code = to_requests_code(parse_curl(command))
        # Pretty-printing indents nested keys onto their own lines.
        assert '"a": 1' in code


class TestCurlRequestDataclass:
    def test_body_joins_parts(self):
        request = CurlRequest(data_parts=["a=1", "b=2"])
        assert request.body == "a=1&b=2"

    def test_has_body_reflects_payload(self):
        assert not CurlRequest().has_body
        assert CurlRequest(data_parts=["a=1"]).has_body
        assert CurlRequest(form_fields=["a=1"]).has_body
        assert CurlRequest(data_file_refs=["f.json"]).has_body

    def test_header_value_missing_returns_none(self):
        request = CurlRequest(headers={"Accept": "text/html"})
        assert request.header_value("content-type") is None

    def test_defaults(self):
        request = CurlRequest()
        assert request.method == "GET"
        assert request.url == ""
        assert request.headers == {}
        # The JSON round-trip in codegen should never see a stale shared dict.
        assert CurlRequest().headers is not request.headers

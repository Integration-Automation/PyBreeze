"""Tests for the HTTP response analyzer."""
from __future__ import annotations

import base64
import json

import pytest

from pybreeze.utils.response_inspector.response_analyzer import analyze_response


def _jwt(header: dict, payload: dict) -> str:
    def seg(obj):
        raw = json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{seg(header)}.{seg(payload)}.sig"


class TestStatusDetection:
    def test_detects_status_line(self):
        analysis = analyze_response("HTTP/1.1 200 OK\n\n{}")
        assert analysis.status is not None
        assert analysis.status.code == 200
        assert analysis.status.phrase == "OK"

    def test_status_11_or_2(self):
        analysis = analyze_response("HTTP/2 404 Not Found\n\n")
        assert analysis.status.code == 404

    def test_no_status_line(self):
        analysis = analyze_response('{"a": 1}')
        assert analysis.status is None

    def test_an_unregistered_code_is_shown_with_its_class_and_own_phrase(self):
        # It was dropped: no status section, and Open status greyed out
        analysis = analyze_response("HTTP/1.1 299 Weird\n\n")

        assert (analysis.status.code, analysis.status.phrase, analysis.status.category) == (
            299, "Weird", "Success")

    def test_an_unregistered_pseudo_header_status_has_no_phrase(self):
        analysis = analyze_response(":status: 599\ncontent-type: text/plain\n\nx")

        assert (analysis.status.code, analysis.status.phrase, analysis.status.category) == (
            599, "", "Server Error")

    def test_a_registered_code_keeps_its_registered_phrase(self):
        assert analyze_response("HTTP/1.1 404 Nope\n\n").status.phrase == "Not Found"


class TestHeaderParsing:
    def test_parses_headers(self):
        text = "HTTP/1.1 200 OK\nContent-Type: application/json\nX-Token: abc\n\n{}"
        analysis = analyze_response(text)
        assert analysis.headers == {"Content-Type": "application/json", "X-Token": "abc"}

    def test_headers_without_status_line(self):
        text = "Content-Type: text/html\n\n<html>"
        analysis = analyze_response(text)
        assert analysis.headers == {"Content-Type": "text/html"}

    def test_header_value_with_colon(self):
        text = "HTTP/1.1 200 OK\nDate: Mon, 01 Jan 2021 00:00:00 GMT\n\n"
        analysis = analyze_response(text)
        assert analysis.headers["Date"] == "Mon, 01 Jan 2021 00:00:00 GMT"

    def test_crlf_line_endings(self):
        text = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{}"
        analysis = analyze_response(text)
        assert analysis.headers == {"Content-Type": "application/json"}


class TestBodyDetection:
    def test_json_body_is_pretty_printed(self):
        analysis = analyze_response("HTTP/1.1 200 OK\n\n{\"a\":1,\"b\":2}")
        assert analysis.is_json_body
        assert '"a": 1' in analysis.pretty_body

    def test_body_only_json(self):
        analysis = analyze_response('{"a": 1}')
        assert analysis.is_json_body
        assert analysis.body == '{"a": 1}'

    def test_non_json_body(self):
        analysis = analyze_response("HTTP/1.1 200 OK\n\n<html>hi</html>")
        assert not analysis.is_json_body
        assert analysis.pretty_body is None
        assert analysis.body == "<html>hi</html>"

    def test_json_key_order_preserved(self):
        analysis = analyze_response('{"z": 1, "a": 2}')
        # Keys should appear in original order, not sorted.
        assert analysis.pretty_body.index('"z"') < analysis.pretty_body.index('"a"')

    def test_numbers_keep_their_text(self):
        # json.loads made 1e400 the Infinity that is not JSON, and rounded the long one
        analysis = analyze_response('{"n": 1e400, "big": 12345678901234567890.5}')

        assert '"n": 1e400' in analysis.pretty_body
        assert '"big": 12345678901234567890.5' in analysis.pretty_body

    def test_a_repeated_key_is_not_laid_out_as_json(self):
        # It kept the last value without a word, and JSON Format then refused the body
        analysis = analyze_response('{"a": 1, "a": 2}')

        assert not analysis.is_json_body
        assert analysis.pretty_body is None

    def test_body_without_blank_line(self):
        # Headers then a JSON body with no separating blank line.
        text = "HTTP/1.1 200 OK\nContent-Type: application/json\n{\"a\": 1}"
        analysis = analyze_response(text)
        assert analysis.is_json_body
        assert analysis.headers == {"Content-Type": "application/json"}


class TestJwtDetection:
    def test_finds_jwt_in_header(self):
        token = _jwt({"alg": "HS256"}, {"sub": "42"})
        text = f"HTTP/1.1 200 OK\nAuthorization: Bearer {token}\n\n{{}}"
        analysis = analyze_response(text)
        assert len(analysis.jwt_findings) == 1
        assert analysis.jwt_findings[0].decoded.payload == {"sub": "42"}

    def test_finds_jwt_in_body(self):
        token = _jwt({"alg": "HS256"}, {"token": "yes"})
        analysis = analyze_response(f'{{"access_token": "{token}"}}')
        assert any(f.decoded.payload == {"token": "yes"} for f in analysis.jwt_findings)

    def test_no_jwt(self):
        assert analyze_response("HTTP/1.1 200 OK\n\n{}").jwt_findings == []

    def test_duplicate_jwt_reported_once(self):
        token = _jwt({"alg": "HS256"}, {"sub": "1"})
        text = f"Authorization: Bearer {token}\nX-Copy: {token}\n\n{{}}"
        analysis = analyze_response(text)
        assert len(analysis.jwt_findings) == 1

    def test_jwt_like_but_undecodable_is_skipped(self):
        # Starts like a JWT but the segments are not valid base64url JSON.
        text = "eyJxx.yyy.zzz appears here"
        assert analyze_response(text).jwt_findings == []


class TestEmptyInput:
    def test_empty(self):
        analysis = analyze_response("")
        assert analysis.status is None
        assert analysis.headers == {}
        assert analysis.body == ""


def test_a_body_nested_past_the_recursion_limit_is_not_json():
    analysis = analyze_response("HTTP/1.1 200 OK\n\n" + "[" * 100000 + "]" * 100000)

    assert analysis.pretty_body is None


def test_a_header_sent_twice_keeps_both_values():
    analysis = analyze_response(
        "HTTP/1.1 200 OK\nSet-Cookie: a=1\nSet-Cookie: b=2\nContent-Type: text/plain\n\nok")

    assert analysis.headers == {"Set-Cookie": ["a=1", "b=2"], "Content-Type": "text/plain"}


class TestHeadersAsHttpDefinesThem:
    def test_a_folded_line_continues_the_header_and_the_body_is_still_json(self):
        # It ended the headers: the value was cut and the body no longer JSON
        analysis = analyze_response('HTTP/1.1 200 OK\nX-Long: a\n b\n\n{"a": 1}')

        assert analysis.headers["X-Long"] == "a b"
        assert analysis.is_json_body

    def test_names_differing_only_in_case_are_one_header(self):
        analysis = analyze_response("HTTP/1.1 200 OK\nSet-Cookie: a=1\nset-cookie: b=2\n\n")

        assert analysis.headers == {"Set-Cookie": ["a=1", "b=2"]}

    def test_an_http2_status_pseudo_header_gives_the_status_and_keeps_the_headers(self):
        # It ended the headers, and everything after it was read as the body
        analysis = analyze_response(':status: 404\ncontent-type: application/json\n\n{"a": 1}')

        assert analysis.status is not None
        assert analysis.status.code == 404
        assert analysis.headers == {"content-type": "application/json"}
        assert analysis.is_json_body

    @pytest.mark.parametrize("code", ["²", "٤٠٤", "4 0 4"])
    def test_a_status_that_is_not_ascii_digits_is_no_status(self, code):
        # "²".isdigit() holds, and int() raised ValueError out of the tab
        analysis = analyze_response(f":status: {code}\ncontent-type: text/plain\n\nbody")

        assert analysis.status is None
        assert analysis.headers == {"content-type": "text/plain"}


class TestCurlShowsEveryResponse:
    """curl -i prints interim and earlier responses before the final one."""

    @pytest.mark.parametrize("first", [
        "HTTP/1.1 100 Continue\n\n",
        "HTTP/1.1 200 Connection established\n\n",
        "HTTP/1.1 301 Moved Permanently\nLocation: /new\n\n",
    ])
    def test_the_final_response_is_the_one_read(self, first):
        # The first status line was taken and the real response read as its body
        from pybreeze.utils.response_inspector.response_analyzer import analyze_response

        result = analyze_response(first + 'HTTP/1.1 404 Not Found\nContent-Type: application/json\n\n{"a": 1}')

        assert result.status.code == 404
        assert result.headers == {"Content-Type": "application/json"}
        assert result.is_json_body

    def test_a_body_alone_is_not_a_header(self):
        from pybreeze.utils.response_inspector.response_analyzer import analyze_response

        result = analyze_response("Error: invalid token supplied")

        assert result.headers == {}
        assert result.body == "Error: invalid token supplied"

    def test_a_header_block_is_still_headers(self):
        from pybreeze.utils.response_inspector.response_analyzer import analyze_response

        result = analyze_response("Content-Type: text/plain\nX-Id: 7\n\nhello")

        assert result.headers == {"Content-Type": "text/plain", "X-Id": "7"}
        assert result.body == "hello"

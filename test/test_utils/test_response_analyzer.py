"""Tests for the HTTP response analyzer."""
from __future__ import annotations

import base64
import json

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

    def test_unknown_status_code(self):
        analysis = analyze_response("HTTP/1.1 299 Weird\n\n")
        assert analysis.status is None  # 299 is not a known code


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

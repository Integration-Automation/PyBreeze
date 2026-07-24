"""Tests for the JWT decoder (inspection only, no signature verification)."""
from __future__ import annotations

import base64
import json

import pytest

from pybreeze.utils.exception.exceptions import JwtDecodeException
from pybreeze.utils.jwt_tools.jwt_decoder import (
    decode_jwt,
    format_timestamp_claim,
    humanized_timestamp_claims,
)


def _segment(obj: dict) -> str:
    """Encode a dict as a base64url JWT segment (no padding), as real JWTs do."""
    raw = json.dumps(obj).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _make_jwt(header: dict, payload: dict, signature: str = "sig") -> str:
    return f"{_segment(header)}.{_segment(payload)}.{signature}"


class TestDecodeJwt:
    def test_decodes_header_and_payload(self):
        token = _make_jwt({"alg": "HS256", "typ": "JWT"}, {"sub": "123", "name": "a"})
        decoded = decode_jwt(token)
        assert decoded.header == {"alg": "HS256", "typ": "JWT"}
        assert decoded.payload == {"sub": "123", "name": "a"}

    def test_signature_segment_preserved(self):
        token = _make_jwt({"alg": "none"}, {"sub": "1"}, signature="abc")
        assert decode_jwt(token).signature == "abc"

    def test_handles_missing_padding(self):
        # Segments without '=' padding (the normal JWT form) must still decode.
        token = _make_jwt({"a": 1}, {"b": 2})
        assert "=" not in token.split(".")[0]
        assert decode_jwt(token).payload == {"b": 2}

    def test_unicode_claims(self):
        token = _make_jwt({"alg": "HS256"}, {"name": "測試"})
        assert decode_jwt(token).payload["name"] == "測試"

    def test_whitespace_is_trimmed(self):
        token = _make_jwt({"alg": "HS256"}, {"sub": "1"})
        assert decode_jwt(f"  {token}  ").payload == {"sub": "1"}

    def test_empty_token_raises(self):
        with pytest.raises(JwtDecodeException):
            decode_jwt("   ")

    def test_wrong_segment_count_raises(self):
        with pytest.raises(JwtDecodeException):
            decode_jwt("only.two")

    def test_invalid_base64_raises(self):
        with pytest.raises(JwtDecodeException):
            decode_jwt("!!!.!!!.sig")

    def test_non_json_segment_raises(self):
        not_json = base64.urlsafe_b64encode(b"hello").decode("ascii").rstrip("=")
        with pytest.raises(JwtDecodeException):
            decode_jwt(f"{not_json}.{not_json}.sig")

    def test_non_object_segment_raises(self):
        # A segment that decodes to a JSON array, not an object.
        array_seg = base64.urlsafe_b64encode(b"[1, 2]").decode("ascii").rstrip("=")
        with pytest.raises(JwtDecodeException):
            decode_jwt(f"{array_seg}.{array_seg}.sig")


class TestFormatTimestampClaim:
    def test_formats_unix_timestamp(self):
        # 2021-01-01T00:00:00Z
        assert format_timestamp_claim(1609459200).startswith("2021-01-01T00:00:00")

    def test_non_number_returns_none(self):
        assert format_timestamp_claim("nope") is None

    def test_bool_returns_none(self):
        # bool is a subclass of int, but a boolean claim is not a timestamp.
        assert format_timestamp_claim(True) is None

    def test_none_returns_none(self):
        assert format_timestamp_claim(None) is None

    def test_out_of_range_returns_none(self):
        assert format_timestamp_claim(10 ** 30) is None


class TestHumanizedTimestampClaims:
    def test_extracts_known_claims(self):
        payload = {"exp": 1609459200, "iat": 1609455600, "sub": "x"}
        readable = humanized_timestamp_claims(payload)
        assert set(readable) == {"exp", "iat"}

    def test_ignores_non_timestamp_values(self):
        assert humanized_timestamp_claims({"exp": "soon"}) == {}

    def test_empty_payload(self):
        assert humanized_timestamp_claims({}) == {}

    def test_nbf_and_auth_time(self):
        payload = {"nbf": 1609459200, "auth_time": 1609459200}
        assert set(humanized_timestamp_claims(payload)) == {"nbf", "auth_time"}

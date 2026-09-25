"""Tests for the JWT decoder (inspection only, no signature verification)."""
from __future__ import annotations

import base64
import json

import pytest

from pybreeze.utils.exception.exception_tags import malformed_jwt_error
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
        with pytest.raises(JwtDecodeException, match=malformed_jwt_error):
            decode_jwt("only.two")

    def test_a_token_without_its_signature_part_is_refused_as_malformed(self):
        # Both parts decode; taken as three, the signature was read past the end
        header, payload, _signature = _make_jwt({"alg": "HS256"}, {"sub": "1"}).split(".")

        with pytest.raises(JwtDecodeException, match=malformed_jwt_error):
            decode_jwt(f"{header}.{payload}")

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

    def test_a_claim_before_1970_is_shown(self):
        # It was silently left out on Windows.
        assert format_timestamp_claim(-86400) == "1969-12-31T00:00:00+00:00"

    def test_not_a_number_returns_none(self):
        assert format_timestamp_claim(float("nan")) is None


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


def test_a_payload_nested_past_the_recursion_limit_is_a_decode_error():
    def segment(obj_text: str) -> str:
        return base64.urlsafe_b64encode(obj_text.encode("utf-8")).decode("ascii").rstrip("=")

    token = ".".join([segment('{"alg": "none"}'), segment("[" * 100000 + "]" * 100000), ""])
    with pytest.raises(JwtDecodeException):
        decode_jwt(token)


class TestATokenPastedWithSomethingAroundIt:
    """Bearer prefixes, quotes and line breaks come along when a token is copied."""

    @pytest.mark.parametrize("header", [{"alg": "none"}, {"alg": "ES256", "kid": "a"}, {"alg": "HS256"}])
    @pytest.mark.parametrize("wrap", ["Bearer {}", '"{}"', "Authorization: Bearer {}\n", "{}"])
    def test_the_token_inside_is_decoded(self, header, wrap):
        # "Bearer eyJ..." always failed; a quoted token failed or kept the quote in
        # its signature depending on the header's length
        token = _make_jwt(header, {"sub": "1"})

        decoded = decode_jwt(wrap.format(token))

        assert decoded.header == header
        assert decoded.signature == "sig"

    def test_a_token_wrapped_over_lines_is_joined(self):
        token = _make_jwt({"alg": "HS256"}, {"sub": "1", "name": "a long enough name"})

        decoded = decode_jwt(token[:20] + "\n" + token[20:40] + "\r\n  " + token[40:])

        assert decoded.payload == {"sub": "1", "name": "a long enough name"}

    @pytest.mark.parametrize("stray", ["!", "!!!!"])
    def test_a_segment_with_characters_outside_base64url_is_refused(self, stray):
        # Non-strict decoding dropped them and decoded what was left; four of
        # them leave the padding as it was, so only strict decoding refuses them
        token = _make_jwt({"alg": "HS256"}, {"sub": "1"})
        header, payload, signature = token.split(".")

        with pytest.raises(JwtDecodeException):
            decode_jwt(f"{header[:4]}{stray}{header[4:]}.{payload}.{signature}")

    def test_of_two_tokens_the_first_is_decoded(self):
        first = _make_jwt({"alg": "HS256"}, {"sub": "first"})
        second = _make_jwt({"alg": "HS256"}, {"sub": "second"})

        assert decode_jwt(f"Bearer {first}, then {second}").payload == {"sub": "first"}


class TestTheSegmentsAsShown:
    """The decoder keeps each segment's JSON text, and shows it as written."""

    @staticmethod
    def _raw_jwt(payload_text: str) -> str:
        encoded = base64.urlsafe_b64encode(payload_text.encode("utf-8")).decode("ascii").rstrip("=")
        return f"{_segment({'alg': 'none'})}.{encoded}.sig"

    def test_numbers_keep_their_text(self):
        from pybreeze.utils.jwt_tools.jwt_decoder import shown_json

        decoded = decode_jwt(self._raw_jwt('{"n": 1e400, "big": 12345678901234567890123.5}'))
        shown = shown_json(decoded.payload_json, decoded.payload)

        # json.dumps wrote Infinity, which is not JSON, and rounded the long number
        assert '"n": 1e400' in shown
        assert '"big": 12345678901234567890123.5' in shown

    def test_a_repeated_claim_falls_back_to_the_decoded_value(self):
        from pybreeze.utils.jwt_tools.jwt_decoder import shown_json

        decoded = decode_jwt(self._raw_jwt('{"a": 1, "a": 2}'))

        # Laid out as the text is when it is shown as written: four spaces a level
        assert shown_json(decoded.payload_json, decoded.payload) == '{\n    "a": 2\n}'

    def test_the_keys_are_sorted_unless_asked_not_to(self):
        from pybreeze.utils.jwt_tools.jwt_decoder import shown_json

        decoded = decode_jwt(self._raw_jwt('{"z": 1, "a": 2}'))

        assert shown_json(decoded.payload_json, decoded.payload).index('"a"') < \
            shown_json(decoded.payload_json, decoded.payload).index('"z"')
        unsorted = shown_json(decoded.payload_json, decoded.payload, sort_keys=False)
        assert unsorted.index('"z"') < unsorted.index('"a"')


class TestWhereTheTokenEnds:
    TOKEN = _make_jwt({"alg": "none"}, {"a": 1})

    def test_the_line_after_it_is_not_part_of_the_signature(self):
        # All whitespace went: the signature read "signextline"
        assert decode_jwt(self.TOKEN + "\nnext line").signature == "sig"

    def test_a_token_wrapped_across_lines_is_joined(self):
        wrapped = f'"{self.TOKEN[:20]}\n    {self.TOKEN[20:]}",'
        assert decode_jwt(wrapped).payload == {"a": 1}

    def test_a_fourth_segment_is_refused_not_dropped(self):
        with pytest.raises(JwtDecodeException, match="three"):
            decode_jwt(self.TOKEN + ".extra")

    def test_a_closing_full_stop_is_not_a_segment(self):
        assert decode_jwt(f"The token is {self.TOKEN}.").signature == "sig"


def test_a_header_whose_encoding_is_not_eyj_is_found_after_bearer():
    # '{ "alg"' encodes to "eyAi", '{\n' to "ewo": only "eyJ" was looked for
    header = base64.urlsafe_b64encode(b'{ "alg": "none"}').decode("ascii").rstrip("=")
    token = f"{header}.{_segment({'a': 1})}.s"

    assert decode_jwt(f"Bearer {token}").header == {"alg": "none"}

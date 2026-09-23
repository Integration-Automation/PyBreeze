"""Decode a JSON Web Token's header and payload for inspection.

API automation frequently carries bearer tokens; being able to see what a JWT
actually claims (issuer, subject, expiry) without pasting it into an external
website is a small but real convenience.

This decoder is purely for inspection: it base64url-decodes the header and
payload segments and does **not** verify the signature. It never trusts the
token for any security decision.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass

from pybreeze.utils.exception.exception_tags import (
    empty_jwt_error,
    jwt_segment_decode_error,
    malformed_jwt_error,
)
from pybreeze.utils.exception.exceptions import JwtDecodeException
from pybreeze.utils.json_format.json_process import pretty_json_or_none
from pybreeze.utils.json_format.view_safe import dumps_for_view
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.timestamp_tools.timestamp_converter import utc_from_epoch_seconds

# A JWT is three base64url segments joined by dots
_JWT_SEGMENT_COUNT = 3
# Standard claim names that hold Unix timestamps, shown as readable dates
_TIMESTAMP_CLAIMS = ("exp", "iat", "nbf", "auth_time")
# Matches a JWT-looking token anywhere in a larger text, such as the value of an
# ``Authorization: Bearer ...`` header. The signature segment may be empty.
JWT_TOKEN_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")


@dataclass
class DecodedJwt:
    """The inspectable parts of a JWT.

    :param header: decoded JOSE header (algorithm, type, ...)
    :param payload: decoded claims set
    :param signature: the raw (still-encoded) signature segment
    :param header_json: the header's JSON text as the token carries it
    :param payload_json: the payload's JSON text as the token carries it
    """

    header: dict
    payload: dict
    signature: str
    header_json: str = ""
    payload_json: str = ""


def shown_json(text: str, value: dict, *, sort_keys: bool = True) -> str:
    """A decoded segment laid out for display: its own *text*, numbers as written.

    ``json.dumps`` of the decoded *value* wrote ``1e400`` as ``Infinity``, which
    is not JSON, and a long number rounded. The decoded value stands in when
    the text is not one JSON Format accepts (a claim repeated, ``NaN``), or
    was not kept.
    """
    return pretty_json_or_none(text, sort_keys=sort_keys) or dumps_for_view(value, indent=4, sort_keys=sort_keys)


def _decode_segment(segment: str) -> tuple[dict, str]:
    """Base64url-decode one JWT segment into a JSON object.

    :param segment: a single base64url-encoded segment
    :return: the decoded JSON object, and its JSON text
    :raises JwtDecodeException: when the segment is not valid base64url/JSON
        or does not decode to a JSON object
    """
    # base64url omits padding; restore it so the stdlib decoder accepts the input.
    padding = "=" * (-len(segment) % 4)
    try:
        # Strict: urlsafe_b64decode drops characters outside the alphabet after
        # the padding was worked out from a length that counted them, so a
        # stray quote decoded or failed depending on the segment's length
        raw = base64.b64decode(segment + padding, altchars=b"-_", validate=True)
        text = raw.decode("utf-8")
        decoded = json.loads(text)
    # binascii.Error and UnicodeDecodeError both derive from ValueError; a
    # payload nested past the recursion limit raises RecursionError.
    except (ValueError, RecursionError) as error:
        pybreeze_logger.error(jwt_segment_decode_error)
        raise JwtDecodeException(jwt_segment_decode_error) from error
    if not isinstance(decoded, dict):
        raise JwtDecodeException(jwt_segment_decode_error)
    return decoded, text


def decode_jwt(token: str) -> DecodedJwt:
    """Decode a JWT's header and payload without verifying its signature.

    :param token: the compact JWT string ``header.payload.signature``, or
        text holding one (``Bearer <token>``, a quoted or wrapped token)
    :return: the decoded parts
    :raises JwtDecodeException: when the token is empty or not three segments,
        or a segment cannot be decoded
    """
    stripped = token.strip()
    if not stripped:
        pybreeze_logger.error(empty_jwt_error)
        raise JwtDecodeException(empty_jwt_error)

    segments = _the_token(stripped).split(".")
    if len(segments) != _JWT_SEGMENT_COUNT:
        pybreeze_logger.error(malformed_jwt_error)
        raise JwtDecodeException(malformed_jwt_error)

    header, header_json = _decode_segment(segments[0])
    payload, payload_json = _decode_segment(segments[1])
    return DecodedJwt(header=header, payload=payload, signature=segments[2],
                      header_json=header_json, payload_json=payload_json)


def _the_token(text: str) -> str:
    """The compact token in *text*, as pasted.

    A token is often copied with something around it: ``Bearer`` from an
    ``Authorization`` header, the quotes of a JSON string, line breaks where it
    wrapped. Those used to reach the decoder, and ``Bearer eyJ...`` always failed.
    """
    compact = "".join(text.split())
    if JWT_TOKEN_RE.fullmatch(compact):
        return compact
    found = find_tokens(compact)
    return found[0] if found else compact


def find_tokens(text: str) -> list[str]:
    """Find every JWT-looking token in *text*, in order and without repeats.

    Used to spot a token inside something larger — a response body, an
    ``Authorization`` header — so it can be handed to the decoder. A match only
    *looks* like a JWT; decoding it may still fail.

    :param text: the text to scan
    :return: the distinct tokens found, in the order they appeared
    """
    tokens: list[str] = []
    for token in JWT_TOKEN_RE.findall(text):
        if token not in tokens:
            tokens.append(token)
    return tokens


def format_timestamp_claim(value: object) -> str | None:
    """Render a Unix-timestamp claim as an ISO UTC string, or ``None``.

    :param value: a claim value that may be a Unix timestamp
    :return: the formatted UTC time, or ``None`` when *value* is not a timestamp
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        # Not fromtimestamp: on Windows it refused claims before 1970
        return utc_from_epoch_seconds(value).isoformat()
    except (OverflowError, ValueError):
        return None


def humanized_timestamp_claims(payload: dict) -> dict[str, str]:
    """Return readable UTC strings for the standard timestamp claims present.

    :param payload: the decoded claim set
    :return: ``claim_name -> ISO UTC time`` for each recognised timestamp claim
    """
    readable: dict[str, str] = {}
    for claim in _TIMESTAMP_CLAIMS:
        formatted = format_timestamp_claim(payload.get(claim))
        if formatted is not None:
            readable[claim] = formatted
    return readable

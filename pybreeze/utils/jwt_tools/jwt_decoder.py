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
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from pybreeze.utils.exception.exception_tags import (
    empty_jwt_error,
    jwt_segment_decode_error,
    malformed_jwt_error,
)
from pybreeze.utils.exception.exceptions import JwtDecodeException
from pybreeze.utils.logging.logger import pybreeze_logger

# A JWT is three base64url segments joined by dots
_JWT_SEGMENT_COUNT = 3
# Standard claim names that hold Unix timestamps, shown as readable dates
_TIMESTAMP_CLAIMS = ("exp", "iat", "nbf", "auth_time")


@dataclass
class DecodedJwt:
    """The inspectable parts of a JWT.

    :param header: decoded JOSE header (algorithm, type, ...)
    :param payload: decoded claims set
    :param signature: the raw (still-encoded) signature segment
    """

    header: dict
    payload: dict
    signature: str


def _decode_segment(segment: str) -> dict:
    """Base64url-decode one JWT segment into a JSON object.

    :param segment: a single base64url-encoded segment
    :return: the decoded JSON object
    :raises JwtDecodeException: when the segment is not valid base64url/JSON
        or does not decode to a JSON object
    """
    # base64url omits padding; restore it so the stdlib decoder accepts the input.
    padding = "=" * (-len(segment) % 4)
    try:
        raw = base64.urlsafe_b64decode(segment + padding)
        decoded = json.loads(raw.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError) as error:
        pybreeze_logger.error(jwt_segment_decode_error)
        raise JwtDecodeException(jwt_segment_decode_error) from error
    if not isinstance(decoded, dict):
        raise JwtDecodeException(jwt_segment_decode_error)
    return decoded


def decode_jwt(token: str) -> DecodedJwt:
    """Decode a JWT's header and payload without verifying its signature.

    :param token: the compact JWT string ``header.payload.signature``
    :return: the decoded parts
    :raises JwtDecodeException: when the token is empty or not three segments,
        or a segment cannot be decoded
    """
    stripped = token.strip()
    if not stripped:
        pybreeze_logger.error(empty_jwt_error)
        raise JwtDecodeException(empty_jwt_error)

    segments = stripped.split(".")
    if len(segments) != _JWT_SEGMENT_COUNT:
        pybreeze_logger.error(malformed_jwt_error)
        raise JwtDecodeException(malformed_jwt_error)

    header = _decode_segment(segments[0])
    payload = _decode_segment(segments[1])
    return DecodedJwt(header=header, payload=payload, signature=segments[2])


def format_timestamp_claim(value: object) -> str | None:
    """Render a Unix-timestamp claim as an ISO UTC string, or ``None``.

    :param value: a claim value that may be a Unix timestamp
    :return: the formatted UTC time, or ``None`` when *value* is not a timestamp
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
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

"""Convert between Unix epoch values and ISO-8601 date-times.

Requests, tokens and log lines constantly mix epoch seconds, epoch milliseconds
and ISO date-times. This module accepts any of those forms and reports all of
them, so an automation engineer never has to reach for an external converter.

All output times are in UTC; the module never depends on the local time zone,
which keeps the conversions deterministic and testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pybreeze.utils.exception.exception_tags import (
    empty_timestamp_error,
    unrecognized_timestamp_error,
)
from pybreeze.utils.exception.exceptions import TimestampParseException
from pybreeze.utils.logging.logger import pybreeze_logger

# Values at or above this magnitude are treated as milliseconds, not seconds.
# Epoch seconds around the year 2020 are ~1.6e9; the same instant in
# milliseconds is ~1.6e12, so 1e11 cleanly separates the two for any plausible
# modern timestamp.
_MILLISECONDS_THRESHOLD = 10 ** 11
# Milliseconds per second
_MS_PER_SECOND = 1000


@dataclass(frozen=True)
class TimestampResult:
    """Every representation of one instant.

    :param epoch_seconds: whole Unix seconds
    :param epoch_millis: whole Unix milliseconds
    :param iso_utc: ISO-8601 string in UTC
    """

    epoch_seconds: int
    epoch_millis: int
    iso_utc: str


def detect_epoch_unit(value: float) -> str:
    """Return ``"ms"`` or ``"s"`` for an epoch *value* by magnitude.

    :param value: an epoch number whose unit is unknown
    :return: ``"ms"`` when the value looks like milliseconds, else ``"s"``
    """
    return "ms" if abs(value) >= _MILLISECONDS_THRESHOLD else "s"


def _from_epoch(value: float) -> datetime:
    """Build a UTC datetime from an epoch number, auto-detecting its unit."""
    seconds = value / _MS_PER_SECOND if detect_epoch_unit(value) == "ms" else value
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        pybreeze_logger.error(unrecognized_timestamp_error)
        raise TimestampParseException(unrecognized_timestamp_error) from error


def _from_iso(text: str) -> datetime:
    """Parse an ISO-8601 string (accepting a trailing ``Z``) into a UTC datetime."""
    # datetime.fromisoformat does not accept the 'Z' suffix before Python 3.11.
    normalised = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError as error:
        pybreeze_logger.error(unrecognized_timestamp_error)
        raise TimestampParseException(unrecognized_timestamp_error) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse(text: str) -> datetime:
    """Parse *text* as an epoch number or an ISO date-time into a UTC datetime."""
    stripped = text.strip()
    if not stripped:
        pybreeze_logger.error(empty_timestamp_error)
        raise TimestampParseException(empty_timestamp_error)
    try:
        return _from_epoch(float(stripped))
    except ValueError:
        # Not a plain number; fall through to ISO parsing.
        return _from_iso(stripped)


def convert_timestamp(text: str) -> TimestampResult:
    """Convert an epoch value or ISO date-time into every representation.

    :param text: an epoch number (seconds or milliseconds) or an ISO-8601 string
    :return: the same instant as epoch seconds, epoch milliseconds and ISO UTC
    :raises TimestampParseException: when *text* is empty or unrecognised
    """
    moment = _parse(text)
    epoch_seconds = int(moment.timestamp())
    return TimestampResult(
        epoch_seconds=epoch_seconds,
        epoch_millis=epoch_seconds * _MS_PER_SECOND,
        iso_utc=moment.isoformat(),
    )

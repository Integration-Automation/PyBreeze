"""Convert between Unix epoch values and ISO-8601 date-times.

Requests, tokens and log lines constantly mix epoch seconds, epoch milliseconds
and ISO date-times. This module accepts any of those forms and reports all of
them, so an automation engineer never has to reach for an external converter.

All output times are in UTC; the module never depends on the local time zone,
which keeps the conversions deterministic and testable.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import MAX_EMAX, MIN_EMIN, Decimal, InvalidOperation, localcontext

from pybreeze.utils.exception.exception_tags import (
    empty_timestamp_error,
    unrecognized_timestamp_error,
)
from pybreeze.utils.exception.exceptions import TimestampParseException
from pybreeze.utils.logging.logger import pybreeze_logger

# An epoch's unit, by magnitude: the same instant around 2020 is ~1.6e9 in
# seconds, ~1.6e12 in milliseconds, ~1.6e15 in microseconds and ~1.6e18 in
# nanoseconds, so each thousandfold step from 1e11 separates two of them for
# any plausible timestamp. (Microseconds and nanoseconds, from time.time_ns()
# or Go's UnixNano, used to be read as milliseconds and overflow.)
_MILLISECONDS_THRESHOLD = 10 ** 11
_MICROSECONDS_THRESHOLD = 10 ** 14
_NANOSECONDS_THRESHOLD = 10 ** 17
# How many of each unit make a second
_PER_SECOND = {"s": 1, "ms": 1000, "us": 10 ** 6, "ns": 10 ** 9}
# Milliseconds per second
_MS_PER_SECOND = 1000
# The Unix epoch, in UTC
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
# Past this many digits before the point, an epoch is outside the years
# datetime can hold in any unit; a longer decimal is refused before any
# arithmetic, which would overflow (1e999999999) or build a huge integer
_MAX_EPOCH_DIGITS = 30
# Digits a decimal epoch is worked out to: enough for the largest one taken,
# in microseconds, with its fraction
_DECIMAL_PRECISION = 60
# Minutes in an hour, the most a zone offset's minutes may be
_MINUTES_PER_HOUR = 60


@dataclass(frozen=True)
class TimestampResult:
    """Every representation of one instant.

    :param epoch_seconds: whole Unix seconds, rounded down (toward the past)
    :param epoch_millis: whole Unix milliseconds, rounded down
    :param iso_utc: ISO-8601 string in UTC
    """

    epoch_seconds: int
    epoch_millis: int
    iso_utc: str


def detect_epoch_unit(value: float) -> str:
    """Return ``"s"``, ``"ms"``, ``"us"`` or ``"ns"`` for an epoch *value* by magnitude.

    :param value: an epoch number whose unit is unknown
    :return: the unit the value's size suggests
    """
    magnitude = abs(value)
    if magnitude >= _NANOSECONDS_THRESHOLD:
        return "ns"
    if magnitude >= _MICROSECONDS_THRESHOLD:
        return "us"
    return "ms" if magnitude >= _MILLISECONDS_THRESHOLD else "s"


def utc_from_epoch_seconds(seconds: float) -> datetime:
    """The UTC instant *seconds* after (or before) the Unix epoch.

    Not ``datetime.fromtimestamp``: on Windows it goes through the C runtime,
    which refuses anything more than a few hours before 1970 with ``OSError``.

    :raises OverflowError: outside the years datetime can hold, or infinite
    :raises ValueError: not a number (NaN)
    """
    return _EPOCH + timedelta(seconds=seconds)


def _decimal_microseconds(value: Decimal) -> int:
    """Whole microseconds in the decimal epoch *value*, rounded toward the past.

    :raises OverflowError: infinite or NaN, or too long to be a date
    """
    if not value.is_finite():
        raise OverflowError("not a finite epoch")
    if value and value.adjusted() >= _MAX_EPOCH_DIGITS:
        raise OverflowError("epoch out of range")
    with localcontext() as context:
        context.prec = _DECIMAL_PRECISION
        # A tiny fraction (1e-999999999) is not rounded away to zero
        context.Emax, context.Emin = MAX_EMAX, MIN_EMIN
        return math.floor(value * 10 ** 6 / _PER_SECOND[detect_epoch_unit(value)])


def _from_epoch(value: int | Decimal) -> datetime:
    """Build a UTC datetime from an epoch number, auto-detecting its unit.

    The number is divided exactly, to the microsecond, rounding toward the
    past: as a float, a nanosecond epoch has lost its last digits already, and
    ``timedelta`` rounds a float's fraction to the nearest microsecond, so
    ``0.0000009`` came out a microsecond after the epoch.
    """
    try:
        if isinstance(value, int):
            microseconds = value * 10 ** 6 // _PER_SECOND[detect_epoch_unit(value)]
        else:
            microseconds = _decimal_microseconds(value)
        return _EPOCH + timedelta(microseconds=microseconds)
    except (OverflowError, ValueError) as error:
        pybreeze_logger.error(unrecognized_timestamp_error)
        raise TimestampParseException(unrecognized_timestamp_error) from error


# ISO-8601 as tools write it, parsed the same way on every Python this runs on:
# before 3.11 datetime.fromisoformat took only what isoformat() writes, and
# refused "Z", "+0000", "+08", fractions of other than 3 or 6 digits (Go and
# Kubernetes write 9) and the basic format 20240101T000000Z. A lower-case "z"
# was refused on every version.
_ISO_RE = re.compile(
    r"(?P<year>\d{4})-?(?P<month>\d{2})-?(?P<day>\d{2})"
    r"(?:[Tt ](?P<hour>\d{2})(?::?(?P<minute>\d{2})(?::?(?P<second>\d{2})(?:[.,](?P<fraction>\d+))?)?)?"
    r"(?P<zone>[Zz]|[+-]\d{2}(?::?\d{2})?)?)?"
)


def _zone(text: str | None) -> timezone:
    """The time zone an ISO-8601 designator names; none means UTC."""
    if not text or text in ("Z", "z"):
        return timezone.utc
    sign = -1 if text[0] == "-" else 1
    digits = text[1:].replace(":", "")
    minutes = int(digits[2:4] or 0)
    if minutes >= _MINUTES_PER_HOUR:
        # +05:99 used to be taken as +06:39
        raise ValueError(f"zone offset minutes out of range: {text}")
    return timezone(sign * timedelta(hours=int(digits[:2]), minutes=minutes))


def _iso_match(text: str) -> datetime | None:
    """*text* as an ISO-8601 date or date-time in UTC, or ``None`` when it is not one.

    :raises ValueError: a field out of range (month 13, hour 25)
    :raises OverflowError: moving it to UTC leaves the years datetime can hold
    """
    match = _ISO_RE.fullmatch(text)
    if match is None:
        return None
    fields = match.groupdict()
    fraction = (fields["fraction"] or "")[:6].ljust(6, "0")
    moment = datetime(
        int(fields["year"]), int(fields["month"]), int(fields["day"]),
        int(fields["hour"] or 0), int(fields["minute"] or 0), int(fields["second"] or 0),
        int(fraction), tzinfo=_zone(fields["zone"]))
    return moment.astimezone(timezone.utc)


def _from_iso(text: str) -> datetime:
    """Parse an ISO-8601 string into a UTC datetime; no offset means UTC."""
    try:
        parsed = _iso_match(text)
        if parsed is not None:
            return parsed
        # Anything else fromisoformat takes on this Python (3.11+ reads more)
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        # Moving 0001-01-01 +01:00 (or 9999-12-31 -01:00) to UTC leaves the
        # range datetime can hold: OverflowError, not ValueError.
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        pybreeze_logger.error(unrecognized_timestamp_error)
        raise TimestampParseException(unrecognized_timestamp_error) from error


def _eight_digit_date(text: str) -> datetime | None:
    """*text* as a ``YYYYMMDD`` date, when it is eight digits that make one.

    20240101 used to be read as seconds, landing in August 1970.
    """
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return _iso_match(text)
    except ValueError:
        return None


def _parse(text: str) -> datetime:
    """Parse *text* as an epoch number or an ISO date-time into a UTC datetime."""
    stripped = text.strip()
    if not stripped:
        pybreeze_logger.error(empty_timestamp_error)
        raise TimestampParseException(empty_timestamp_error)
    date = _eight_digit_date(stripped)
    if date is not None:
        return date
    for number_type in (int, Decimal):
        try:
            number = number_type(stripped)
        except (ValueError, InvalidOperation):
            continue
        return _from_epoch(number)
    # Not a plain number; fall through to ISO parsing.
    return _from_iso(stripped)


def convert_timestamp(text: str) -> TimestampResult:
    """Convert an epoch value or ISO date-time into every representation.

    :param text: an epoch number (seconds or milliseconds) or an ISO-8601 string
    :return: the same instant as epoch seconds, epoch milliseconds and ISO UTC
    :raises TimestampParseException: when *text* is empty or unrecognised
    """
    moment = _parse(text)
    # From the instant itself, not from whole seconds: milliseconds kept their
    # sub-second part only as zeros, and int() moved an instant before 1970
    # toward zero -- -1.5 s became -1 rather than -2.
    epoch_millis = (moment - _EPOCH) // timedelta(milliseconds=1)
    return TimestampResult(
        epoch_seconds=epoch_millis // _MS_PER_SECOND,
        epoch_millis=epoch_millis,
        iso_utc=moment.isoformat(),
    )

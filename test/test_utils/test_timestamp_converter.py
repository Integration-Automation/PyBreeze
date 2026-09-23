"""Tests for the epoch / ISO-8601 timestamp converter."""
from __future__ import annotations

import pytest

from pybreeze.utils.exception.exceptions import TimestampParseException
from pybreeze.utils.timestamp_tools.timestamp_converter import (
    convert_timestamp,
    detect_epoch_unit,
)

# 2021-01-01T00:00:00Z
_EPOCH_2021 = 1609459200


class TestDetectEpochUnit:
    def test_seconds(self):
        assert detect_epoch_unit(_EPOCH_2021) == "s"

    def test_milliseconds(self):
        assert detect_epoch_unit(_EPOCH_2021 * 1000) == "ms"

    def test_zero_is_seconds(self):
        assert detect_epoch_unit(0) == "s"


class TestConvertFromEpoch:
    def test_seconds_input(self):
        result = convert_timestamp(str(_EPOCH_2021))
        assert result.epoch_seconds == _EPOCH_2021
        assert result.iso_utc.startswith("2021-01-01T00:00:00")

    def test_milliseconds_input(self):
        result = convert_timestamp(str(_EPOCH_2021 * 1000))
        assert result.epoch_seconds == _EPOCH_2021
        assert result.epoch_millis == _EPOCH_2021 * 1000

    def test_float_seconds(self):
        result = convert_timestamp("1609459200.0")
        assert result.epoch_seconds == _EPOCH_2021

    def test_millis_output_is_seconds_times_1000(self):
        result = convert_timestamp(str(_EPOCH_2021))
        assert result.epoch_millis == result.epoch_seconds * 1000

    def test_whitespace_trimmed(self):
        assert convert_timestamp(f"  {_EPOCH_2021}  ").epoch_seconds == _EPOCH_2021


class TestConvertFromIso:
    def test_iso_with_z(self):
        assert convert_timestamp("2021-01-01T00:00:00Z").epoch_seconds == _EPOCH_2021

    def test_iso_with_offset(self):
        # +00:00 offset is the same instant as Z.
        assert convert_timestamp("2021-01-01T00:00:00+00:00").epoch_seconds == _EPOCH_2021

    def test_iso_naive_treated_as_utc(self):
        assert convert_timestamp("2021-01-01T00:00:00").epoch_seconds == _EPOCH_2021

    def test_iso_with_nonzero_offset(self):
        # 01:00 at +01:00 is midnight UTC.
        assert convert_timestamp("2021-01-01T01:00:00+01:00").epoch_seconds == _EPOCH_2021

    def test_iso_date_only(self):
        assert convert_timestamp("2021-01-01").epoch_seconds == _EPOCH_2021

    def test_round_trip(self):
        result = convert_timestamp(str(_EPOCH_2021))
        assert convert_timestamp(result.iso_utc).epoch_seconds == _EPOCH_2021


class TestConvertErrors:
    def test_empty_raises(self):
        with pytest.raises(TimestampParseException):
            convert_timestamp("   ")

    def test_garbage_raises(self):
        with pytest.raises(TimestampParseException):
            convert_timestamp("not-a-timestamp")

    def test_out_of_range_epoch_raises(self):
        with pytest.raises(TimestampParseException):
            convert_timestamp("1" * 40)


class TestInstantsDatetimeCannotHold:
    @pytest.mark.parametrize("text", ["0001-01-01T00:00:00+01:00", "9999-12-31T23:30:00-01:00"])
    def test_a_date_that_leaves_the_range_in_utc_is_a_parse_error(self, text):
        # In UTC these fall before year 1 or after year 9999: OverflowError, not ValueError.
        with pytest.raises(TimestampParseException):
            convert_timestamp(text)


class TestSubSecondPrecision:
    def test_milliseconds_keep_their_sub_second_part(self):
        result = convert_timestamp("1700000000123")

        assert result.epoch_millis == 1700000000123
        assert result.epoch_seconds == 1700000000

    def test_an_instant_before_1970_rounds_down_not_toward_zero(self):
        result = convert_timestamp("-1.5")

        assert result.epoch_millis == -1500
        assert result.epoch_seconds == -2

    @pytest.mark.parametrize("text,iso", [
        ("-86400", "1969-12-31T00:00:00+00:00"),
        ("-315619200", "1960-01-01T00:00:00+00:00"),
    ])
    def test_a_day_or_more_before_1970_converts_on_every_platform(self, text, iso):
        # fromtimestamp() refused these on Windows: "not a recognized epoch number"
        assert convert_timestamp(text).iso_utc == iso

    def test_an_iso_time_with_milliseconds_keeps_them(self):
        assert convert_timestamp("2021-01-01T00:00:00.250Z").epoch_millis == 1609459200250

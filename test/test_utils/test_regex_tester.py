"""Tests for the regular expression tester."""
from __future__ import annotations

import pytest

from pybreeze.utils.exception.exceptions import RegexTesterException
from pybreeze.utils.regex_tools.regex_tester import (
    available_flags,
    build_flags,
    compile_pattern,
    find_matches,
)


class TestBuildFlags:
    def test_no_flags(self):
        assert build_flags([]) == 0

    def test_ignorecase(self):
        import re
        assert build_flags(["IGNORECASE"]) & re.IGNORECASE

    def test_multiple(self):
        import re
        combined = build_flags(["IGNORECASE", "DOTALL"])
        assert combined & re.IGNORECASE and combined & re.DOTALL

    def test_unknown_ignored(self):
        assert build_flags(["NOPE"]) == 0

    def test_available_flags(self):
        assert set(available_flags()) == {"IGNORECASE", "MULTILINE", "DOTALL", "VERBOSE"}


class TestCompilePattern:
    def test_valid(self):
        assert compile_pattern(r"\d+").pattern == r"\d+"

    def test_empty_raises(self):
        with pytest.raises(RegexTesterException):
            compile_pattern("")

    def test_invalid_raises(self):
        with pytest.raises(RegexTesterException):
            compile_pattern("(")


class TestFindMatches:
    def test_simple(self):
        matches = find_matches(r"\d+", "a1 b22 c333")
        assert [m.matched_text for m in matches] == ["1", "22", "333"]

    def test_offsets(self):
        matches = find_matches(r"b", "abc")
        assert (matches[0].start, matches[0].end) == (1, 2)

    def test_numbered_groups(self):
        matches = find_matches(r"(\d)(\d)", "12")
        assert matches[0].groups == ["1", "2"]

    def test_named_groups(self):
        matches = find_matches(r"(?P<year>\d{4})", "2021")
        assert matches[0].named_groups == {"year": "2021"}

    def test_no_matches(self):
        assert find_matches(r"z", "abc") == []

    def test_ignorecase_flag(self):
        assert len(find_matches(r"abc", "ABC abc", ["IGNORECASE"])) == 2

    def test_multiline_flag(self):
        matches = find_matches(r"^\d", "1\n2\n3", ["MULTILINE"])
        assert len(matches) == 3

    def test_dotall_flag(self):
        assert find_matches(r"a.b", "a\nb", ["DOTALL"])[0].matched_text == "a\nb"

    def test_invalid_pattern_raises(self):
        with pytest.raises(RegexTesterException):
            find_matches("(", "text")

    def test_empty_pattern_raises(self):
        with pytest.raises(RegexTesterException):
            find_matches("", "text")

    def test_group_that_did_not_match_is_none(self):
        matches = find_matches(r"(a)|(b)", "a")
        assert matches[0].groups == ["a", None]

    def test_match_cap(self):
        from pybreeze.utils.regex_tools import regex_tester
        # More potential matches than the cap; result is capped, not unbounded.
        text = "a" * (regex_tester._MAX_MATCHES + 50)
        assert len(find_matches("a", text)) == regex_tester._MAX_MATCHES

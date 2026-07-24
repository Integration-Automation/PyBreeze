"""Test a regular expression against sample text and report the matches.

Automation work leans on regexes constantly — extracting values from responses,
building element locators, parsing log output. Being able to try a pattern
against real sample text inside the IDE shortens that loop.

This module is pure logic: it compiles the pattern and reports matches; it never
touches the UI or the network.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from pybreeze.utils.exception.exception_tags import (
    empty_regex_pattern_error,
    invalid_regex_pattern_error,
)
from pybreeze.utils.exception.exceptions import RegexTesterException
from pybreeze.utils.logging.logger import pybreeze_logger

# Cap on reported matches so a pathological pattern cannot flood the UI.
_MAX_MATCHES = 1000

# Human-facing flag names mapped to their ``re`` values.
_FLAG_NAMES: dict[str, int] = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "VERBOSE": re.VERBOSE,
}


@dataclass
class MatchResult:
    """One regex match and its captured groups.

    :param matched_text: the full matched substring
    :param start: match start offset in the text
    :param end: match end offset in the text
    :param groups: numbered capture groups (``None`` for groups that did not match)
    :param named_groups: named capture groups by name
    """

    matched_text: str
    start: int
    end: int
    groups: list[str | None] = field(default_factory=list)
    named_groups: dict[str, str | None] = field(default_factory=dict)


def available_flags() -> list[str]:
    """Return the supported flag names."""
    return list(_FLAG_NAMES)


def build_flags(flag_names: list[str] | set[str]) -> int:
    """Combine flag names into a single ``re`` flags integer.

    :param flag_names: names from :func:`available_flags` (unknown names ignored)
    :return: the combined flags value
    """
    combined = 0
    for name in flag_names:
        combined |= _FLAG_NAMES.get(name, 0)
    return combined


def compile_pattern(pattern: str, flag_names: list[str] | set[str] | None = None) -> re.Pattern:
    """Compile *pattern*, raising a friendly error on failure.

    :param pattern: the regular expression
    :param flag_names: optional flag names to apply
    :return: the compiled pattern
    :raises RegexTesterException: when the pattern is empty or invalid
    """
    if pattern == "":
        pybreeze_logger.error(empty_regex_pattern_error)
        raise RegexTesterException(empty_regex_pattern_error)
    try:
        return re.compile(pattern, build_flags(flag_names or []))
    except re.error as error:
        message = invalid_regex_pattern_error.format(detail=str(error))
        pybreeze_logger.error(message)
        raise RegexTesterException(message) from error


def find_matches(
        pattern: str, text: str,
        flag_names: list[str] | set[str] | None = None) -> list[MatchResult]:
    """Find every match of *pattern* in *text*.

    :param pattern: the regular expression
    :param text: the sample text to search
    :param flag_names: optional flag names to apply
    :return: the matches, up to an internal cap
    :raises RegexTesterException: when the pattern is empty or invalid
    """
    compiled = compile_pattern(pattern, flag_names)
    results: list[MatchResult] = []
    for match in compiled.finditer(text):
        results.append(
            MatchResult(
                matched_text=match.group(0),
                start=match.start(),
                end=match.end(),
                groups=list(match.groups()),
                named_groups=dict(match.groupdict()),
            )
        )
        if len(results) >= _MAX_MATCHES:
            break
    return results

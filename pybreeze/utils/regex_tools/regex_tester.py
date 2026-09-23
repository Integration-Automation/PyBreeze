"""Test a regular expression against sample text and report the matches.

Automation work leans on regexes constantly — extracting values from responses,
building element locators, parsing log output. Being able to try a pattern
against real sample text inside the IDE shortens that loop.

This module is pure logic: it compiles the pattern and reports matches; it never
touches the UI or the network.
"""
from __future__ import annotations

import multiprocessing
import re
from dataclasses import dataclass, field

from pybreeze.utils.exception.exception_tags import (
    empty_regex_pattern_error,
    invalid_regex_pattern_error,
    regex_timeout_error,
    regex_worker_error,
)
from pybreeze.utils.exception.exceptions import RegexTesterException
from pybreeze.utils.logging.logger import pybreeze_logger

# Cap on reported matches, so a pattern that matches everywhere cannot flood
# the output. It bounds how many matches are reported, not how long one takes.
_MAX_MATCHES = 1000

# How long a pattern may run, in its own process, before it is stopped.
MATCH_TIMEOUT_SECONDS = 5.0

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
    # OverflowError: a repeat count past what re takes (a{4294967296});
    # RecursionError: groups nested deeper than the compiler goes. Either
    # escaped the worker, and the tab stayed on "Running the pattern..."
    except (re.error, OverflowError, RecursionError) as error:
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


def find_matches_bounded(
        pattern: str, text: str, flag_names: list[str] | set[str] | None = None,
        timeout_seconds: float = MATCH_TIMEOUT_SECONDS) -> list[MatchResult]:
    """Like :func:`find_matches`, in a separate process stopped after *timeout_seconds*.

    Python's ``re`` cannot be interrupted once a match attempt starts, and a
    pattern with nested repetition backtracks exponentially: ``(a+)+$`` against
    26 ``a``'s and a ``b`` takes seconds, and each further character doubles it.
    Only a process can be stopped mid-match. The pattern is compiled here first,
    so a malformed one is reported without starting anything.

    :param pattern: the regular expression
    :param text: the sample text to search
    :param flag_names: optional flag names to apply
    :param timeout_seconds: how long the pattern may run, process start included
    :return: the matches, up to an internal cap
    :raises RegexTesterException: when the pattern is empty or invalid, or ran too long
    """
    compile_pattern(pattern, flag_names)
    context = multiprocessing.get_context("spawn")
    receiving, sending = context.Pipe(duplex=False)
    process = context.Process(
        target=_matches_into_pipe, args=(sending, pattern, text, list(flag_names or [])),
        daemon=True)
    process.start()
    sending.close()
    try:
        if not receiving.poll(timeout_seconds):
            message = regex_timeout_error.format(seconds=timeout_seconds)
            pybreeze_logger.error(message)
            raise RegexTesterException(message)
        kind, value = receiving.recv()
    except (EOFError, OSError) as error:
        message = regex_worker_error.format(detail=repr(error))
        pybreeze_logger.error(message)
        raise RegexTesterException(message) from error
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=_JOIN_SECONDS)
        receiving.close()
    if kind == "error":
        raise RegexTesterException(value)
    return value


# How long to wait for the worker process to go once it is done or stopped
_JOIN_SECONDS = 2.0


def _matches_into_pipe(sending, pattern: str, text: str, flag_names: list[str]) -> None:
    """Run :func:`find_matches` in the worker process and send back what happened."""
    try:
        sending.send(("matches", find_matches(pattern, text, flag_names)))
    except RegexTesterException as error:
        sending.send(("error", str(error)))
    finally:
        sending.close()


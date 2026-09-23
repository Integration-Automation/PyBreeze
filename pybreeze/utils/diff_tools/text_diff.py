"""Produce a line-by-line diff between two pieces of text.

Comparing an expected response with an actual one is a daily automation task.
This wraps the standard library's ``difflib`` so the IDE can show a unified diff
and a one-line summary of how many lines were added or removed.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass

# Labels shown in the unified diff header for the two inputs
_LEFT_LABEL = "expected"
_RIGHT_LABEL = "actual"
# Lines of unchanged context kept around each change in the unified diff
_CONTEXT_LINES = 3


@dataclass(frozen=True)
class DiffSummary:
    """Counts describing how two texts differ.

    :param added: lines present in the right text but not the left
    :param removed: lines present in the left text but not the right
    :param is_equal: whether the two texts are identical
    """

    added: int
    removed: int
    is_equal: bool


def _split_lines(text: str) -> list[str]:
    """Split *text* into lines, keeping a stable count for empty input."""
    return text.splitlines()


def unified_diff(
        left: str, right: str,
        left_label: str = _LEFT_LABEL, right_label: str = _RIGHT_LABEL) -> str:
    """Return a unified diff between *left* and *right*.

    :param left: the first (expected) text
    :param right: the second (actual) text
    :param left_label: header label for the first text
    :param right_label: header label for the second text
    :return: the unified diff text (empty when the inputs are identical)
    """
    diff_lines = difflib.unified_diff(
        _split_lines(left),
        _split_lines(right),
        fromfile=left_label,
        tofile=right_label,
        lineterm="",
        n=_CONTEXT_LINES,
    )
    return "\n".join(diff_lines)


def diff_summary(left: str, right: str) -> DiffSummary:
    """Summarise how *left* and *right* differ, line by line.

    The counts come from the same line matching ``unified_diff`` uses, so they
    agree with the diff shown beside them. ``difflib.ndiff`` also compared the
    characters inside every changed line, which the counts never needed: two
    3000-line texts with every line changed took over a minute, on the UI
    thread.

    :param left: the first (expected) text
    :param right: the second (actual) text
    :return: the counts of added and removed lines and whether they are equal
    """
    matcher = difflib.SequenceMatcher(None, _split_lines(left), _split_lines(right))
    added = 0
    removed = 0
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed += left_end - left_start
        if tag in ("replace", "insert"):
            added += right_end - right_start
    return DiffSummary(added=added, removed=removed, is_equal=left == right)

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

    :param left: the first (expected) text
    :param right: the second (actual) text
    :return: the counts of added and removed lines and whether they are equal
    """
    left_lines = _split_lines(left)
    right_lines = _split_lines(right)
    added = 0
    removed = 0
    for line in difflib.ndiff(left_lines, right_lines):
        if line.startswith("+ "):
            added += 1
        elif line.startswith("- "):
            removed += 1
    return DiffSummary(added=added, removed=removed, is_equal=left == right)

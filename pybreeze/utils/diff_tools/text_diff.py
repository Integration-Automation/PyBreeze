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
# diff's own note under a last line that has no newline
_NO_NEWLINE_MARK = "\\ No newline at end of file"


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


def _line_lists(left: str, right: str) -> tuple[list[str], list[str]]:
    """The two texts as the lists of lines to compare, each line ending in ``\\n``.

    Lines are compared without their endings. Only when that finds nothing
    while the texts still differ -- a final newline, or ``\\r\\n`` against
    ``\\n`` -- are the real endings kept: the summary called such texts
    different, and the diff showed nothing.
    """
    left_lines, right_lines = left.splitlines(), right.splitlines()
    if left_lines != right_lines or left == right:
        return [f"{line}\n" for line in left_lines], [f"{line}\n" for line in right_lines]
    return left.splitlines(keepends=True), right.splitlines(keepends=True)


def _shown(diff_line: str) -> str:
    """One line of the unified diff, its line ending taken off for display.

    An added or removed line with no newline gets diff's own marker on the
    next line; one with another ending (``\\r\\n``, a lone ``\\r``) names it.
    Unchanged context lines are shown without comment.
    """
    content = diff_line.rstrip("\r\n")
    ending = diff_line[len(content):]
    if diff_line[:1] not in ("+", "-") or diff_line.startswith(("+++", "---")) or ending == "\n":
        return content
    if not ending:
        return f"{content}\n{_NO_NEWLINE_MARK}"
    return f"{content}  (line ends with {ending!r})"


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
    left_lines, right_lines = _line_lists(left, right)
    diff_lines = difflib.unified_diff(
        left_lines,
        right_lines,
        fromfile=left_label,
        tofile=right_label,
        lineterm="",
        n=_CONTEXT_LINES,
    )
    return "\n".join(_shown(line) for line in diff_lines)


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
    matcher = difflib.SequenceMatcher(None, *_line_lists(left, right))
    added = 0
    removed = 0
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed += left_end - left_start
        if tag in ("replace", "insert"):
            added += right_end - right_start
    return DiffSummary(added=added, removed=removed, is_equal=left == right)

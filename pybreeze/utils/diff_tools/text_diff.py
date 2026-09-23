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
# The "--- left" and "+++ right" lines a non-empty unified diff starts with
_HEADER_LINES = 2
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
    """One line of the unified diff's body, its line ending taken off for display.

    An added or removed line with no newline gets diff's own marker on the
    next line; one with another ending (``\\r\\n``, a lone ``\\r``, or any other
    separator ``str.splitlines`` ends a line at, such as U+2028) names it.
    Unchanged context lines are shown without comment.
    """
    content = diff_line.splitlines()[0] if diff_line else ""
    ending = diff_line[len(content):]
    if diff_line[:1] not in ("+", "-") or ending == "\n":
        return content
    if not ending:
        return f"{content}\n{_NO_NEWLINE_MARK}"
    return f"{content}  (line ends with {ending!r})"


@dataclass(frozen=True)
class Comparison:
    """How two texts differ: the counts and the unified diff, from one line matching.

    :param summary: the counts
    :param diff: the unified diff text (empty when the texts are identical)
    """

    summary: DiffSummary
    diff: str


def _unified_range(start: int, stop: int) -> str:
    """A hunk header's ``start,length``, as ``diff -u`` and ``difflib.unified_diff`` write it."""
    length = stop - start
    if length == 1:
        return str(start + 1)
    return f"{start if length == 0 else start + 1},{length}"


def _unified_lines(
        matcher: difflib.SequenceMatcher, left_lines: list[str], right_lines: list[str],
        labels: tuple[str, str]) -> list[str]:
    """The unified diff lines of *matcher*'s match, as ``difflib.unified_diff`` writes them."""
    lines: list[str] = []
    for group in matcher.get_grouped_opcodes(_CONTEXT_LINES):
        if not lines:
            lines += [f"--- {labels[0]}", f"+++ {labels[1]}"]
        first, last = group[0], group[-1]
        lines.append(f"@@ -{_unified_range(first[1], last[2])} +{_unified_range(first[3], last[4])} @@")
        for tag, left_start, left_end, right_start, right_end in group:
            if tag == "equal":
                lines += [f" {line}" for line in left_lines[left_start:left_end]]
                continue
            if tag in ("replace", "delete"):
                lines += [f"-{line}" for line in left_lines[left_start:left_end]]
            if tag in ("replace", "insert"):
                lines += [f"+{line}" for line in right_lines[right_start:right_end]]
    return lines


def compare_texts(
        left: str, right: str,
        left_label: str = _LEFT_LABEL, right_label: str = _RIGHT_LABEL) -> Comparison:
    """Compare *left* and *right* once, for both the counts and the unified diff.

    Matching the lines is the slow part: the counts and the diff each did it
    on their own, which doubled a wait of several seconds on large inputs.

    :param left: the first (expected) text
    :param right: the second (actual) text
    :param left_label: header label for the first text
    :param right_label: header label for the second text
    :return: the counts and the diff
    """
    left_lines, right_lines = _line_lists(left, right)
    matcher = difflib.SequenceMatcher(None, left_lines, right_lines)
    added = 0
    removed = 0
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed += left_end - left_start
        if tag in ("replace", "insert"):
            added += right_end - right_start
    lines = _unified_lines(matcher, left_lines, right_lines, (left_label, right_label))
    # The two header lines are shown as they are: told apart by position, not
    # by their "---"/"+++", which a removed "--x" or an added "++x" also has
    diff = "\n".join(lines[:_HEADER_LINES] + [_shown(line) for line in lines[_HEADER_LINES:]])
    return Comparison(DiffSummary(added=added, removed=removed, is_equal=left == right), diff)


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
    return compare_texts(left, right, left_label, right_label).diff


def diff_summary(left: str, right: str) -> DiffSummary:
    """Summarise how *left* and *right* differ, line by line.

    The counts come from the same line matching as the unified diff, so they
    agree with the diff shown beside them. ``difflib.ndiff`` also compared the
    characters inside every changed line, which the counts never needed.

    :param left: the first (expected) text
    :param right: the second (actual) text
    :return: the counts of added and removed lines and whether they are equal
    """
    return compare_texts(left, right).summary

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
# Most lines, both texts together, for which a trimmed match is checked
# against the plain one (``_closest_match``); matching takes milliseconds there
_PLAIN_MATCH_MAX_LINES = 2000
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


class _TrimmedMatcher(difflib.SequenceMatcher):
    """A line matcher that sets the unchanged head and tail aside before matching.

    ``SequenceMatcher`` treats a line making up more than 1% of 200 or more as
    junk that cannot anchor a match, so in a long text full of ``}`` one
    changed line came out as hundreds removed and added. Trimmed, what is left
    to match is usually short, under the 200 lines the heuristic starts at.
    It is not turned off for what is left: without it, matching repetitive
    text grows with the square of its lines (1,996 lines took 55 s).

    Only the opcodes cover both texts whole; ``ratio()`` and
    ``get_matching_blocks()`` describe what is left to match. It can change
    more lines than the plain match does, so ``_closest_match`` compares them.
    """

    def __init__(self, left_lines: list[str], right_lines: list[str]) -> None:
        head = 0
        limit = min(len(left_lines), len(right_lines))
        while head < limit and left_lines[head] == right_lines[head]:
            head += 1
        tail = 0
        while (tail < limit - head
               and left_lines[len(left_lines) - 1 - tail] == right_lines[len(right_lines) - 1 - tail]):
            tail += 1
        self._head, self._tail = head, tail
        self._sizes = (len(left_lines), len(right_lines))
        middle_left = left_lines[head:len(left_lines) - tail]
        middle_right = right_lines[head:len(right_lines) - tail]
        super().__init__(None, middle_left, middle_right)

    def trimmed_any(self) -> bool:
        """Whether an unchanged head or tail was set aside."""
        return bool(self._head or self._tail)

    def get_opcodes(self) -> list[tuple[str, int, int, int, int]]:
        """The opcodes over the whole two texts, the head and tail as equal blocks.

        The middle's opcodes never begin or end with an equal block -- the head
        ends at the first line that differs, the tail at the last -- so the
        head's and the tail's blocks stand next to a change, never next to
        another equal block, and nothing needs merging.
        """
        head, tail = self._head, self._tail
        left_size, right_size = self._sizes
        codes = [("equal", 0, head, 0, head)] if head else []
        # difflib gives no block for an empty middle, never an empty equal one
        codes += [(tag, i1 + head, i2 + head, j1 + head, j2 + head)
                  for tag, i1, i2, j1, j2 in super().get_opcodes()]
        if tail:
            codes.append(("equal", left_size - tail, left_size, right_size - tail, right_size))
        return codes or [("equal", 0, 0, 0, 0)]


def _unified_range(start: int, stop: int) -> str:
    """A hunk header's ``start,length``, as ``diff -u`` and ``difflib.unified_diff`` write it."""
    length = stop - start
    if length == 1:
        return str(start + 1)
    return f"{start if length == 0 else start + 1},{length}"


def _changed_lines(matcher: difflib.SequenceMatcher) -> tuple[int, int]:
    """How many lines *matcher*'s match adds and removes."""
    added = 0
    removed = 0
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed += left_end - left_start
        if tag in ("replace", "insert"):
            added += right_end - right_start
    return added, removed


def _closest_match(left_lines: list[str], right_lines: list[str]) -> tuple[difflib.SequenceMatcher, int, int]:
    """The match that changes fewer lines, with its added and removed counts.

    Setting the unchanged head and tail aside (``_TrimmedMatcher``) usually
    finds the smaller diff, but not always: in ``b b a b a`` against
    ``b a c b`` the first ``b`` taken as unchanged left a worse match, five
    lines changed where ``difflib`` changes three. When anything was set
    aside, the plain match is made too and the smaller one kept -- for texts
    of up to ``_PLAIN_MATCH_MAX_LINES`` lines between them. On larger ones a
    second match doubled a wait of seconds (40,000 lines: 6 s became 16 s)
    for the same diff.
    """
    trimmed = _TrimmedMatcher(left_lines, right_lines)
    best = (trimmed, *_changed_lines(trimmed))
    if trimmed.trimmed_any() and len(left_lines) + len(right_lines) <= _PLAIN_MATCH_MAX_LINES:
        plain = difflib.SequenceMatcher(None, left_lines, right_lines)
        added, removed = _changed_lines(plain)
        if added + removed < best[1] + best[2]:
            best = (plain, added, removed)
    return best


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
    matcher, added, removed = _closest_match(left_lines, right_lines)
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

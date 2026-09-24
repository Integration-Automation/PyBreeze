"""Tests for the text diff utility."""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pybreeze.utils.diff_tools.text_diff import diff_summary, unified_diff


class TestUnifiedDiff:
    def test_identical_is_empty(self):
        assert unified_diff("a\nb", "a\nb") == ""

    def test_shows_added_line(self):
        diff = unified_diff("a\nb", "a\nb\nc")
        assert "+c" in diff

    def test_shows_removed_line(self):
        diff = unified_diff("a\nb\nc", "a\nb")
        assert "-c" in diff

    def test_shows_changed_line(self):
        diff = unified_diff("hello", "world")
        assert "-hello" in diff
        assert "+world" in diff

    def test_uses_labels(self):
        diff = unified_diff("a", "b", left_label="expected", right_label="actual")
        assert "expected" in diff
        assert "actual" in diff

    def test_empty_inputs(self):
        assert unified_diff("", "") == ""


class TestDiffSummary:
    def test_identical(self):
        summary = diff_summary("a\nb", "a\nb")
        assert summary.is_equal
        assert summary.added == 0
        assert summary.removed == 0

    def test_added_line(self):
        summary = diff_summary("a", "a\nb")
        assert summary.added == 1
        assert summary.removed == 0
        assert not summary.is_equal

    def test_removed_line(self):
        summary = diff_summary("a\nb", "a")
        assert summary.removed == 1
        assert summary.added == 0

    def test_changed_line_counts_as_add_and_remove(self):
        summary = diff_summary("hello", "world")
        assert summary.added == 1
        assert summary.removed == 1

    def test_whitespace_only_difference(self):
        summary = diff_summary("a", "a ")
        assert not summary.is_equal


class TestSummaryMatchesTheShownDiff:
    def test_the_counts_are_the_diffs_own_plus_and_minus_lines(self):
        from hypothesis import given, settings
        from hypothesis import strategies as st

        lines = st.lists(st.sampled_from(["a", "b", "c", "d", ""]), max_size=12)

        @settings(max_examples=200, deadline=None)
        @given(lines, lines)
        def agree(left, right):
            left_text, right_text = "\n".join(left), "\n".join(right)
            shown = unified_diff(left_text, right_text).splitlines()[2:]  # skip the ---/+++ header
            summary = diff_summary(left_text, right_text)
            assert summary.added == sum(line.startswith("+") for line in shown)
            assert summary.removed == sum(line.startswith("-") for line in shown)

        agree()

    def test_every_line_changed_in_a_large_text_is_quick(self):
        import time

        left = "\n".join(f"line {number} alpha" for number in range(3000))
        right = "\n".join(f"line {number} beta" for number in range(3000))

        started = time.perf_counter()
        summary = diff_summary(left, right)

        # ndiff took over a minute here; the opcodes take milliseconds.
        assert time.perf_counter() - started < 5
        assert (summary.added, summary.removed) == (3000, 3000)


class TestOnlyTheLineEndingsDiffer:
    """Texts that differ in a final newline or a line ending: the diff says where."""

    def test_a_missing_final_newline_shows_as_a_change(self):
        # It said "not identical" and showed an empty diff: +0 / -0.
        summary = diff_summary("a\n", "a")

        assert (summary.added, summary.removed, summary.is_equal) == (1, 1, False)
        assert unified_diff("a\n", "a").endswith("+a\n\\ No newline at end of file")

    def test_a_different_line_ending_is_named(self):
        assert "-a  (line ends with '\\r\\n')" in unified_diff("a\r\nb", "a\nb")

    def test_other_changes_are_counted_as_before(self):
        # A line added after a last line without a newline is one added line.
        assert diff_summary("a", "a\nb").added == 1


class TestAnotherLineSeparator:
    """splitlines also ends a line at U+2028, \\v, \\f, ...: the diff must name it."""

    def test_a_line_separator_is_named_not_mistaken_for_no_newline(self):
        diff = unified_diff("a b", "a\nb")

        assert "-a  (line ends with '\\u2028')" in diff
        assert "No newline" not in diff

    def test_two_separators_that_look_alike_are_told_apart(self):
        diff = unified_diff("a\x0bb", "a\x0cb")

        assert "-a  (line ends with '\\x0b')" in diff
        assert "+a  (line ends with '\\x0c')" in diff


def test_a_removed_line_starting_with_dashes_gets_its_ending_named():
    # "---x" was taken for the diff's header line and left without a note
    diff = unified_diff("--x\r\n", "--x\n")

    assert diff.splitlines()[:2] == ["--- expected", "+++ actual"]
    assert "---x  (line ends with '\\r\\n')" in diff


_LINES = st.lists(st.sampled_from(["a", "b", "c", "", "d e"]), max_size=25)


def _applied(diff: str, left: list[str]) -> list[str]:
    """*left* with the unified *diff* applied, each context and removed line checked."""
    import re

    out: list[str] = []
    position = 0
    for line in diff.splitlines()[2:]:
        if line.startswith("@@"):
            start, length = re.match(r"@@ -(\d+)(?:,(\d+))? ", line).groups()
            begin = int(start) - 1 if length != "0" else int(start)
            out += left[position:begin]
            position = begin
        elif line.startswith("\\ No newline"):
            continue
        elif line.startswith("+"):
            out.append(line[1:])
        else:
            assert left[position] == line[1:]
            if line.startswith(" "):
                out.append(line[1:])
            position += 1
    return out + left[position:]


@settings(max_examples=300, deadline=None)
@given(left=_LINES, right=_LINES)
def test_the_diff_turns_the_left_into_the_right_and_is_no_longer_than_difflibs(left, right):
    # Where two alignments are as short, the unchanged head and tail set aside
    # first may pick the other one; the diff must still be right, and never
    # longer than difflib.unified_diff's
    import difflib

    from pybreeze.utils.diff_tools.text_diff import _line_lists, compare_texts

    left_text, right_text = "\n".join(left), "\n".join(right)
    comparison = compare_texts(left_text, right_text)
    body = comparison.diff.splitlines()[2:]
    left_lines, right_lines = _line_lists(left_text, right_text)
    written = list(difflib.unified_diff(left_lines, right_lines, lineterm="", n=3))[2:]

    assert _applied(comparison.diff, left_text.splitlines()) == right_text.splitlines()
    assert comparison.summary.added == sum(line.startswith("+") for line in body)
    assert comparison.summary.removed == sum(line.startswith("-") for line in body)
    changed = comparison.summary.added + comparison.summary.removed
    assert changed <= sum(line[:1] in ("+", "-") for line in written)


@pytest.mark.parametrize(("left", "right"), [
    ("\n".join(["{", "  a", "}"] * 100), "\n".join(["{", "  a", "}"] * 100).replace("  a", "  b", 1)),
    ("x\n" * 300, "y\n" + "x\n" * 299),
])
def test_one_changed_line_in_a_long_repetitive_text_is_one_line(left, right):
    # A line making up over 1% of 200 or more was junk to difflib: 299 removed and added
    from pybreeze.utils.diff_tools.text_diff import compare_texts

    summary = compare_texts(left, right).summary

    assert (summary.added, summary.removed) == (1, 1)

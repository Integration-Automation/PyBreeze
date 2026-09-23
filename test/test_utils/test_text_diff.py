"""Tests for the text diff utility."""
from __future__ import annotations

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

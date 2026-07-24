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

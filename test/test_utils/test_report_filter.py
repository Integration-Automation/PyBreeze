"""Which results of a report are shown: by ending, by time taken, by text, by package."""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pybreeze.utils.execution_report.report_filter import (
    EVERY_STATUS,
    FAILURES,
    ReportFilter,
    leaf_counts,
    total_seconds,
)
from pybreeze.utils.execution_report.report_schema import (
    ErrorDetail,
    ExecutionReport,
    ExecutionResult,
    ResultKind,
    Status,
)


def _test(name: str, status: Status = Status.PASSED, seconds: float | None = 0.1, error: str = "") -> ExecutionResult:
    return ExecutionResult(id=name, name=name, status=status, duration=seconds,
                           error=ErrorDetail(error) if error else None)


def _suite(name: str, *children: ExecutionResult) -> ExecutionResult:
    return ExecutionResult(id=name, name=name, status=max((child.status for child in children),
                                                          key=list(Status).index),
                           kind=ResultKind.SUITE, children=children)


RESULTS = (
    _suite("login",
           _test("logs in", seconds=0.4),
           _test("wrong password", Status.FAILED, 0.3, "assert 200 == 401"),
           _suite("slow", _test("builds a report", seconds=2.5))),
    _suite("profile",
           _test("avatar", Status.ERROR, 0.05, "fixture storage not found"),
           _test("export", Status.SKIPPED, None)),
    _test("loose step", seconds=1.0),
)


def _outline(results) -> list:
    return [[result.name, _outline(result.children)] if result.children else result.name for result in results]


def test_a_filter_that_leaves_nothing_out_gives_the_results_as_they_are():
    assert ReportFilter().shows_everything()
    assert ReportFilter().of(RESULTS) is RESULTS


def test_only_the_endings_asked_for_are_shown_with_what_holds_them():
    shown = ReportFilter(statuses=FAILURES).of(RESULTS)

    assert _outline(shown) == [["login", ["wrong password"]], ["profile", ["avatar"]]]


def test_a_suite_with_nothing_left_under_it_is_not_shown():
    assert _outline(ReportFilter(statuses=frozenset({Status.SKIPPED})).of(RESULTS)) == [["profile", ["export"]]]
    assert ReportFilter(statuses=frozenset()).of(RESULTS) == ()


def test_only_what_took_long_enough_is_shown_and_what_has_no_time_is_left_out():
    shown = ReportFilter(at_least_seconds=1.0).of(RESULTS)

    assert _outline(shown) == [["login", [["slow", ["builds a report"]]]], "loose step"]


def test_text_is_looked_for_in_names_whatever_the_capitals():
    assert _outline(ReportFilter(text="  WRONG ").of(RESULTS)) == [["login", ["wrong password"]]]


def test_text_is_looked_for_in_what_went_wrong_too():
    assert _outline(ReportFilter(text="fixture").of(RESULTS)) == [["profile", ["avatar"]]]


def test_typing_a_suites_name_shows_everything_under_it():
    assert _outline(ReportFilter(text="login").of(RESULTS)) == [
        ["login", ["logs in", "wrong password", ["slow", ["builds a report"]]]]]
    assert _outline(ReportFilter(text="slow").of(RESULTS)) == [["login", [["slow", ["builds a report"]]]]]


def test_the_ways_of_filtering_narrow_each_other():
    shown = ReportFilter(statuses=FAILURES, text="login", at_least_seconds=0.2).of(RESULTS)

    assert _outline(shown) == [["login", ["wrong password"]]]
    assert ReportFilter(statuses=FAILURES, at_least_seconds=1.0).of(RESULTS) == ()


def test_what_is_shown_is_a_copy_and_the_results_are_left_whole():
    ReportFilter(statuses=FAILURES).of(RESULTS)

    assert len(RESULTS[0].children) == 3


def test_a_report_is_taken_when_its_package_is_among_those_asked_for():
    mcp, web = ExecutionReport("mcp"), ExecutionReport("je_web_runner")

    assert ReportFilter().takes_report(mcp) and ReportFilter().takes_report(web)
    only_mcp = ReportFilter(frameworks=frozenset({"mcp"}))
    assert only_mcp.takes_report(mcp) and not only_mcp.takes_report(web)
    assert not only_mcp.shows_everything()


@pytest.mark.parametrize("changed", [
    ReportFilter(statuses=FAILURES), ReportFilter(at_least_seconds=0.001), ReportFilter(text="x"),
])
def test_any_narrowing_is_not_everything(changed):
    assert not changed.shows_everything()
    assert ReportFilter(text="   ", at_least_seconds=0.0, statuses=EVERY_STATUS).shows_everything()


def test_results_are_counted_by_ending_without_what_holds_them():
    counts = leaf_counts(RESULTS)

    assert counts == {Status.PASSED: 3, Status.FAILED: 1, Status.ERROR: 1, Status.SKIPPED: 1}
    assert leaf_counts(ReportFilter(statuses=FAILURES).of(RESULTS))[Status.PASSED] == 0
    assert leaf_counts(()) == dict.fromkeys(Status, 0)


def test_the_time_taken_is_that_of_the_results_that_hold_no_others():
    assert total_seconds(RESULTS) == pytest.approx(0.4 + 0.3 + 2.5 + 0.05 + 1.0)
    assert total_seconds(()) == 0.0


def test_a_tree_as_deep_as_a_report_may_be_is_filtered_without_recursion():
    deep = _test("bottom", Status.FAILED)
    for level in range(5000):
        deep = ExecutionResult(id=str(level), name=f"level {level}", status=Status.FAILED, children=(deep,))

    shown = ReportFilter(statuses=FAILURES).of((deep,))

    assert shown[0].name == "level 4999"
    assert leaf_counts(shown)[Status.FAILED] == 1
    assert total_seconds(shown) == pytest.approx(0.1)


_STATUSES = st.frozensets(st.sampled_from(list(Status)))


@given(statuses=_STATUSES, seconds=st.floats(0, 3), text=st.sampled_from(["", "o", "login", "zzz"]))
def test_whatever_the_filter_everything_shown_passes_it_and_nothing_is_added(statuses, seconds, text):
    wanted = ReportFilter(statuses=statuses, at_least_seconds=seconds, text=text)

    shown = wanted.of(RESULTS)

    leaves = []
    pending = list(shown)
    while pending:
        result = pending.pop()
        pending.extend(result.children)
        if not result.children:
            leaves.append(result)
    assert all(leaf.status in statuses for leaf in leaves) or wanted.shows_everything()
    assert all(leaf.duration is not None and leaf.duration >= seconds for leaf in leaves) or seconds <= 0
    assert len(leaves) <= sum(leaf_counts(RESULTS).values())

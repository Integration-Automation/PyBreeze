"""The execution report: one shape for a run, written and read back without loss."""
from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pybreeze.utils.exception.exceptions import ExecutionReportException
from pybreeze.utils.execution_report.report_schema import (
    MAX_DEPTH,
    SCHEMA_VERSION,
    Attachment,
    ErrorDetail,
    ExecutionReport,
    ExecutionResult,
    ResultKind,
    Status,
    rolled_up,
    stable_id,
)

_FRAMEWORK = "je_api_testka"


def _step(name: str, status: Status, **fields) -> ExecutionResult:
    return ExecutionResult(id=name, name=name, status=status, kind=ResultKind.STEP, **fields)


def _report() -> ExecutionReport:
    """A run with every field in use somewhere."""
    failed = _step(
        "check the status", Status.FAILED, started=1759900000.5, duration=0.25,
        stdout="GET /items\n", stderr="warning: slow\n",
        error=ErrorDetail(message="expected 200, got 500", kind="AssertionError", trace="Traceback ..."),
        attachments=(Attachment(name="response", path="out/response.json", media_type="application/json"),),
        raw={"status_code": 500, "headers": {"X-A": ["1", "2"]}})
    suite = ExecutionResult(
        id="suite", name="items", status=Status.FAILED, kind=ResultKind.SUITE,
        children=(_step("open the page", Status.PASSED), failed, _step("clean up", Status.SKIPPED)))
    return ExecutionReport(
        framework=_FRAMEWORK, results=(suite, _step("alone", Status.ERROR)), name="items.json",
        started=1759900000.0, duration=1.5, raw={"total": 4})


class TestRoundTrip:
    def test_a_report_comes_back_as_it_was(self):
        report = _report()

        assert ExecutionReport.from_dict(json.loads(json.dumps(report.to_dict()))) == report

    def test_the_written_form_names_the_schema_version(self):
        assert _report().to_dict()["schema_version"] == SCHEMA_VERSION

    def test_the_written_form_keeps_its_field_order(self):
        written = ExecutionReport(framework=_FRAMEWORK, results=(_step("a", Status.PASSED),)).to_dict()

        assert list(written) == ["schema_version", "framework", "name", "started", "duration", "results", "raw"]
        assert list(written["results"][0]) == [
            "id", "kind", "name", "status", "started", "duration", "stdout", "stderr",
            "error", "attachments", "children", "raw"]

    def test_a_field_from_a_later_writer_is_left_unread(self):
        written = _report().to_dict()
        written["retries"] = 3
        written["results"][0]["flaky"] = True

        assert ExecutionReport.from_dict(written) == _report()

    def test_only_what_identifies_a_result_is_required(self):
        report = ExecutionReport.from_dict({
            "schema_version": 1, "framework": _FRAMEWORK,
            "results": [{"id": "a", "name": "a", "status": "passed"}]})

        assert report == ExecutionReport(
            framework=_FRAMEWORK, results=(ExecutionResult(id="a", name="a", status=Status.PASSED),))

    def test_a_whole_number_of_seconds_reads_as_a_float(self):
        report = ExecutionReport.from_dict({"schema_version": 1, "framework": _FRAMEWORK, "duration": 2})

        assert report.duration == 2.0
        assert isinstance(report.duration, float)


_names = st.text(max_size=8)
_seconds = st.one_of(st.none(), st.floats(allow_nan=False, allow_infinity=False))
_raw = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=8)),
    lambda inner: st.one_of(st.lists(inner, max_size=3), st.dictionaries(_names, inner, max_size=3)),
    max_leaves=6)


@st.composite
def _results(draw, depth: int = 0) -> ExecutionResult:
    children = draw(st.lists(_results(depth + 1), max_size=2)) if depth < 3 else []
    return ExecutionResult(
        id=draw(_names), name=draw(_names), status=draw(st.sampled_from(Status)),
        kind=draw(st.sampled_from(ResultKind)), started=draw(_seconds), duration=draw(_seconds),
        stdout=draw(_names), stderr=draw(_names),
        error=draw(st.one_of(st.none(), st.builds(ErrorDetail, message=_names, kind=_names, trace=_names))),
        attachments=tuple(draw(st.lists(
            st.builds(Attachment, name=_names, path=_names, media_type=_names), max_size=2))),
        children=tuple(children), raw=draw(_raw))


def _with_ids_made_unique(results: list[ExecutionResult], taken: list[int]) -> tuple[ExecutionResult, ...]:
    """*results* with every ID replaced by one no other result has."""
    renamed = []
    for result in results:
        taken.append(len(taken))
        renamed.append(ExecutionResult(
            id=f"{result.id}#{taken[-1]}", name=result.name, status=result.status, kind=result.kind,
            started=result.started, duration=result.duration, stdout=result.stdout, stderr=result.stderr,
            error=result.error, attachments=result.attachments,
            children=_with_ids_made_unique(list(result.children), taken), raw=result.raw))
    return tuple(renamed)


@given(results=st.lists(_results(), max_size=3), name=_names, started=_seconds, duration=_seconds, raw=_raw)
def test_any_report_survives_being_written_as_json(results, name, started, duration, raw):
    report = ExecutionReport(
        framework=_FRAMEWORK, results=_with_ids_made_unique(results, []), name=name,
        started=started, duration=duration, raw=raw)

    assert ExecutionReport.from_dict(json.loads(json.dumps(report.to_dict()))) == report


def _written(**changes) -> dict:
    """A small valid report as data, with *changes* made at its top level."""
    written = {
        "schema_version": 1, "framework": _FRAMEWORK,
        "results": [{"id": "a", "name": "a", "status": "passed", "children": [
            {"id": "b", "name": "b", "status": "failed"}]}]}
    written.update(changes)
    return written


class TestWhatIsNotAReport:
    @pytest.mark.parametrize("data", [None, [], "report", 3], ids=["null", "a-list", "a-string", "a-number"])
    def test_anything_but_an_object(self, data):
        with pytest.raises(ExecutionReportException, match=r"\$ is missing"):
            ExecutionReport.from_dict(data)

    @pytest.mark.parametrize(("changes", "field"), [
        ({"schema_version": "1"}, "$.schema_version"),
        ({"schema_version": True}, "$.schema_version"),
        ({"schema_version": 0}, "$.schema_version"),
        ({"framework": None}, "$.framework"),
        ({"name": 5}, "$.name"),
        ({"started": "yesterday"}, "$.started"),
        ({"duration": True}, "$.duration"),
        ({"duration": float("nan")}, "$.duration"),
        ({"duration": float("inf")}, "$.duration"),
        ({"results": {}}, "$.results"),
        ({"results": ["a"]}, "$.results[0]"),
        ({"results": [{"name": "a", "status": "passed"}]}, "$.results[0].id"),
        ({"results": [{"id": "a", "name": "a", "status": "green"}]}, "$.results[0].status"),
        ({"results": [{"id": "a", "name": "a", "status": []}]}, "$.results[0].status"),
        ({"results": [{"id": "a", "name": "a", "status": "passed", "kind": "scenario"}]}, "$.results[0].kind"),
        ({"results": [{"id": "a", "name": "a", "status": "passed", "stdout": None}]}, "$.results[0].stdout"),
        ({"results": [{"id": "a", "name": "a", "status": "passed", "error": "boom"}]}, "$.results[0].error"),
        ({"results": [{"id": "a", "name": "a", "status": "passed", "error": {}}]}, "$.results[0].error.message"),
        ({"results": [{"id": "a", "name": "a", "status": "passed", "attachments": [{"name": "log"}]}]},
         "$.results[0].attachments[0].path"),
        ({"results": [{"id": "a", "name": "a", "status": "passed", "children": [{}]}]},
         "$.results[0].children[0].id"),
    ])
    def test_a_field_missing_or_of_another_type_is_named(self, changes, field):
        with pytest.raises(ExecutionReportException) as refused:
            ExecutionReport.from_dict(_written(**changes))

        assert f"{field} is missing or of the wrong type" in str(refused.value)

    def test_a_missing_field_is_named_too(self):
        written = _written()
        del written["framework"]

        with pytest.raises(ExecutionReportException, match=r"\$\.framework is missing"):
            ExecutionReport.from_dict(written)

    def test_a_report_from_a_newer_schema(self):
        newer = r"schema version 2, newer than this PyBreeze reads \(up to 1\)"

        with pytest.raises(ExecutionReportException, match=newer):
            ExecutionReport.from_dict(_written(schema_version=SCHEMA_VERSION + 1))

    def test_two_results_with_one_id(self):
        results = [{"id": "a", "name": "a", "status": "passed", "children": [
            {"id": "a", "name": "b", "status": "passed"}]}]

        with pytest.raises(ExecutionReportException, match="the ID 'a' to more than one result"):
            ExecutionReport.from_dict(_written(results=results))

    def test_results_nested_past_the_limit(self):
        # Deep enough that reading it recursively would also pass Python's own limit
        innermost: dict = {"id": "0", "name": "n", "status": "passed"}
        for level in range(1, 5000):
            innermost = {"id": str(level), "name": "n", "status": "passed", "children": [innermost]}

        with pytest.raises(ExecutionReportException, match=f"more than {MAX_DEPTH} levels deep"):
            ExecutionReport.from_dict(_written(results=[innermost]))

    def test_results_nested_to_the_limit_are_read(self):
        innermost: dict = {"id": "0", "name": "n", "status": "passed"}
        for level in range(1, MAX_DEPTH):
            innermost = {"id": str(level), "name": "n", "status": "passed", "children": [innermost]}

        report = ExecutionReport.from_dict(_written(results=[innermost]))

        assert len(list(report.walk())) == MAX_DEPTH


class TestBuiltInCode:
    def test_two_results_cannot_share_an_id(self):
        with pytest.raises(ExecutionReportException):
            ExecutionReport(framework=_FRAMEWORK, results=(_step("a", Status.PASSED), _step("a", Status.FAILED)))

    def test_results_cannot_nest_past_the_limit(self):
        result = _step("0", Status.PASSED)
        for level in range(1, MAX_DEPTH + 1):
            result = ExecutionResult(id=str(level), name="n", status=Status.PASSED, children=(result,))

        with pytest.raises(ExecutionReportException):
            ExecutionReport(framework=_FRAMEWORK, results=(result,))


class TestSummary:
    def test_results_are_walked_parents_first_in_order(self):
        assert [result.name for result in _report().walk()] == [
            "items", "open the page", "check the status", "clean up", "alone"]

    def test_counts_leave_out_a_result_made_of_others(self):
        assert _report().counts() == {
            Status.SKIPPED: 1, Status.PASSED: 1, Status.FAILED: 1, Status.ERROR: 1}

    def test_counts_name_every_status_when_nothing_ran(self):
        assert ExecutionReport(framework=_FRAMEWORK).counts() == dict.fromkeys(Status, 0)

    def test_a_run_ends_as_its_most_serious_result(self):
        assert _report().status is Status.ERROR

    def test_a_run_of_nothing_is_skipped(self):
        assert ExecutionReport(framework=_FRAMEWORK).status is Status.SKIPPED

    @pytest.mark.parametrize(("statuses", "expected"), [
        ([Status.PASSED, Status.SKIPPED], Status.PASSED),
        ([Status.SKIPPED, Status.SKIPPED], Status.SKIPPED),
        ([Status.PASSED, Status.FAILED, Status.PASSED], Status.FAILED),
        ([Status.FAILED, Status.ERROR], Status.ERROR),
    ])
    def test_parts_roll_up_to_the_most_serious(self, statuses, expected):
        assert rolled_up(statuses) is expected


class TestStableId:
    def test_it_is_the_same_wherever_it_is_made(self):
        # Pinned: a changed algorithm would make every earlier run incomparable
        assert stable_id(_FRAMEWORK, "a") == "e18275b5eb38cd50"

    def test_it_tells_parents_names_and_repeats_apart(self):
        ids = {
            stable_id(_FRAMEWORK, "a"), stable_id("je_web_runner", "a"), stable_id(_FRAMEWORK, "b"),
            stable_id(_FRAMEWORK, "a", 1), stable_id(stable_id(_FRAMEWORK, "a"), "a")}

        assert len(ids) == 5

    def test_a_name_holding_the_separator_is_not_another_pair(self):
        assert stable_id("a", "b\x00c") != stable_id("a\x00b", "c")

    def test_half_a_character_in_a_name_is_hashed_too(self):
        # A name read from a framework's JSON can hold a lone surrogate
        assert len(stable_id(_FRAMEWORK, "\ud83d")) == 16

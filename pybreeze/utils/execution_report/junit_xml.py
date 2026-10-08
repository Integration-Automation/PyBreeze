"""JUnit XML, read into an execution report and written from one.

JUnit XML is what pytest (``--junitxml``), most test runners and every CI
service's test summary speak: ``<testsuites>`` of ``<testsuite>`` of
``<testcase>``, a case that did not pass holding ``<failure>``, ``<error>`` or
``<skipped>``. Reading it brings any such run into the report viewer; writing
it hands any report PyBreeze holds (an automation package's run, an MCP
session) to a CI service.

A report can be deeper than JUnit's two levels. Written out, each top-level
result that holds others is a suite, every result under it that holds none is
a case, and the names in between become the case's ``classname``.
"""
from __future__ import annotations

from datetime import datetime

from pybreeze.utils.exception.exception_tags import report_format_error
from pybreeze.utils.exception.exceptions import ExecutionReportException
from pybreeze.utils.execution_report.report_schema import (
    ErrorDetail, ExecutionReport, ExecutionResult, ResultKind, Status, rolled_up, stable_id,
)
from pybreeze.utils.execution_report.safe_xml import XmlElement, parse_xml, write_xml

FRAMEWORK = "junit"
SUITES, SUITE, CASE = "testsuites", "testsuite", "testcase"
# The element a case holds when it did not pass, and how it then ended
_ENDINGS = {"failure": Status.FAILED, "error": Status.ERROR, "skipped": Status.SKIPPED}
_ELEMENT_OF = {status: tag for tag, status in _ENDINGS.items()}
# Suites nested deeper than this are left out: with their cases they would pass the depth a report may have
_MAX_SUITE_DEPTH = 32


def _seconds(text: str | None) -> float | None:
    try:
        seconds = float(text) if text is not None else None
    except ValueError:
        return None
    return seconds if seconds is not None and 0 <= seconds < float("inf") else None


def _moment(text: str | None) -> float | None:
    try:
        return datetime.fromisoformat(text).timestamp() if text else None
    except (ValueError, OverflowError, OSError):
        return None


class _Ids:
    """Gives each result its ID: its parent's, its name, and which of that name under that parent it is."""

    def __init__(self) -> None:
        self._seen: dict[tuple[str, str], int] = {}

    def take(self, parent: str, name: str) -> str:
        occurrence = self._seen.get((parent, name), 0)
        self._seen[parent, name] = occurrence + 1
        return stable_id(parent, name, occurrence)


def _case(element: XmlElement, parent: str, ids: _Ids) -> ExecutionResult:
    name = element.attributes.get("name", "")
    ending = next((child for child in element.children if child.tag in _ENDINGS), None)
    error = None
    if ending is not None:
        said = ending.attributes.get("message", "") or (ending.text.strip().splitlines() or [""])[0]
        error = ErrorDetail(message=said, kind=ending.attributes.get("type", ""), trace=ending.text.strip())
    raw = {key: value for key, value in element.attributes.items() if key not in ("name", "time")}
    return ExecutionResult(
        id=ids.take(parent, f"{element.attributes.get('classname', '')}::{name}"), name=name,
        status=_ENDINGS[ending.tag] if ending is not None else Status.PASSED, kind=ResultKind.TEST,
        duration=_seconds(element.attributes.get("time")),
        stdout="\n".join(out.text for out in element.all("system-out")),
        stderr="\n".join(out.text for out in element.all("system-err")), error=error, raw=raw or None)


def _suite(element: XmlElement, parent: str, ids: _Ids, depth: int) -> ExecutionResult:
    name = element.attributes.get("name", "")
    own_id = ids.take(parent, name)
    children = []
    for child in element.children:
        if child.tag == CASE:
            children.append(_case(child, own_id, ids))
        elif child.tag == SUITE and depth < _MAX_SUITE_DEPTH:
            children.append(_suite(child, own_id, ids, depth + 1))
    return ExecutionResult(
        id=own_id, name=name, status=rolled_up(child.status for child in children), kind=ResultKind.SUITE,
        started=_moment(element.attributes.get("timestamp")), duration=_seconds(element.attributes.get("time")),
        children=tuple(children))


def is_junit(root: XmlElement) -> bool:
    """Whether *root* is the root of a JUnit XML document."""
    return root.tag in (SUITES, SUITE)


def report_from_junit(text: str, name: str = "") -> ExecutionReport:
    """The run a JUnit XML document tells of.

    :param name: what to call the run when the document does not say
    :raises ExecutionReportException: when *text* is not JUnit XML
    """
    root = parse_xml(text)
    if not is_junit(root):
        raise ExecutionReportException(report_format_error)
    ids = _Ids()
    suites = root.all(SUITE) if root.tag == SUITES else [root]
    results = tuple(_suite(suite, FRAMEWORK, ids, 0) for suite in suites)
    started = min((result.started for result in results if result.started is not None), default=None)
    return ExecutionReport(
        framework=FRAMEWORK, results=results, name=root.attributes.get("name", "") or name, started=started,
        duration=_seconds(root.attributes.get("time")) if root.tag == SUITES else None)


def _leaves(result: ExecutionResult, path: tuple[str, ...]) -> list[tuple[tuple[str, ...], ExecutionResult]]:
    """Every result under *result* that holds no other, with the names that lead to it."""
    found = []
    pending = [(path, result)]
    while pending:
        names, each = pending.pop()
        if each.children:
            pending.extend(((*names, each.name), child) for child in reversed(each.children))
        else:
            found.append((names, each))
    return found


def _case_element(path: tuple[str, ...], result: ExecutionResult) -> XmlElement:
    case = XmlElement(CASE, {"name": result.name, "classname": ".".join(path)})
    if result.duration is not None:
        case.attributes["time"] = f"{result.duration:.3f}"
    if result.status is not Status.PASSED:
        error = result.error or ErrorDetail(message="")
        ending = XmlElement(_ELEMENT_OF[result.status], {"message": error.message}, error.trace)
        if error.kind:
            ending.attributes["type"] = error.kind
        case.children.append(ending)
    for tag, text in (("system-out", result.stdout), ("system-err", result.stderr)):
        if text:
            case.children.append(XmlElement(tag, text=text))
    return case


def _counted(tag: str, name: str, cases: list[ExecutionResult]) -> XmlElement:
    """A suite or the set of suites, with the counts a CI service reads from it."""
    return XmlElement(tag, {
        "name": name, "tests": str(len(cases)),
        "failures": str(sum(case.status is Status.FAILED for case in cases)),
        "errors": str(sum(case.status is Status.ERROR for case in cases)),
        "skipped": str(sum(case.status is Status.SKIPPED for case in cases)),
        "time": f"{sum(case.duration or 0.0 for case in cases):.3f}"})


def junit_from_report(report: ExecutionReport) -> str:
    """*report* as a JUnit XML document.

    Each top-level result that holds others is a suite; results that hold none
    at the top are gathered into one suite named after the run.
    """
    name = report.name or report.framework
    # Each suite's name, and its cases with the names that lead to each
    grouped = [(name, [((name,), result) for result in report.results if not result.children])]
    grouped += [(result.name, _leaves(result, ())) for result in report.results if result.children]
    every_case: list[ExecutionResult] = []
    suites: list[XmlElement] = []
    for suite_name, leaves in grouped:
        if not leaves:
            continue
        cases = [leaf for _path, leaf in leaves]
        suite = _counted(SUITE, suite_name, cases)
        suite.children.extend(_case_element(path, leaf) for path, leaf in leaves)
        suites.append(suite)
        every_case.extend(cases)
    root = _counted(SUITES, name, every_case)
    root.children.extend(suites)
    return write_xml(root)

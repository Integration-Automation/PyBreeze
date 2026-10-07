"""The automation packages' own reports, read into the common shape.

APITestka, AutoControl, WebRunner and LoadDensity each keep a run as a list of
records and write it the same way: two files, ``<name>_success.json`` and
``<name>_failure.json`` (or ``.xml``), each a set of ``Success_Test1``,
``Success_Test2``... or ``Failure_Test1``... holding one record. What a record
holds is the package's own:

- APITestka: a request and its response (``request_url``, ``status_code``,
  ``request_time_sec``...), or the request that failed and its ``error``;
- AutoControl and WebRunner: a function that was called (``function_name``,
  ``param``, ``time``, ``exception``);
- LoadDensity: a request of a load test (``Method``, ``test_url``, ``name``,
  ``status_code``), with ``error`` when it failed.

Each record becomes one :class:`ExecutionResult`; the record itself is kept
beside it (``raw``), so nothing the package wrote is lost. Every value in these
files is text (the packages write ``str(...)`` of everything, ``"None"`` for
what was not there), and is read as such.

Pure logic: no package is imported, and nothing here opens a file.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pybreeze.utils.exception.exception_tags import report_format_error
from pybreeze.utils.exception.exceptions import ExecutionReportException
from pybreeze.utils.execution_report.report_schema import (
    ErrorDetail, ExecutionReport, ExecutionResult, ResultKind, Status, stable_id,
)
from pybreeze.utils.execution_report.safe_xml import parse_xml

API_TESTKA, AUTO_CONTROL, WEB_RUNNER, LOAD_DENSITY = (
    "je_api_testka", "je_auto_control", "je_web_runner", "je_load_density")
SUCCESS_PREFIX, FAILURE_PREFIX = "Success_Test", "Failure_Test"
# The element the packages put their records under in an XML report
XML_ROOT = "xml_data"
# How WebRunner names the function of a record; AutoControl's are single words
_WEB_RUNNER_NAMES = ("webdriver wrapper ", "web element ", "web runner manager ", "webdriver with options ")
# What the packages write for a value that was not there
_ABSENT = ("", "None")
# An error's first line is its message, cut to this
_MESSAGE_CHARACTERS = 300


@dataclass(frozen=True)
class _Read:
    """What one record says, in the common terms."""

    name: str
    status: Status
    started: float | None = None
    duration: float | None = None
    output: str = ""
    error: ErrorDetail | None = None


def _value(record: dict, key: str) -> str:
    """The value of *key* in *record* as text; empty when the package wrote none."""
    value = record.get(key)
    text = value if isinstance(value, str) else "" if value is None else str(value)
    return "" if text in _ABSENT else text


def _moment(text: str) -> float | None:
    """*text* as a time, in seconds since the epoch; ``None`` when it is not one the packages write."""
    try:
        return datetime.fromisoformat(text).timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def _seconds(text: str) -> float | None:
    try:
        seconds = float(text)
    except ValueError:
        return None
    return seconds if 0 <= seconds < float("inf") else None


def _error(text: str) -> ErrorDetail:
    """An exception as a package wrote it (its ``repr``), as an error: its class is the kind."""
    first_line = text.splitlines()[0] if text else ""
    kind = first_line.split("(", 1)[0]
    return ErrorDetail(message=first_line[:_MESSAGE_CHARACTERS], kind=kind if kind.isidentifier() else "", trace=text)


def _ending(error: str) -> Status:
    """How a record with *error* ended: a check that did not hold has failed, anything else broke."""
    return Status.FAILED if "Assert" in error else Status.ERROR


def _api(record: dict, failed: bool) -> _Read:
    if failed:
        error = _value(record, "error")
        return _Read(f"{_value(record, 'http_method')} {_value(record, 'test_url')}".strip(), _ending(error),
                     error=_error(error))
    return _Read(
        f"{_value(record, 'request_method')} {_value(record, 'request_url')}".strip(), Status.PASSED,
        started=_moment(_value(record, "start_time")), duration=_seconds(_value(record, "request_time_sec")),
        output=_value(record, "text"))


def _action(record: dict, failed: bool) -> _Read:
    error = _value(record, "exception")
    return _Read(_value(record, "function_name"), _ending(error) if failed else Status.PASSED,
                 started=_moment(_value(record, "time")), error=_error(error) if failed else None)


def _load(record: dict, failed: bool) -> _Read:
    name = f"{_value(record, 'Method')} {_value(record, 'name') or _value(record, 'test_url')}".strip()
    if failed:
        return _Read(name, Status.FAILED, error=_error(_value(record, "error")))
    return _Read(name, Status.PASSED, output=_value(record, "text"))


# How each package's records are read, and the level a record stands for
_READERS: dict[str, tuple[Callable[[dict, bool], _Read], ResultKind]] = {
    API_TESTKA: (_api, ResultKind.TEST),
    AUTO_CONTROL: (_action, ResultKind.STEP),
    WEB_RUNNER: (_action, ResultKind.STEP),
    LOAD_DENSITY: (_load, ResultKind.TEST),
}
FRAMEWORKS = tuple(_READERS)


def is_records(data: object) -> bool:
    """Whether *data* is what a record file holds: ``Success_Test…`` or ``Failure_Test…``, each an object."""
    return isinstance(data, dict) and all(
        isinstance(name, str) and name.startswith((SUCCESS_PREFIX, FAILURE_PREFIX)) and isinstance(record, dict)
        for name, record in data.items())


def records_from_json(text: str) -> dict[str, dict]:
    """The records of a ``_success.json`` or ``_failure.json`` file.

    :raises ExecutionReportException: when *text* is not such a file
    """
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise ExecutionReportException(report_format_error) from error
    if not is_records(data):
        raise ExecutionReportException(report_format_error)
    return data


def records_from_xml(text: str) -> dict[str, dict]:
    """The records of a ``_success.xml`` or ``_failure.xml`` file.

    :raises ExecutionReportException: when *text* is not such a file
    """
    root = parse_xml(text)
    records = {record.tag: {value.tag: value.text.strip() for value in record.children} for record in root.children}
    if root.tag != XML_ROOT or not is_records(records):
        raise ExecutionReportException(report_format_error)
    return records


def framework_of_records(records: dict[str, dict]) -> str | None:
    """Which package wrote *records*, told by what a record holds; ``None`` when there is none to tell from."""
    fields: set[str] = set()
    names: list[str] = []
    for record in records.values():
        fields.update(record)
        names.append(_value(record, "function_name").lower())
    if "function_name" in fields:
        return WEB_RUNNER if any(name.startswith(_WEB_RUNNER_NAMES) for name in names) else AUTO_CONTROL
    if "Method" in fields:
        return LOAD_DENSITY
    if fields & {"request_url", "http_method", "request_method"}:
        return API_TESTKA
    return None


def report_from_records(records: dict[str, dict], name: str = "", framework: str | None = None) -> ExecutionReport:
    """The run *records* tell of, as an execution report.

    :param records: the records of one run: those of its success file and of its failure file together
    :param name: what the run is called (the files' name without ``_success`` / ``_failure``)
    :param framework: the package that wrote them, when it is known; told from the records otherwise
    :raises ExecutionReportException: when no package can be told and none was given
    """
    framework = framework or framework_of_records(records)
    if framework not in _READERS:
        raise ExecutionReportException(report_format_error)
    read, kind = _READERS[framework]
    told = [(key, record, read(record, key.startswith(FAILURE_PREFIX))) for key, record in records.items()]
    if told and all(each.started is not None for _key, _record, each in told):
        # The two files keep what passed and what failed apart; their times put the run back in
        # order. Done before the results are numbered: the third call of a function is then
        # the third whichever of the three failed, and has the same ID in every run
        told.sort(key=lambda entry: entry[2].started)
    seen: dict[str, int] = {}
    results = []
    for key, record, each in told:
        title = each.name or key
        occurrence = seen.get(title, 0)
        seen[title] = occurrence + 1
        results.append(ExecutionResult(
            id=stable_id(framework, title, occurrence), name=title, status=each.status, kind=kind,
            started=each.started, duration=each.duration, stdout=each.output, error=each.error, raw=record))
    started = min((result.started for result in results if result.started is not None), default=None)
    return ExecutionReport(framework=framework, results=tuple(results), name=name, started=started)

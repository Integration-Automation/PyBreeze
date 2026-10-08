"""What a run produced, in one shape whatever framework ran it.

Each automation package reports a run its own way: APITestka and AutoControl
write HTML, JSON and XML records, LoadDensity gives request statistics, a
pytest file a tree of tests. A viewer that understood each of them would be
four viewers. An :class:`ExecutionReport` is the shape they are all read into:
a tree of :class:`ExecutionResult` (suite, test, case, step), each with its
status, timing, output, error and attachments, and with the framework's own
record kept beside it (``raw``) for what the common fields do not say.

A result's ``id`` is the same from one run to the next when it is made with
:func:`stable_id`, so two runs can be compared result by result.

Pure data: nothing here runs a test or reads a framework's file. A report read
back from a file is checked field by field (:meth:`ExecutionReport.from_dict`),
because that file may be anything.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from pybreeze.utils.exception.exception_tags import (
    execution_report_depth_error,
    execution_report_duplicate_id_error,
    execution_report_field_error,
    execution_report_version_error,
)
from pybreeze.utils.exception.exceptions import ExecutionReportException

# The version written into a report; raised when a field changes its meaning
SCHEMA_VERSION = 1
# Deepest a result may nest. A report is walked and written recursively, and a
# file can nest as deep as it likes
MAX_DEPTH = 64
# Characters of the digest kept as an ID: 64 bits, enough to tell a run's results apart
_ID_LENGTH = 16
# Bytes that hold the length of each part hashed into an ID
_LENGTH_BYTES = 8
# Where the report itself is, in the path an error names (JSONPath's root)
_ROOT = "$"
# Marks a field that has no default
_REQUIRED = object()

_Choice = TypeVar("_Choice", bound=Enum)


class Status(Enum):
    """How a result ended, from the least to the most serious."""

    SKIPPED = "skipped"
    PASSED = "passed"
    FAILED = "failed"   # a check did not hold
    ERROR = "error"     # the run itself broke before it could tell


class ResultKind(Enum):
    """What a result stands for; a framework uses the levels it has."""

    SUITE = "suite"
    TEST = "test"
    CASE = "case"
    STEP = "step"


_SERIOUSNESS = {status: rank for rank, status in enumerate(Status)}


def rolled_up(statuses: Iterable[Status]) -> Status:
    """The status of something made of parts with these *statuses*: the most serious of them.

    :return: ``SKIPPED`` when there are none: nothing ran
    """
    return max(statuses, key=_SERIOUSNESS.__getitem__, default=Status.SKIPPED)


def stable_id(parent_id: str, name: str, occurrence: int = 0) -> str:
    """The ID of the result called *name* under the result (or framework) *parent_id*.

    It depends on nothing a run changes (no time, no position among other
    names), so the same test has the same ID in every run.

    :param parent_id: the parent result's ID; the framework's name for a top-level result
    :param name: the result's name
    :param occurrence: which of its parent's results of that name it is, from 0
    """
    digest = hashlib.sha256()
    for part in (parent_id, name, str(occurrence)):
        # Each part with its length before it: joined by a separator, a name
        # holding the separator would read as another parent and name
        encoded = part.encode("utf-8", "surrogatepass")
        digest.update(len(encoded).to_bytes(_LENGTH_BYTES, "big"))
        digest.update(encoded)
    return digest.hexdigest()[:_ID_LENGTH]


@dataclass(frozen=True)
class Attachment:
    """Something a result left behind: a screenshot, a log, a saved response.

    :param name: what to call it
    :param path: where it is, as the framework gave it
    :param media_type: its media type, when known
    """

    name: str
    path: str
    media_type: str = ""


@dataclass(frozen=True)
class ErrorDetail:
    """Why a result failed or broke.

    :param message: the reason, in a line
    :param kind: the error's type (an exception class name), when there is one
    :param trace: the traceback or log excerpt, when there is one
    """

    message: str
    kind: str = ""
    trace: str = ""


@dataclass(frozen=True)
class ExecutionResult:
    """One node of a run: a suite, a test, a case or a step.

    :param id: unique in its report; made with :func:`stable_id` to be comparable across runs
    :param name: what the framework calls it
    :param status: how it ended
    :param kind: the level it stands for
    :param started: when it started, in seconds since the epoch, when known
    :param duration: how long it took, in seconds, when known
    :param stdout: what it wrote to standard output
    :param stderr: what it wrote to standard error
    :param error: why it failed or broke, when it did
    :param attachments: what it left behind
    :param children: the results it is made of
    :param raw: the framework's own record of it, JSON-compatible
    """

    id: str
    name: str
    status: Status
    kind: ResultKind = ResultKind.TEST
    started: float | None = None
    duration: float | None = None
    stdout: str = ""
    stderr: str = ""
    error: ErrorDetail | None = None
    attachments: tuple[Attachment, ...] = ()
    children: tuple[ExecutionResult, ...] = ()
    raw: object = None

    def to_dict(self) -> dict:
        """This result and the results under it as JSON-compatible data."""
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.name,
            "status": self.status.value,
            "started": self.started,
            "duration": self.duration,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": None if self.error is None else {
                "message": self.error.message, "kind": self.error.kind, "trace": self.error.trace},
            "attachments": [
                {"name": attachment.name, "path": attachment.path, "media_type": attachment.media_type}
                for attachment in self.attachments],
            "children": [child.to_dict() for child in self.children],
            "raw": self.raw,
        }


@dataclass(frozen=True)
class ExecutionReport:
    """One run of one framework.

    :param framework: the package that ran it, by its import name (``je_api_testka``)
    :param results: the run's top-level results
    :param name: what was run: a file, a suite
    :param started: when the run started, in seconds since the epoch, when known
    :param duration: how long the run took, in seconds, when known
    :param raw: the framework's own report, JSON-compatible
    :raises ExecutionReportException: when two results share an ID, or results
        nest deeper than :data:`MAX_DEPTH`
    """

    framework: str
    results: tuple[ExecutionResult, ...] = ()
    name: str = ""
    started: float | None = None
    duration: float | None = None
    raw: object = None

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for result in self.walk():
            if result.id in seen:
                raise ExecutionReportException(execution_report_duplicate_id_error.format(id=result.id))
            seen.add(result.id)

    def walk(self) -> Iterator[ExecutionResult]:
        """Every result of the run, a parent before its children, in order.

        :raises ExecutionReportException: when results nest deeper than :data:`MAX_DEPTH`
        """
        pending = [(result, 1) for result in reversed(self.results)]
        while pending:
            result, depth = pending.pop()
            if depth > MAX_DEPTH:
                raise ExecutionReportException(execution_report_depth_error.format(limit=MAX_DEPTH))
            yield result
            pending.extend((child, depth + 1) for child in reversed(result.children))

    @property
    def status(self) -> Status:
        """How the run ended as a whole: the most serious status of its top-level results."""
        return rolled_up(result.status for result in self.results)

    def counts(self) -> dict[Status, int]:
        """How many results ended in each status, counting those with no results under them.

        A suite is not counted beside its tests: it would count each of them twice.
        """
        totals = dict.fromkeys(Status, 0)
        for result in self.walk():
            if not result.children:
                totals[result.status] += 1
        return totals

    def to_dict(self) -> dict:
        """The report as JSON-compatible data, which :meth:`from_dict` reads back."""
        return {
            "schema_version": SCHEMA_VERSION,
            "framework": self.framework,
            "name": self.name,
            "started": self.started,
            "duration": self.duration,
            "results": [result.to_dict() for result in self.results],
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, data: object) -> ExecutionReport:
        """Read a report back from what :meth:`to_dict` wrote.

        A field this version does not know is left unread, so a report with
        more in it still opens.

        :param data: the decoded JSON
        :raises ExecutionReportException: when *data* is not a report: a field
            is missing or of another type, the schema version is newer than
            this one, results nest too deep, or two share an ID
        """
        if not isinstance(data, dict):
            raise _not_a_report(_ROOT)
        version = data.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise _not_a_report(f"{_ROOT}.schema_version")
        if version > SCHEMA_VERSION:
            raise ExecutionReportException(
                execution_report_version_error.format(version=version, supported=SCHEMA_VERSION))
        return cls(
            framework=_text(data, "framework", _ROOT),
            results=_results(data, "results", _ROOT, depth=1),
            name=_text(data, "name", _ROOT, ""),
            started=_seconds(data, "started", _ROOT),
            duration=_seconds(data, "duration", _ROOT),
            raw=data.get("raw"),
        )


def _not_a_report(field: str) -> ExecutionReportException:
    """The error for a *field* that is missing or of the wrong type."""
    return ExecutionReportException(execution_report_field_error.format(field=field))


def _text(data: dict, name: str, where: str, default: object = _REQUIRED) -> str:
    """The string field *name* of *data*, which is at *where* in the report."""
    value = data.get(name, default)
    if not isinstance(value, str):
        raise _not_a_report(f"{where}.{name}")
    return value


def _seconds(data: dict, name: str, where: str) -> float | None:
    """The optional field *name* of *data*: a finite number, or ``None`` when it is not given.

    ``true`` is a number to Python, and ``NaN`` one to ``json.loads``; neither is a time.
    """
    value = data.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise _not_a_report(f"{where}.{name}")
    return float(value)


def _choice(data: dict, name: str, where: str, choices: type[_Choice], default: object = _REQUIRED) -> _Choice:
    """The field *name* of *data* as a member of *choices*."""
    value = data.get(name, default)
    if isinstance(value, choices):
        return value
    try:
        return choices(value)
    except ValueError:
        raise _not_a_report(f"{where}.{name}") from None


def _records(data: dict, name: str, where: str) -> list[tuple[str, dict]]:
    """The list of objects in the field *name* of *data*, each with where it is; none when not given."""
    value = data.get(name, [])
    if not isinstance(value, list):
        raise _not_a_report(f"{where}.{name}")
    records: list[tuple[str, dict]] = []
    for index, item in enumerate(value):
        item_at = f"{where}.{name}[{index}]"
        if not isinstance(item, dict):
            raise _not_a_report(item_at)
        records.append((item_at, item))
    return records


def _results(data: dict, name: str, where: str, depth: int) -> tuple[ExecutionResult, ...]:
    """The results in the field *name* of *data*, which are *depth* levels into the report."""
    records = _records(data, name, where)
    if records and depth > MAX_DEPTH:
        raise ExecutionReportException(execution_report_depth_error.format(limit=MAX_DEPTH))
    return tuple(_result(item, item_at, depth) for item_at, item in records)


def _error(data: dict, where: str) -> ErrorDetail | None:
    """The ``error`` of the result *data*, when it has one."""
    error = data.get("error")
    if error is None:
        return None
    error_at = f"{where}.error"
    if not isinstance(error, dict):
        raise _not_a_report(error_at)
    return ErrorDetail(
        message=_text(error, "message", error_at),
        kind=_text(error, "kind", error_at, ""),
        trace=_text(error, "trace", error_at, ""))


def _result(data: dict, where: str, depth: int) -> ExecutionResult:
    """The result *data* holds, which is at *where* in the report."""
    return ExecutionResult(
        id=_text(data, "id", where),
        name=_text(data, "name", where),
        status=_choice(data, "status", where, Status),
        kind=_choice(data, "kind", where, ResultKind, ResultKind.TEST),
        started=_seconds(data, "started", where),
        duration=_seconds(data, "duration", where),
        stdout=_text(data, "stdout", where, ""),
        stderr=_text(data, "stderr", where, ""),
        error=_error(data, where),
        attachments=tuple(
            Attachment(
                name=_text(item, "name", item_at),
                path=_text(item, "path", item_at),
                media_type=_text(item, "media_type", item_at, ""))
            for item_at, item in _records(data, "attachments", where)),
        children=_results(data, "children", where, depth + 1),
        raw=data.get("raw"),
    )

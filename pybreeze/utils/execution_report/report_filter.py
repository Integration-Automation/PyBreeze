"""Which results of a report to show: by how they ended, how long they took, and what they are called.

A filter is asked of the results that hold no others (the tests, the steps):
those are what ended one way or another and took some time. A result that
holds others is kept when something under it is kept, with only what was kept
under it, so the tree keeps its shape around what is shown. Text is matched in
a result's own name and error and in the names of what holds it, so typing a
suite's name shows the suite.

Pure logic: the viewer hands in results and shows what comes back.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from pybreeze.utils.execution_report.report_schema import ExecutionReport, ExecutionResult, Status

FAILURES = frozenset({Status.FAILED, Status.ERROR})
EVERY_STATUS = frozenset(Status)


@dataclass(frozen=True)
class ReportFilter:
    """What to show.

    :param statuses: the endings shown
    :param at_least_seconds: only results that took this long or longer; one whose time is not known is left
        out as soon as this is above zero
    :param text: only results with this in their name, their error, or the name of something that holds them;
        capitals do not matter
    :param frameworks: only reports of these packages; every report when empty
    """

    statuses: frozenset[Status] = EVERY_STATUS
    at_least_seconds: float = 0.0
    text: str = ""
    frameworks: frozenset[str] = frozenset()

    def shows_everything(self) -> bool:
        """Whether nothing is left out."""
        return (self.statuses == EVERY_STATUS and self.at_least_seconds <= 0 and not self.text.strip()
                and not self.frameworks)

    def takes_report(self, report: ExecutionReport) -> bool:
        """Whether *report* is of a package this filter shows."""
        return not self.frameworks or report.framework in self.frameworks

    def _takes(self, result: ExecutionResult, named: bool) -> bool:
        """Whether *result*, which holds no other, is shown; *named* when something that holds it has the text."""
        if result.status not in self.statuses:
            return False
        if self.at_least_seconds > 0 and (result.duration is None or result.duration < self.at_least_seconds):
            return False
        wanted = self.text.strip().lower()
        if not wanted or named:
            return True
        said = result.error.message if result.error is not None else ""
        return wanted in result.name.lower() or wanted in said.lower()

    def of(self, results: tuple[ExecutionResult, ...]) -> tuple[ExecutionResult, ...]:
        """*results* with only what is shown, and what holds it. Without recursion: a report is as deep as it likes."""
        if self.shows_everything():
            return results
        wanted = self.text.strip().lower()
        # Each result once on the way down (to know whether a name above it has the text) and,
        # for one that holds others, once more on the way up, when its children are decided
        pending = [(result, False, False) for result in reversed(results)]
        shown: dict[int, ExecutionResult | None] = {}
        while pending:
            result, named, decided = pending.pop()
            if not result.children:
                shown[id(result)] = result if self._takes(result, named) else None
            elif decided:
                children = tuple(filter(None, (shown[id(child)] for child in result.children)))
                shown[id(result)] = replace(result, children=children) if children else None
            else:
                here = named or bool(wanted and wanted in result.name.lower())
                pending.append((result, named, True))
                pending.extend((child, here, False) for child in reversed(result.children))
        return tuple(filter(None, (shown[id(result)] for result in results)))


def leaf_counts(results: tuple[ExecutionResult, ...]) -> dict[Status, int]:
    """How many of *results* and of what they hold ended in each status, counting those that hold no others."""
    totals = dict.fromkeys(Status, 0)
    pending = list(results)
    while pending:
        result = pending.pop()
        if result.children:
            pending.extend(result.children)
        else:
            totals[result.status] += 1
    return totals


def total_seconds(results: tuple[ExecutionResult, ...]) -> float:
    """How long the results that hold no others took together; one whose time is not known counts for nothing."""
    total = 0.0
    pending = list(results)
    while pending:
        result = pending.pop()
        if result.children:
            pending.extend(result.children)
        else:
            total += result.duration or 0.0
    return total

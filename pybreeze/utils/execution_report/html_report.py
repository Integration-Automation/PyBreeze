"""An execution report as one HTML page, and such a page read back.

The page is for people: a summary, then every result with its status, how long
it took, and what went wrong, each opening to its output. It is one file with
its style inside and no script that runs, so it can be mailed, attached to a
build or opened from disk as it is.

The report itself travels in the page too, as JSON in a data block
(``<script type="application/json">``, which a browser does not run), so a page
exported here is read back as the report it was made from. A package's own
HTML report holds no such block and is not read: its ``_success`` and
``_failure`` JSON or XML files beside it are.

Every word of the report is escaped on its way into the page.
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping
from html import escape

from pybreeze.utils.exception.exception_tags import report_html_error
from pybreeze.utils.exception.exceptions import ExecutionReportException
from pybreeze.utils.execution_report.report_schema import ExecutionReport, ExecutionResult, Status

# The data block that carries the report
BLOCK_ID = "pybreeze-execution-report"
_BLOCK = re.compile(
    rf'<script type="application/json" id="{BLOCK_ID}">(.*?)</script>', re.DOTALL)
# Each status and the language key of its name
STATUS_WORDS: dict[Status, str] = {
    Status.PASSED: "report_status_passed",
    Status.FAILED: "report_status_failed",
    Status.ERROR: "report_status_error",
    Status.SKIPPED: "report_status_skipped",
}
_STYLE = """
body { font-family: system-ui, sans-serif; margin: 2em; color: #1b1f24; }
h1 { font-size: 1.4em; margin-bottom: 0.2em; }
p.summary { color: #57606a; margin-top: 0; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 0.3em 0.6em; border-bottom: 1px solid #d0d7de; vertical-align: top; }
td.passed { color: #1a7f37; } td.failed { color: #cf222e; } td.error { color: #9a3412; } td.skipped { color: #57606a; }
pre { white-space: pre-wrap; margin: 0.3em 0; background: #f6f8fa; padding: 0.5em; }
summary { cursor: pointer; }
"""


def _when(seconds: float | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds)) if seconds is not None else ""


def _took(seconds: float | None) -> str:
    return f"{seconds:.2f}" if seconds is not None else ""


def _rows(results: tuple[ExecutionResult, ...], words: Mapping[str, str]) -> list[str]:
    """One table row a result, indented by its depth. Without recursion: a report is as deep as it likes."""
    rows = []
    pending = [(0, result) for result in reversed(results)]
    while pending:
        depth, result = pending.pop()
        detail = ""
        said = "\n".join(filter(None, (
            result.error.trace or result.error.message if result.error is not None else "",
            result.stdout, result.stderr)))
        if said:
            headline = result.error.message if result.error is not None and result.error.message else (
                words["report_html_output"])
            detail = f"<details><summary>{escape(headline)}</summary><pre>{escape(said)}</pre></details>"
        rows.append(
            f'<tr><td style="padding-left: {0.6 + 1.2 * depth:.1f}em">{escape(result.name)}</td>'
            f'<td class="{result.status.value}">{escape(words[STATUS_WORDS[result.status]])}</td>'
            f"<td>{_took(result.duration)}</td><td>{detail}</td></tr>")
        pending.extend((depth + 1, child) for child in reversed(result.children))
    return rows


def html_from_report(report: ExecutionReport, words: Mapping[str, str]) -> str:
    """*report* as an HTML page.

    :param words: the page's own words, by language key (a PyBreeze dictionary)
    """
    counts = report.counts()
    summary = " · ".join(filter(None, (
        report.framework, words[STATUS_WORDS[report.status]],
        *(f"{words[key]}: {counts[status]}" for status, key in STATUS_WORDS.items() if counts[status]),
        _when(report.started),
        words["report_html_seconds"].format(seconds=_took(report.duration)) if report.duration is not None else "")))
    title = report.name or report.framework
    # In a data block a "<" could end the block; as an escape it means the same to JSON
    carried = json.dumps(report.to_dict(), ensure_ascii=False).replace("<", "\\u003c")
    return "\n".join((
        "<!DOCTYPE html>",
        "<html>",
        f'<head><meta charset="utf-8"><title>{escape(title)}</title><style>{_STYLE}</style></head>',
        "<body>",
        f"<h1>{escape(title)}</h1>",
        f'<p class="summary">{escape(summary)}</p>',
        "<table>",
        f"<tr><th>{escape(words['report_column_name'])}</th><th>{escape(words['report_column_status'])}</th>"
        f"<th>{escape(words['report_column_seconds'])}</th><th>{escape(words['report_html_detail'])}</th></tr>",
        *_rows(report.results, words),
        "</table>",
        f'<script type="application/json" id="{BLOCK_ID}">{carried}</script>',
        "</body>",
        "</html>",
        ""))


def report_from_html(text: str) -> ExecutionReport:
    """The report a page exported by :func:`html_from_report` carries.

    :raises ExecutionReportException: when the page carries none, or what it carries is not a report
    """
    block = _BLOCK.search(text)
    if block is None:
        raise ExecutionReportException(report_html_error)
    try:
        data = json.loads(block.group(1))
    except (ValueError, RecursionError) as error:
        raise ExecutionReportException(report_html_error) from error
    return ExecutionReport.from_dict(data)

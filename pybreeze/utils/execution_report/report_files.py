"""Reports read from files and written to them: which adapter a file needs, told from the file.

A report comes as one of:

- an execution report PyBreeze wrote (JSON), or a page it exported (HTML);
- an automation package's record files: ``<name>_success.json`` and
  ``<name>_failure.json``, or the ``.xml`` pair. Either of the two is opened and
  the other is read with it, so a run is one report;
- JUnit XML.

What a file is, is told from what it holds, not from its name: every ``.json``
is tried as each of the JSON kinds. A file is read with a size limit, and as
data throughout: nothing in it is run, and XML that declares a document type is
refused (``safe_xml.py``).

Written, a report is JSON (the report itself), JUnit XML (for a CI service) or
HTML (for people).
"""
from __future__ import annotations

import json
import locale
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from pybreeze.utils.exception.exception_tags import report_format_error
from pybreeze.utils.exception.exceptions import ExecutionReportException
from pybreeze.utils.execution_report.html_report import html_from_report, report_from_html
from pybreeze.utils.execution_report.junit_xml import is_junit, junit_from_report, report_from_junit
from pybreeze.utils.execution_report.record_reports import (
    FAILURE_PREFIX, XML_ROOT, is_records, records_from_json, records_from_xml, report_from_records,
)
from pybreeze.utils.execution_report.report_schema import ExecutionReport
from pybreeze.utils.execution_report.safe_xml import parse_xml
from pybreeze.utils.file_process.replace_file import replace_text
from pybreeze.utils.json_format.view_safe import escape_for_view
from pybreeze.utils.logging.logger import pybreeze_logger

# A report larger than this is not opened
MAX_REPORT_BYTES = 64 * 1024 * 1024
# How the two files of a package's run end, before the extension
_SUCCESS, _FAILURE = "_success", "_failure"
_HTML_SUFFIXES = (".html", ".htm")


@dataclass(frozen=True)
class ExportFormat:
    """A way a report is written.

    :param key: what names it
    :param label_key: the language key of its name
    :param extension: the extension of the file, without the dot
    :param write: gives the file's text for a report and the page's words
    """

    key: str
    label_key: str
    extension: str
    write: Callable[[ExecutionReport, Mapping[str, str]], str]


def _as_json(report: ExecutionReport, _words: Mapping[str, str]) -> str:
    return escape_for_view(json.dumps(report.to_dict(), indent=2, ensure_ascii=False)) + "\n"


EXPORT_FORMATS: tuple[ExportFormat, ...] = (
    ExportFormat("json", "report_format_json", "json", _as_json),
    ExportFormat("junit", "report_format_junit", "xml", lambda report, _words: junit_from_report(report)),
    ExportFormat("html", "report_format_html", "html", html_from_report),
)


def read_text(path: Path) -> str:
    """The text of the report file *path*.

    The packages write some of their files in the machine's own encoding (an
    XML report on Windows): what is not UTF-8 is read as that.

    :raises ExecutionReportException: when the file is larger than a report is
    :raises OSError: when it cannot be read
    """
    if path.stat().st_size > MAX_REPORT_BYTES:
        raise ExecutionReportException(report_format_error)
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode(locale.getpreferredencoding(False), errors="replace")


def _other_half(path: Path) -> Path | None:
    """The other file of a package's run: ``x_failure.json`` for ``x_success.json`` and the reverse, when it is there."""
    stem = path.stem
    for ending, other in ((_SUCCESS, _FAILURE), (_FAILURE, _SUCCESS)):
        if stem.endswith(ending):
            sibling = path.with_name(stem[:-len(ending)] + other + path.suffix)
            return sibling if sibling.is_file() else None
    return None


def _run_name(path: Path) -> str:
    """What a package's run is called: its files' name without ``_success`` or ``_failure``."""
    stem = path.stem
    return next((stem[:-len(ending)] for ending in (_SUCCESS, _FAILURE) if stem.endswith(ending)), stem)


def _from_records(path: Path, records: dict[str, dict], read: Callable[[str], dict[str, dict]]) -> ExecutionReport:
    """The run of which *path* holds *records*, with the records of its other file when there is one."""
    other = _other_half(path)
    if other is not None:
        try:
            records = {**records, **read(read_text(other))}
        except (ExecutionReportException, OSError) as error:
            # The half that was opened is still a report of what it holds
            pybreeze_logger.debug("report_files.py %s read without its other half: %r", path.name, error)
    # What passed first, then what failed, whichever file was opened: the run reads the same from either
    ordered = dict(sorted(records.items(), key=lambda entry: entry[0].startswith(FAILURE_PREFIX)))
    return report_from_records(ordered, _run_name(path))


def _from_json(path: Path, text: str) -> ExecutionReport:
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise ExecutionReportException(report_format_error) from error
    if is_records(data):
        # Also an empty file of a pair (nothing failed): the run is then what its other half holds
        return _from_records(path, data, records_from_json)
    return ExecutionReport.from_dict(data)


def _from_xml(path: Path, text: str) -> ExecutionReport:
    root = parse_xml(text)
    if is_junit(root):
        return report_from_junit(text, path.stem)
    if root.tag == XML_ROOT:
        return _from_records(path, records_from_xml(text), records_from_xml)
    raise ExecutionReportException(report_format_error)


def read_report(path: Path) -> ExecutionReport:
    """The report the file *path* holds, whichever kind it is.

    :raises ExecutionReportException: when it is none of the kinds read
    :raises OSError: when the file cannot be read
    """
    text = read_text(path)
    if path.suffix.lower() in _HTML_SUFFIXES:
        return report_from_html(text)
    opening = text.lstrip()[:1]
    if opening == "<":
        return _from_xml(path, text)
    if opening in ("{", "["):
        return _from_json(path, text)
    raise ExecutionReportException(report_format_error)


def write_report(report: ExecutionReport, path: Path, wanted: ExportFormat, words: Mapping[str, str]) -> None:
    """Write *report* to *path* the way *wanted* says, replacing the file in one step.

    :param words: the words of an HTML page, by language key
    :raises OSError: when the file cannot be written; the one there is left as it was
    """
    replace_text(path, wanted.write(report, words))

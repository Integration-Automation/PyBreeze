# 0012. One viewer for every run: reports are read by adapters and told from their content

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/utils/execution_report/` (`record_reports.py`, `junit_xml.py`, `html_report.py`,
  `report_files.py`, `report_filter.py`, `safe_xml.py`), `pybreeze/pybreeze_ui/report_gui/`;
  `test_report_adapters.py`, `test_report_real_generators.py`, `test_report_filter.py`,
  `test_report_viewer_gui.py`, `fixtures/reports/`

## Context

[0002](0002-execution-report-schema.md) settled the shape every run is reported in. Phase 8 of the
roadmap fills it: each framework's output normalised into it, the framework's own record kept, one
viewer with summary, hierarchy, details and artifacts, import and export in HTML, JSON and XML,
filters by status, duration, framework and failure, stable IDs, and MCP results in the same view.

What the frameworks write was read from the installed packages. APITestka, AutoControl, WebRunner
and LoadDensity all write a run the same way: two files, `<name>_success.json` and
`<name>_failure.json`, or the same two as XML under an `<xml_data>` root, each holding
`Success_Test1`… or `Failure_Test1`… with one record; only what a record holds differs. Their HTML
reports are tables for people. Everything in a record is `str(...)` of the value.

## Decision

1. **A record file is read by what its records hold** (`record_reports.py`): `request_url` or
   `http_method` is APITestka's, `Method` is LoadDensity's, `function_name` is AutoControl's or
   WebRunner's, told apart by how WebRunner names a function (`webdriver wrapper …`,
   `web element …`). Each record is one result, with the record itself as its `raw`.
2. **A run is its two files.** Opening either reads the other with it. What passed and what failed
   are put back in the order they happened when every record has a time, before the results are
   numbered, so the third call of a function has the same ID whichever of the three failed.
3. **How a record ended**: in the success file, passed. In the failure file, failed when the error
   is an assertion (a check did not hold), error otherwise (the run broke); a failed request of a
   load test is a failure.
4. **JUnit XML is read and written** (`junit_xml.py`): suites and cases in, with `failure`, `error`,
   `skipped`, `system-out`, `system-err`; out, a suite per top-level result that holds others,
   every result under it that holds none as a case, the names between as its `classname`.
5. **An HTML page is written for people and carries the report** (`html_report.py`): one file, its
   style inside, no script that runs, every word escaped, and the report as JSON in a data block,
   which is how a page exported here is read back. A package's own HTML report is not read.
6. **What a file is, is told from the file** (`report_files.py`), not from its name: its first
   character says XML or JSON, and then its root element or its keys.
7. **XML is read with nothing switched on** (`safe_xml.py`): a document that declares a document
   type or an entity is refused, and depth and size are capped.
8. **Filtering is a function of results** (`report_filter.py`): by ending, by time taken, by text
   (in a result's name, its error, or the name of what holds it), by package. A result that holds
   others is kept when something under it is.
9. **The viewer holds several runs** and filters them together; a run's items are made as they are
   opened. The paths a report names are listed, not opened.
10. **Another tool hands a run over with `ReportViewerGUI.show_report()`.** The MCP tab does, for
    its session.

## Alternatives considered

- **Parsing the packages' HTML reports.** They are generated tables with the same records as the
  JSON beside them, minus the structure. Reading them would be a scraper for four layouts that the
  packages may restyle.
- **Asking the user which package a file is from.** The records say, in all cases found; a file
  nobody can place is refused rather than guessed.
- **Deriving a step's duration from the next step's time.** The gap includes whatever happened
  between two calls. A duration is given only where the package measured one (APITestka's
  `request_time_sec`, JUnit's `time`, an MCP call's).
- **`defusedxml` for reading XML.** One more dependency for one function: refusing the document
  type declaration with the standard library's parser is what it does.
- **A page with scripts** (sorting, folding). It would have to be trusted to run wherever it is
  opened; `<details>` folds without one.
- **Opening an attachment from the viewer.** The path is whatever the report file says; opening it
  hands a file from elsewhere a way to have a program started.

## Consequences

- A further format is a function from text to `ExecutionReport`, a branch in `read_report()`, and,
  to be written, one `ExportFormat` line.
- The two-file layout, the `Success_Test` / `Failure_Test` names, the `<xml_data>` root and the
  field names of the four packages are relied on (`architecture.md` §6).
  `test_report_real_generators.py` runs each installed package's own JSON and XML generators in a
  process of its own, on a few records, and reads what they write: a package that changes its
  layout fails a test here. The fixtures under `fixtures/reports/` are the same shapes, by hand.
- JUnit has two levels: a deeper report written as JUnit keeps every ending and loses the nesting
  to `classname`. JSON and HTML give the report back whole.
- APITestka writes every failure under the same key (`Failure_Test`, without a number), so its
  failure file holds the last failure only. The adapter reads what is there.
- A file is read whole (64 MB at most), and a run of 3,000 results opens with 3,001 items.
- LSP diagnostics are not in the viewer: a file's diagnostics are not a run. A report made from
  them would be one more adapter.

# 0007. A header finding has a rule, and the findings are exported as SARIF

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/utils/header_tools/` (`header_rules.py`, `header_sarif.py`, `header_analyzer.py`),
  `pybreeze/pybreeze_ui/tools_gui/header_analyzer_gui.py`; `test_header_sarif.py`

## Context

The header analyzer reported a finding as a code, a level, a header name and a detail, and the IDE
turned the code into a translated sentence. That is enough for a person reading the tab. The
roadmap's Phase 3 wants the same findings in security tooling and CI: a stable finding model (rule
ID, level, message, location, help URI, remediation), SARIF 2.1.0 output to a file or standard
output in a fixed order, fields GitHub Code Scanning accepts, and no credential in what is written.

## Decision

1. **A finding's code is its rule ID, and a rule says the rest once.** `HeaderRule` holds a name,
   the default level, what the rule looks for, the sentence for one finding, what to do about it
   and where it is explained. One rule per code, in `header_rules.py`.
2. **The English sentence has one home.** The English dictionary takes each `header_finding_*`
   entry from the rule's `message`, as it takes the tools' error texts from `exception_tags`. The
   IDE and an exported report say the same thing about one finding because it is the same string.
3. **A header and a finding know their line.** `parse_headers` records the line each header starts
   on, and a finding carries the line of the header it is about. A finding about the block as a
   whole (a header that is missing) has none.
4. **SARIF is written the same way every time.** All rules, in the order of their ids; results in
   the order of their lines, then of their rules. The text is indented ASCII JSON.
5. **A result has what a code-scanning service needs and nothing it should not have**: its rule by
   id and by index, a level (`warning`, or `note` for an info), the English sentence, the file and
   the line, and a fingerprint made of the rule, the header's name and the detail. No line of the
   input is quoted.
6. **A finding without a line is placed on line 1.** A result must have a place in a file.
7. **It runs without the IDE.** `python -m pybreeze.utils.header_tools.header_sarif FILE` (or `-`
   for standard input) writes to standard output or to `-o`; `--fail-on-warning` exits with 1 when
   a finding is a warning. It imports no Qt.
8. **The tab exports the analysis it shows**, through the same function.

## Alternatives considered

- **Translate the report.** SARIF is read by tools and shown in a service's own interface; its
  consumers expect one language, and a report that differs by the IDE's language setting could not
  be compared across machines.
- **Include the header line as a snippet.** It helps a reader, and it would put an `Authorization`
  or `Cookie` value into a file whose purpose is to be uploaded.
- **Rule ids of the form `PB0001`.** Opaque numbers need a table to be read, and the codes were
  already stable names used by the dictionaries.
- **List only the rules that fired.** A rule's index would then change from one report to the
  next, and a service would see rules come and go.
- **A separate package or a console script for the command.** The analyzer is pure Python inside
  `pybreeze`; `python -m` on its module needs no new entry in the packaging and no Qt.
- **Validate the output against the SARIF JSON schema in the tests.** It needs the schema file and
  a validator among the test dependencies. The tests check the fields the specification and GitHub
  require, by name.

## Consequences

- A new finding needs a `HeaderRule` and a Traditional Chinese sentence; `test_header_sarif.py`
  fails on a code the analyzer reports without a rule, on a rule nothing reports, and on a rule
  without its Chinese sentence.
- `HeaderField` and `HeaderFinding` gained a `line` that is left out of comparisons, so two fields
  of one name and value are still equal wherever they stand.
- The report's file path is the one given on the command line, written with `/`. A service matches
  it against the repository, so the command is to be run from the repository's root on a file
  inside it.
- A finding's detail is the one channel by which a header's value reaches a report, and the
  analyzer fills it with a cookie's name, a count, a directive or a non-secret value, never with a
  credential (`CLAUDE.md`, Security). A test writes a secret into four headers and looks for it in
  the output.
- The exit code is 0 unless `--fail-on-warning` is given: uploading findings and failing a build
  are two decisions.

"""The header analyzer's findings as SARIF 2.1.0, for tools that read findings rather than people.

SARIF is the format code-scanning services take (GitHub Code Scanning among
them): a run of a tool, the rules it knows and the results it found, each with
a place in a file. :func:`to_sarif` writes an analysis as one such run, so the
same findings the IDE shows can be uploaded from CI and tracked there.

What it writes is the same on every run for the same headers: rules in the
order of their ids, results in the order of their lines. A result names its
rule, its level, the sentence the IDE shows (in English), the line of the
header, and a fingerprint that stays the same while the finding does.

No header value reaches the file except through a finding's detail, which the
analyzer never fills with a credential, and no line of the input is quoted: a
report that is uploaded must not carry an ``Authorization`` header with it.

It can be run on its own, without the IDE and without Qt::

    python -m pybreeze.utils.header_tools.header_sarif response-headers.txt -o headers.sarif
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from pybreeze.utils.file_process.read_capped import read_text_capped
from pybreeze.utils.file_process.replace_file import replace_text
from pybreeze.utils.header_tools.header_analyzer import LEVEL_WARNING, HeaderAnalysis, HeaderFinding, analyze_headers
from pybreeze.utils.header_tools.header_rules import RULES, HeaderRule

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
TOOL_NAME = "PyBreeze Header Analyzer"
TOOL_URI = "https://github.com/Integration-Automation/PyBreeze"
# What the headers are called when they did not come from a file
DEFAULT_SOURCE = "headers.txt"
# The analyzer's level -> SARIF's
_SARIF_LEVELS = {LEVEL_WARNING: "warning"}
_SARIF_NOTE = "note"
# A finding about the whole block is placed on its first line: a result needs a place
_FIRST_LINE = 1
# The name of the fingerprint, and how much of the digest is kept
_FINGERPRINT_NAME = "pybreezeHeaderFinding/v1"
_FINGERPRINT_LENGTH = 32
# Bytes that hold the length of each part hashed into a fingerprint
_LENGTH_BYTES = 4
_TAGS = ["security", "http-headers"]
# Process exit codes
_EXIT_OK = 0
_EXIT_WARNINGS = 1
_EXIT_UNREADABLE = 2


def _sarif_level(level: str) -> str:
    return _SARIF_LEVELS.get(level, _SARIF_NOTE)


def _rule_entry(rule: HeaderRule) -> dict:
    """A rule as SARIF's ``reportingDescriptor``."""
    return {
        "id": rule.id,
        "name": rule.name,
        "shortDescription": {"text": rule.summary},
        "fullDescription": {"text": f"{rule.summary} {rule.remediation}"},
        "help": {"text": f"{rule.remediation}\n\nSee {rule.help_uri}"},
        "helpUri": rule.help_uri,
        "defaultConfiguration": {"level": _sarif_level(rule.level)},
        "properties": {"tags": list(_TAGS)},
    }


def _fingerprint(finding: HeaderFinding) -> str:
    """What stays the same while the finding does: its rule, its header and its detail, not its line."""
    digest = hashlib.sha256()
    for part in (finding.code, finding.header.lower(), finding.detail):
        encoded = part.encode("utf-8", "surrogatepass")
        digest.update(len(encoded).to_bytes(_LENGTH_BYTES, "big"))
        digest.update(encoded)
    return digest.hexdigest()[:_FINGERPRINT_LENGTH]


def _result(finding: HeaderFinding, rule_index: dict[str, int], source: str) -> dict:
    """A finding as SARIF's ``result``."""
    rule = RULES[finding.code]
    line = finding.line if finding.line is not None else _FIRST_LINE
    return {
        "ruleId": finding.code,
        "ruleIndex": rule_index[finding.code],
        "level": _sarif_level(finding.level),
        "message": {"text": rule.message.format(header=finding.header, detail=finding.detail)},
        "locations": [{
            "physicalLocation": {
                "artifactLocation": {"uri": source},
                "region": {"startLine": line},
            },
        }],
        "partialFingerprints": {_FINGERPRINT_NAME: _fingerprint(finding)},
    }


def to_sarif(analysis: HeaderAnalysis, source: str = DEFAULT_SOURCE) -> dict:
    """Write *analysis* as a SARIF log of one run.

    :param analysis: what ``analyze_headers`` returned
    :param source: the file the headers came from, as a relative path with ``/``
        between its parts (what a code-scanning service matches against the
        repository); a name for them when they came from nowhere
    :return: the log, as JSON-compatible data
    """
    rules = sorted(RULES.values(), key=lambda rule: rule.id)
    rule_index = {rule.id: index for index, rule in enumerate(rules)}
    findings = sorted(
        analysis.findings,
        key=lambda finding: (finding.line if finding.line is not None else _FIRST_LINE, finding.code,
                             finding.header.lower(), finding.detail))
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [{
            "tool": {"driver": {
                "name": TOOL_NAME,
                "informationUri": TOOL_URI,
                "rules": [_rule_entry(rule) for rule in rules],
            }},
            "results": [_result(finding, rule_index, source) for finding in findings],
        }],
    }


def sarif_text(analysis: HeaderAnalysis, source: str = DEFAULT_SOURCE) -> str:
    """*analysis* as SARIF text: indented JSON ending in a line break, the same for the same findings.

    Written in ASCII (anything else as an escape), so that it can go to a
    console or a pipe whatever encoding that has.
    """
    return json.dumps(to_sarif(analysis, source), indent=2) + "\n"


def write_sarif(path: Path, analysis: HeaderAnalysis, source: str = DEFAULT_SOURCE) -> None:
    """Write *analysis* to *path* as SARIF, replacing the file in one step.

    :raises OSError: when the file cannot be written
    """
    replace_text(path, sarif_text(analysis, source))


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m pybreeze.utils.header_tools.header_sarif",
        description="Analyse a block of HTTP headers and write the findings as SARIF 2.1.0.")
    parser.add_argument("headers", help="the file holding the headers, or - to read them from standard input")
    parser.add_argument("-o", "--output", help="the SARIF file to write; standard output when not given")
    parser.add_argument(
        "--fail-on-warning", action="store_true",
        help="exit with 1 when a finding is a warning (a note never fails the run)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the analyzer from the command line.

    :param argv: the arguments; the process's own when ``None``
    :return: 0, or 1 with ``--fail-on-warning`` and a warning found, or 2 when
        the headers cannot be read or the report cannot be written
    """
    options = _arguments(argv)
    from_stdin = options.headers == "-"
    try:
        text = sys.stdin.read() if from_stdin else read_text_capped(Path(options.headers), encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        sys.stderr.write(f"cannot read the headers: {getattr(error, 'strerror', None) or type(error).__name__}\n")
        return _EXIT_UNREADABLE
    analysis = analyze_headers(text)
    source = DEFAULT_SOURCE if from_stdin else Path(options.headers).as_posix()
    if options.output is None:
        sys.stdout.write(sarif_text(analysis, source))
    else:
        try:
            write_sarif(Path(options.output), analysis, source)
        except OSError as error:
            sys.stderr.write(f"cannot write the report: {error.strerror or type(error).__name__}\n")
            return _EXIT_UNREADABLE
    warned = any(finding.level == LEVEL_WARNING for finding in analysis.findings)
    return _EXIT_WARNINGS if options.fail_on_warning and warned else _EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

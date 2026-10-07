"""The header findings as rules and as SARIF 2.1.0: what a code-scanning service is given."""
from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict as ENGLISH
from pybreeze.extend_multi_language.extend_traditional_chinese import (
    pybreeze_traditional_chinese_word_dict as CHINESE,
)
from pybreeze.utils.header_tools import header_analyzer, header_sarif
from pybreeze.utils.header_tools.header_analyzer import (
    LEVEL_INFO,
    LEVEL_WARNING,
    HeaderField,
    HeaderFinding,
    analyze_headers,
    parse_headers,
)
from pybreeze.utils.header_tools.header_rules import HEADER_FINDING_KEY_PREFIX, RULES
from pybreeze.utils.header_tools.header_sarif import main, sarif_text, to_sarif, write_sarif

# A response with something for most rules, and credentials that must go nowhere
_SECRET = "s3cr3t-V4lue"
_HEADERS = "\n".join([
    "HTTP/1.1 200 OK",
    "Server: nginx/1.25.3",
    f"Set-Cookie: session={_SECRET}; Path=/",
    f"Authorization: Bearer {_SECRET}",
    f"X-Api-Key: {_SECRET}",
    "Content-Type: text/html",
    "X-Request-Id: a",
    "X-Request-Id: b",
    "Strict-Transport-Security: max-age=60",
    "Access-Control-Allow-Origin: *",
])


def _codes_the_analyzer_reports() -> set[str]:
    """Every finding code written in the analyzer's source: the first argument of ``HeaderFinding(...)``."""
    source = Path(header_analyzer.__file__).read_text(encoding="utf-8")
    written = set(re.findall(r'HeaderFinding\(\s*"(\w+)"', source))
    return written | {code for _name, _canonical, code in header_analyzer._RESPONSE_SECURITY_HEADERS}


class TestRules:
    def test_every_finding_the_analyzer_reports_has_a_rule_and_no_rule_is_left_over(self):
        assert _codes_the_analyzer_reports() == set(RULES)

    @pytest.mark.parametrize("rule", RULES.values(), ids=lambda rule: rule.id)
    def test_a_rule_says_everything_a_tool_asks_of_it(self, rule):
        assert rule.level in (LEVEL_WARNING, LEVEL_INFO)
        assert re.fullmatch(r"[A-Z][A-Za-z]+", rule.name)
        assert rule.summary.endswith(".") and "{" not in rule.summary
        assert rule.remediation.endswith(".") and "{" not in rule.remediation
        assert rule.help_uri.startswith("https://")
        assert set(re.findall(r"\{(\w+)\}", rule.message)) <= {"header", "detail"}
        assert rule.message.startswith("{header}: ")

    def test_names_are_not_shared(self):
        names = [rule.name for rule in RULES.values()]

        assert len(set(names)) == len(names)

    def test_the_ide_says_in_english_what_the_rule_says(self):
        for rule in RULES.values():
            assert ENGLISH[HEADER_FINDING_KEY_PREFIX + rule.id] == rule.message

    def test_every_rule_has_its_sentence_in_chinese(self):
        missing = [rule.id for rule in RULES.values() if HEADER_FINDING_KEY_PREFIX + rule.id not in CHINESE]

        assert missing == []

    def test_a_rules_level_is_the_level_its_findings_are_reported_at(self):
        levels = {finding.code: finding.level for finding in analyze_headers(_HEADERS).findings}

        assert levels
        assert all(RULES[code].level == level for code, level in levels.items())


class TestLines:
    def test_a_header_knows_the_line_it_is_on(self):
        fields = parse_headers("HTTP/1.1 200 OK\nA: 1\n\tfolded\nB: 2\n\nbody: not a header")

        assert [(header.name, header.value, header.line) for header in fields] == [("A", "1 folded", 2), ("B", "2", 4)]

    def test_two_headers_alike_are_equal_wherever_they_stand(self):
        assert HeaderField("A", "1", line=3) == HeaderField("A", "1")
        assert HeaderFinding("server_banner", LEVEL_INFO, "Server", "x", line=2) == HeaderFinding(
            "server_banner", LEVEL_INFO, "Server", "x")

    def test_a_finding_about_a_header_is_on_its_line(self):
        lines = {(finding.code, finding.line) for finding in analyze_headers(_HEADERS).findings}

        assert {("server_banner", 2), ("cookie_not_secure", 3), ("sensitive_header", 4), ("sensitive_header", 5),
                ("content_type_no_charset", 6), ("hsts_weak_max_age", 9), ("cors_wildcard_origin", 10)} <= lines

    def test_a_repeated_header_is_reported_at_its_first_repeat(self):
        finding = next(f for f in analyze_headers(_HEADERS).findings if f.code == "duplicate_header")

        assert finding.line == 8

    def test_a_wildcard_with_credentials_is_reported_at_the_origin_header(self):
        analysis = analyze_headers("Access-Control-Allow-Credentials: true\nAccess-Control-Allow-Origin: *")
        finding = next(f for f in analysis.findings if f.code == "cors_wildcard_with_credentials")

        assert finding.line == 2

    def test_a_missing_header_is_on_no_line(self):
        missing = [finding.line for finding in analyze_headers(_HEADERS).findings if finding.code.startswith("missing_")]

        assert missing and set(missing) == {None}


def _run(text: str = _HEADERS, source: str = "captures/response.txt") -> dict:
    [run] = to_sarif(analyze_headers(text), source)["runs"]
    return run


class TestSarif:
    def test_it_is_a_sarif_2_1_0_log_of_one_run(self):
        log = to_sarif(analyze_headers(_HEADERS))

        assert log["version"] == "2.1.0"
        assert log["$schema"].endswith("sarif-2.1.0.json")
        assert len(log["runs"]) == 1
        assert list(log) == ["$schema", "version", "runs"]

    def test_the_tool_names_itself_and_lists_every_rule_by_id(self):
        driver = _run()["tool"]["driver"]

        assert driver["name"] == "PyBreeze Header Analyzer"
        assert driver["informationUri"].startswith("https://")
        assert [rule["id"] for rule in driver["rules"]] == sorted(RULES)

    def test_a_rule_carries_what_code_scanning_shows_for_it(self):
        for entry in _run()["tool"]["driver"]["rules"]:
            rule = RULES[entry["id"]]
            assert entry["name"] == rule.name
            assert entry["shortDescription"]["text"] == rule.summary
            assert rule.remediation in entry["fullDescription"]["text"]
            assert rule.remediation in entry["help"]["text"] and rule.help_uri in entry["help"]["text"]
            assert entry["helpUri"] == rule.help_uri
            assert entry["defaultConfiguration"]["level"] in ("warning", "note")
            assert entry["properties"]["tags"] == ["security", "http-headers"]

    def test_a_result_names_its_rule_by_id_and_by_place_in_the_list(self):
        run = _run()
        rules = run["tool"]["driver"]["rules"]

        assert run["results"]
        for result in run["results"]:
            assert rules[result["ruleIndex"]]["id"] == result["ruleId"]

    def test_a_warning_is_a_warning_and_the_rest_are_notes(self):
        levels = {result["ruleId"]: result["level"] for result in _run()["results"]}

        assert levels["cookie_not_secure"] == "warning"
        assert levels["server_banner"] == "note"
        assert set(levels.values()) == {"warning", "note"}

    def test_a_result_says_what_the_ide_says_in_english(self):
        messages = {result["ruleId"]: result["message"]["text"] for result in _run()["results"]}

        assert messages["server_banner"] == "Server: 'nginx/1.25.3' reveals the software in use."
        assert messages["hsts_weak_max_age"] == (
            "Strict-Transport-Security: max-age=60 is short; 15552000 (180 days) is the usual minimum.")

    def test_a_result_is_placed_in_the_file_it_came_from_on_its_line(self):
        places = {result["ruleId"]: result["locations"][0]["physicalLocation"] for result in _run()["results"]}

        assert places["server_banner"] == {
            "artifactLocation": {"uri": "captures/response.txt"}, "region": {"startLine": 2}}
        # About the whole block: placed on the first line, since a result needs a place
        assert places["missing_csp"]["region"] == {"startLine": 1}

    def test_every_result_has_the_fields_code_scanning_needs(self):
        for result in _run()["results"]:
            assert result["message"]["text"]
            [location] = result["locations"]
            physical = location["physicalLocation"]
            assert physical["region"]["startLine"] >= 1
            uri = physical["artifactLocation"]["uri"]
            assert "\\" not in uri and "://" not in uri and not uri.startswith("/")
            assert result["partialFingerprints"]

    def test_results_come_in_the_order_of_their_lines_then_their_rules(self):
        order = [(result["locations"][0]["physicalLocation"]["region"]["startLine"], result["ruleId"])
                 for result in _run()["results"]]

        assert order == sorted(order)

    def test_the_same_headers_give_the_same_text(self):
        assert sarif_text(analyze_headers(_HEADERS)) == sarif_text(analyze_headers(_HEADERS))

    def test_no_credential_reaches_the_report(self):
        text = sarif_text(analyze_headers(_HEADERS))

        assert _SECRET not in text
        assert "session" in text  # a cookie's name is said, its value is not

    def test_the_text_is_ascii_json_ending_in_a_line_break(self):
        text = sarif_text(analyze_headers("Set-Cookie: 名稱=1"))

        assert text.isascii() and text.endswith("}\n")
        assert "名稱" in json.loads(text)["runs"][0]["results"][0]["message"]["text"]

    def test_headers_with_nothing_to_report_give_a_run_without_results(self):
        run = _run("Accept: application/json")

        assert run["results"] == []
        assert len(run["tool"]["driver"]["rules"]) == len(RULES)

    def test_a_fingerprint_stays_while_the_finding_does_and_moves_with_nothing_else(self):
        def fingerprints(text: str) -> dict:
            return {result["ruleId"]: result["partialFingerprints"]["pybreezeHeaderFinding/v1"]
                    for result in _run(text)["results"] if not result["ruleId"].startswith("missing_")}

        here = fingerprints("Server: nginx\nSet-Cookie: a=1")
        moved = fingerprints("X-Other: 1\nX-More: 2\nServer: nginx")
        changed = fingerprints("Server: apache")

        assert here["server_banner"] == moved["server_banner"]
        assert here["server_banner"] != changed["server_banner"]
        assert len(set(here.values())) == len(here)
        assert re.fullmatch(r"[0-9a-f]{32}", here["server_banner"])

    def test_it_is_written_to_a_file_whole(self, tmp_path):
        target = tmp_path / "headers.sarif"
        analysis = analyze_headers(_HEADERS)

        write_sarif(target, analysis, "response.txt")

        assert target.read_text(encoding="utf-8") == sarif_text(analysis, "response.txt")
        assert [entry.name for entry in tmp_path.iterdir()] == ["headers.sarif"]


class TestCommandLine:
    @pytest.fixture
    def headers_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "captures").mkdir()
        (tmp_path / "captures" / "response.txt").write_text(_HEADERS, encoding="utf-8")
        return "captures/response.txt"

    def test_a_file_is_analysed_to_standard_output(self, headers_file, capsys):
        assert main([headers_file]) == 0

        log = json.loads(capsys.readouterr().out)
        uris = {result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
                for result in log["runs"][0]["results"]}
        assert uris == {"captures/response.txt"}

    def test_a_path_written_the_windows_way_is_named_with_slashes(self, headers_file, capsys):
        if os.sep != "\\":
            pytest.skip("a backslash separates folders on Windows only")

        assert main(["captures\\response.txt"]) == 0

        assert '"uri": "captures/response.txt"' in capsys.readouterr().out

    def test_it_is_written_to_the_file_asked_for(self, headers_file, capsys, tmp_path):
        assert main([headers_file, "-o", "out.sarif"]) == 0

        assert capsys.readouterr().out == ""
        assert json.loads((tmp_path / "out.sarif").read_text(encoding="utf-8"))["version"] == "2.1.0"

    def test_headers_come_from_standard_input_too(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO("Authorization: Bearer token"))

        assert main(["-"]) == 0

        [result] = json.loads(capsys.readouterr().out)["runs"][0]["results"]
        assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "headers.txt"

    def test_a_warning_fails_the_run_only_when_asked_to(self, headers_file, capsys):
        assert main([headers_file]) == 0
        assert main([headers_file, "--fail-on-warning"]) == 1
        capsys.readouterr()

    def test_notes_alone_never_fail_the_run(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        Path("notes.txt").write_text("Server: nginx", encoding="utf-8")

        assert main(["notes.txt", "--fail-on-warning"]) == 0
        capsys.readouterr()

    def test_a_file_that_is_not_there_is_said_and_nothing_is_written(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)

        assert main(["missing.txt"]) == 2

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err.startswith("cannot read the headers: ")

    def test_a_file_that_is_not_text_is_said(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        Path("binary.txt").write_bytes(b"\xff\xfe\x00\x80")

        assert main(["binary.txt"]) == 2
        assert "cannot read the headers" in capsys.readouterr().err

    def test_a_report_that_cannot_be_written_is_said(self, headers_file, capsys, monkeypatch):
        def refuse(_path, _analysis, _source):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(header_sarif, "write_sarif", refuse)

        assert main([headers_file, "-o", "out.sarif"]) == 2
        assert capsys.readouterr().err == "cannot write the report: Permission denied\n"

    def test_it_runs_as_a_module_without_qt(self, headers_file):
        import subprocess

        from pybreeze.utils.subprocess_util import no_window_creationflags, utf8_subprocess_env

        probe = ("import runpy, sys\n"
                 "sys.argv = ['header_sarif', 'captures/response.txt', '-o', 'out.sarif']\n"
                 "try:\n"
                 "    runpy.run_module('pybreeze.utils.header_tools.header_sarif', run_name='__main__')\n"
                 "except SystemExit as stop:\n"
                 "    print(stop.code, 'PySide6' in sys.modules, 'je_editor' in sys.modules)\n")
        environment = utf8_subprocess_env()
        environment["PYTHONPATH"] = str(Path(header_sarif.__file__).resolve().parents[3])
        child = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, timeout=120, check=False, shell=False,
            env=environment, creationflags=no_window_creationflags())

        assert child.stdout.decode("utf-8").split() == ["0", "False", "False"], child.stderr.decode("utf-8", "replace")
        assert Path("out.sarif").is_file()


class TestTheTab:
    @pytest.fixture(scope="class")
    def app(self):
        from PySide6.QtWidgets import QApplication

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict

        instance = QApplication.instance() or QApplication([])
        update_language_dict()
        return instance

    @pytest.fixture
    def tab(self, app):
        from pybreeze.pybreeze_ui.tools_gui.header_analyzer_gui import HeaderAnalyzerGUI

        made = HeaderAnalyzerGUI()
        yield made
        made.deleteLater()

    @staticmethod
    def _choose(monkeypatch, path: str) -> list:
        from PySide6.QtWidgets import QFileDialog

        asked: list = []

        def chosen(_parent, title, suggested, filters):
            asked.append((title, suggested, filters))
            return path, ""

        monkeypatch.setattr(QFileDialog, "getSaveFileName", chosen)
        return asked

    def test_there_is_nothing_to_export_before_an_analysis(self, tab):
        assert not tab.export_sarif_button.isEnabled()
        assert tab.export_sarif() is None

    def test_an_analysis_can_be_exported(self, tab, tmp_path, monkeypatch):
        target = tmp_path / "found.sarif"
        asked = self._choose(monkeypatch, str(target))
        tab.input_edit.setPlainText(_HEADERS)
        tab.analyze()

        assert tab.export_sarif_button.isEnabled()
        assert tab.export_sarif() == str(target)

        log = json.loads(target.read_text(encoding="utf-8"))
        assert log["runs"][0]["results"]
        assert _SECRET not in target.read_text(encoding="utf-8")
        assert asked == [("Export findings as SARIF", "headers.sarif", "SARIF (*.sarif);;JSON (*.json)")]

    def test_the_button_exports(self, tab, tmp_path, monkeypatch):
        target = tmp_path / "clicked.sarif"
        self._choose(monkeypatch, str(target))
        tab.input_edit.setPlainText(_HEADERS)
        tab.analyze()

        tab.export_sarif_button.click()

        assert target.is_file()

    def test_a_dialog_closed_without_a_name_writes_nothing(self, tab, tmp_path, monkeypatch):
        self._choose(monkeypatch, "")
        tab.input_edit.setPlainText(_HEADERS)
        tab.analyze()

        assert tab.export_sarif() is None
        assert list(tmp_path.iterdir()) == []

    def test_text_without_headers_takes_the_export_away_again(self, tab):
        tab.input_edit.setPlainText(_HEADERS)
        tab.analyze()

        tab.input_edit.setPlainText("no headers here")
        tab.analyze()

        assert not tab.export_sarif_button.isEnabled()

    def test_a_file_that_cannot_be_written_is_said_and_not_claimed(self, tab, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        from pybreeze.pybreeze_ui.tools_gui import header_analyzer_gui

        def refuse(_path, _analysis):
            raise PermissionError(13, "Permission denied")

        said: list = []
        self._choose(monkeypatch, str(tmp_path / "<i>report.sarif"))
        monkeypatch.setattr(header_analyzer_gui, "write_sarif", refuse)
        monkeypatch.setattr(QMessageBox, "warning", lambda _parent, title, text: said.append((title, text)))
        tab.input_edit.setPlainText(_HEADERS)
        tab.analyze()

        assert tab.export_sarif() is None

        [(title, text)] = said
        assert title == "Not saved"
        assert "Permission denied" in text
        # The file's name is shown as text, not as markup
        assert "<i>" not in text and "&lt;i&gt;report.sarif" in text

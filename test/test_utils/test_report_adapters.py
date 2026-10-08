"""Reports read into the common shape from every kind of file, and written back out."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict as WORDS
from pybreeze.utils.exception.exceptions import ExecutionReportException
from pybreeze.utils.execution_report import report_files
from pybreeze.utils.execution_report.html_report import BLOCK_ID, html_from_report, report_from_html
from pybreeze.utils.execution_report.junit_xml import junit_from_report, report_from_junit
from pybreeze.utils.execution_report.record_reports import (
    API_TESTKA,
    AUTO_CONTROL,
    LOAD_DENSITY,
    WEB_RUNNER,
    framework_of_records,
    records_from_json,
    records_from_xml,
    report_from_records,
)
from pybreeze.utils.execution_report.report_files import EXPORT_FORMATS, read_report, write_report
from pybreeze.utils.execution_report.report_schema import (
    ErrorDetail,
    ExecutionReport,
    ExecutionResult,
    ResultKind,
    Status,
    stable_id,
)
from pybreeze.utils.execution_report.safe_xml import MAX_DEPTH, XmlElement, parse_xml, write_xml

FIXTURES = Path(__file__).parent / "fixtures" / "reports"
FORMATS = {each.key: each for each in EXPORT_FORMATS}


def _statuses(report: ExecutionReport) -> list[tuple[str, Status]]:
    return [(result.name, result.status) for result in report.walk()]


# ----------------------------------------------------------------------
# The packages' own record files
# ----------------------------------------------------------------------

def test_an_apitestka_run_is_its_requests_with_their_times_and_the_one_that_failed():
    report = read_report(FIXTURES / "api_success.json")

    assert (report.framework, report.name) == (API_TESTKA, "api")
    assert _statuses(report) == [
        ("GET https://example.com/api/users/1", Status.PASSED), ("POST https://example.com/api/users", Status.PASSED),
        ("get https://example.com/api/missing", Status.FAILED)]
    first = report.results[0]
    assert (first.kind, first.duration) == (ResultKind.TEST, 0.182)
    assert first.stdout == '{"id": 1, "name": "demo"}'
    assert first.raw["status_code"] == "200"
    failed = report.results[2]
    assert (failed.error.kind, failed.error.message) == (
        "APIAssertException", "APIAssertException('value should be 200 but value was 404')")


def test_either_file_of_a_run_opens_the_whole_run():
    assert read_report(FIXTURES / "api_failure.json") == read_report(FIXTURES / "api_success.json")
    assert read_report(FIXTURES / "web_failure.json") == read_report(FIXTURES / "web_success.json")


def test_a_webrunner_run_is_put_back_in_the_order_it_happened():
    report = read_report(FIXTURES / "web_success.json")

    assert report.framework == WEB_RUNNER
    assert _statuses(report) == [
        ("web runner manager new_driver", Status.PASSED), ("webdriver wrapper to_url", Status.PASSED),
        ("webdriver wrapper find_element", Status.ERROR), ("webdriver wrapper to_url", Status.FAILED),
        ("web runner manager quit", Status.PASSED)]
    assert all(result.kind is ResultKind.STEP for result in report.results)
    assert report.results[2].error.kind == "NoSuchElementException"
    assert report.results[0].raw["param"] == "{'webdriver_name': 'chrome', 'options': None}"
    assert report.started == report.results[0].started


def test_the_same_step_called_twice_has_two_ids_that_do_not_depend_on_which_failed():
    report = read_report(FIXTURES / "web_success.json")
    visits = [result for result in report.results if result.name == "webdriver wrapper to_url"]

    assert [visit.id for visit in visits] == [
        stable_id(WEB_RUNNER, "webdriver wrapper to_url", 0), stable_id(WEB_RUNNER, "webdriver wrapper to_url", 1)]
    assert [visit.status for visit in visits] == [Status.PASSED, Status.FAILED]


def test_an_autocontrol_run_is_read_from_its_xml_files():
    report = read_report(FIXTURES / "desktop_failure.xml")

    assert (report.framework, report.name) == (AUTO_CONTROL, "desktop")
    assert _statuses(report) == [
        ("set_mouse_position", Status.PASSED), ("click_mouse", Status.PASSED), ("locate_image_center", Status.ERROR)]
    assert report.results[2].error.message == "ImageNotFoundException('could not find <button.png> on screen')"


def test_a_loaddensity_run_is_its_requests_and_a_failed_request_is_a_failure():
    report = read_report(FIXTURES / "load_success.json")

    assert report.framework == LOAD_DENSITY
    assert _statuses(report) == [("GET /", Status.PASSED), ("GET /", Status.PASSED), ("POST /login", Status.FAILED)]
    assert report.results[0].id != report.results[1].id
    assert report.results[2].error.kind == "HTTPError"
    assert report.started is None


def test_a_file_without_its_other_half_is_a_report_of_what_it_holds(tmp_path):
    shutil.copy(FIXTURES / "web_failure.json", tmp_path / "alone_failure.json")

    report = read_report(tmp_path / "alone_failure.json")

    assert (report.name, len(report.results)) == ("alone", 2)


def test_a_run_in_which_nothing_failed_is_read_from_its_empty_failure_file(tmp_path):
    shutil.copy(FIXTURES / "load_success.json", tmp_path / "run_success.json")
    (tmp_path / "run_failure.json").write_text("{}", encoding="utf-8")

    assert len(read_report(tmp_path / "run_failure.json").results) == 2


def test_a_record_file_under_any_name_is_told_by_what_it_holds(tmp_path):
    shutil.copy(FIXTURES / "api_success.json", tmp_path / "whatever.json")

    assert read_report(tmp_path / "whatever.json").framework == API_TESTKA


@pytest.mark.parametrize(("records", "framework"), [
    ({"Success_Test1": {"function_name": "Web element click_element"}}, WEB_RUNNER),
    ({"Success_Test1": {"function_name": "click_mouse"}}, AUTO_CONTROL),
    ({"Failure_Test1": {"Method": "GET", "test_url": "x"}}, LOAD_DENSITY),
    ({"Failure_Test": {"http_method": "get", "test_url": "x"}}, API_TESTKA),
    ({"Success_Test1": {"request_url": "x"}}, API_TESTKA),
    ({"Success_Test1": {"something": "else"}}, None),
    ({}, None),
])
def test_the_package_that_wrote_records_is_told_from_what_a_record_holds(records, framework):
    assert framework_of_records(records) == framework


def test_records_nobody_can_place_are_not_a_report_unless_the_package_is_given():
    records = {"Success_Test1": {"function_name": "anything"}, "Failure_Test1": {"something": "else"}}

    with pytest.raises(ExecutionReportException):
        report_from_records({"Success_Test1": {"something": "else"}})
    assert report_from_records(records, "run", WEB_RUNNER).framework == WEB_RUNNER


def test_a_record_with_values_missing_is_still_a_result():
    report = report_from_records({"Failure_Test1": {"function_name": "None", "exception": "None"},
                                  "Success_Test2": {"function_name": "write", "time": "not a time"}})

    assert [(result.name, result.started) for result in report.results] == [("Failure_Test1", None), ("write", None)]
    assert report.results[0].status is Status.ERROR


@pytest.mark.parametrize("text", [
    "", "not json", "[]", "5", '{"Success_Test1": 5}', '{"other": {}}', '{"Success_Test1": {}, "x": {}}',
])
def test_json_that_is_not_a_record_file_is_refused(text):
    with pytest.raises(ExecutionReportException, match="not a report"):
        records_from_json(text)


@pytest.mark.parametrize("text", [
    "<other><Success_Test1><a>b</a></Success_Test1></other>",
    "<xml_data><Something><a>b</a></Something></xml_data>",
])
def test_xml_that_is_not_a_record_file_is_refused(text):
    with pytest.raises(ExecutionReportException, match="not a report"):
        records_from_xml(text)


# ----------------------------------------------------------------------
# JUnit XML
# ----------------------------------------------------------------------

def test_junit_is_read_into_suites_and_tests_with_how_each_ended():
    report = read_report(FIXTURES / "pytest.junit.xml")

    assert (report.framework, report.name) == ("junit", "pytest tests")
    assert _statuses(report) == [
        ("pytest", Status.ERROR), ("test_logs_in", Status.PASSED), ("test_wrong_password", Status.FAILED),
        ("test_avatar", Status.ERROR), ("test_export", Status.SKIPPED), ("slow", Status.PASSED),
        ("test_builds_a_report", Status.PASSED)]
    suite = report.results[0]
    assert (suite.kind, suite.duration) == (ResultKind.SUITE, 1.25)
    assert suite.started is not None


def test_a_junit_case_keeps_its_message_its_trace_and_what_it_printed():
    suite = read_report(FIXTURES / "pytest.junit.xml").results[0]
    failed, broken, skipped = suite.children[1], suite.children[2], suite.children[3]

    assert (failed.error.message, failed.error.kind) == ("assert 200 == 401", "AssertionError")
    assert failed.error.trace.endswith("E       assert 200 == 401")
    assert failed.stdout == "POST /login -> 200"
    assert (failed.duration, failed.raw) == (0.3, {"classname": "tests.test_login"})
    assert (broken.error.kind, broken.stderr) == ("FixtureLookupError", "warning: no storage")
    assert skipped.error.message == "needs the export service"


def test_a_lone_testsuite_is_a_document_too():
    report = report_from_junit('<testsuite name="one"><testcase name="a" classname="c"/></testsuite>', "from the file")

    assert (report.name, _statuses(report)) == ("one", [("one", Status.PASSED), ("a", Status.PASSED)])


def test_two_cases_of_one_name_in_different_classes_have_ids_of_their_own():
    report = report_from_junit(
        '<testsuite name="s"><testcase name="test_it" classname="a"/><testcase name="test_it" classname="b"/>'
        '<testcase name="test_it" classname="a"/></testsuite>')

    assert len({case.id for case in report.results[0].children}) == 3


def test_a_report_written_as_junit_has_the_counts_a_ci_service_reads():
    root = parse_xml(junit_from_report(read_report(FIXTURES / "pytest.junit.xml")))

    assert root.tag == "testsuites"
    assert {key: root.attributes[key] for key in ("tests", "failures", "errors", "skipped")} == {
        "tests": "5", "failures": "1", "errors": "1", "skipped": "1"}
    (suite,) = root.children
    assert suite.attributes["name"] == "pytest"
    assert [case.attributes["classname"] for case in suite.children] == ["pytest"] * 4 + ["pytest.slow"]


def test_junit_written_and_read_back_tells_the_same_run():
    report = read_report(FIXTURES / "pytest.junit.xml")

    back = report_from_junit(junit_from_report(report))

    cases = [(result.name, result.status, result.duration, result.stdout, result.stderr,
              result.error.message if result.error else None, result.error.kind if result.error else None)
             for result in report.walk() if not result.children]
    assert [(result.name, result.status, result.duration, result.stdout, result.stderr,
             result.error.message if result.error else None, result.error.kind if result.error else None)
            for result in back.walk() if not result.children] == cases


def test_a_packages_run_is_written_as_one_suite_named_after_the_run():
    root = parse_xml(junit_from_report(read_report(FIXTURES / "web_success.json")))

    (suite,) = root.children
    assert (suite.attributes["name"], suite.attributes["tests"], suite.attributes["failures"],
            suite.attributes["errors"]) == ("web", "5", "1", "1")
    broken = suite.children[2]
    assert broken.attributes == {"name": "webdriver wrapper find_element", "classname": "web"}
    assert (broken.children[0].tag, broken.children[0].attributes["type"]) == ("error", "NoSuchElementException")


def test_an_empty_report_is_an_empty_document():
    root = parse_xml(junit_from_report(ExecutionReport("mcp", name="nothing")))

    assert (root.attributes["tests"], root.children) == ("0", [])


@pytest.mark.parametrize("text", ["<html/>", "<testsuite", "not xml at all", ""])
def test_what_is_not_junit_is_refused(text):
    with pytest.raises(ExecutionReportException):
        report_from_junit(text)


# ----------------------------------------------------------------------
# XML read safely
# ----------------------------------------------------------------------

def test_a_document_that_declares_entities_is_refused():
    laughs = ('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
              '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]><testsuite name="&lol2;"/>')

    with pytest.raises(ExecutionReportException, match="document type"):
        parse_xml(laughs)


def test_a_document_that_names_a_file_to_fetch_is_refused():
    with pytest.raises(ExecutionReportException):
        parse_xml('<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><testsuite name="&secret;"/>')


def test_a_document_deeper_than_a_report_is_refused():
    with pytest.raises(ExecutionReportException):
        parse_xml("<a>" * (MAX_DEPTH + 1) + "</a>" * (MAX_DEPTH + 1))

    assert parse_xml("<a>" * MAX_DEPTH + "</a>" * MAX_DEPTH).tag == "a"


def test_an_element_knows_its_attributes_its_text_and_its_children():
    root = parse_xml('<suite name="s"> lead <case id="1">one</case><case id="2"/><other/></suite>')

    assert (root.tag, root.attributes, root.text.strip()) == ("suite", {"name": "s"}, "lead")
    assert [case.attributes["id"] for case in root.all("case")] == ["1", "2"]
    assert root.child("case").text == "one"
    assert root.child("missing") is None


def test_what_is_written_is_escaped_and_what_xml_cannot_hold_is_left_out():
    written = write_xml(XmlElement("case", {"name": 'a "quoted" <name> & more'}, "text with <tags> & \x00\x0b control"))

    back = parse_xml(written)
    assert back.attributes["name"] == 'a "quoted" <name> & more'
    assert back.text == "text with <tags> &  control"


_TEXT = st.text(max_size=20)


@given(name=_TEXT, text=_TEXT, value=_TEXT)
def test_whatever_is_written_is_read_back_as_text(name, text, value):
    from pybreeze.utils.execution_report.safe_xml import xml_text

    back = parse_xml(write_xml(XmlElement("root", {"a": value}, text, [XmlElement("child", {}, name)])))

    # A parser gives every line break in text back as \n
    def normal(written: str) -> str:
        return xml_text(written).replace("\r\n", "\n").replace("\r", "\n")

    # An element that holds others is written with each on a line of its own, which adds white space to its text
    assert back.text.strip() == normal(text).strip()
    assert back.children[0].text == normal(name)
    # An attribute's line breaks and tabs are written as character references and come back as they were
    assert back.attributes["a"] == xml_text(value)


# ----------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------

def test_a_page_shows_the_run_and_carries_the_report():
    report = read_report(FIXTURES / "pytest.junit.xml")

    page = html_from_report(report, WORDS)

    assert page.startswith("<!DOCTYPE html>")
    assert "<h1>pytest tests</h1>" in page
    assert "test_wrong_password" in page and "assert 200 == 401" in page
    assert WORDS["report_status_failed"] in page
    assert page.count("<script") == 1 and f'id="{BLOCK_ID}"' in page
    assert report_from_html(page) == report


def test_nothing_in_a_report_becomes_markup_or_ends_the_data_block():
    hostile = ExecutionReport("mcp", name="<script>alert(1)</script>", results=(ExecutionResult(
        id="1", name='<img src=x onerror="alert(2)">', status=Status.FAILED, stdout="</script><script>alert(3)</script>",
        error=ErrorDetail(message="<b>bold</b>", trace="</pre><h1>big</h1>")),))

    page = html_from_report(hostile, WORDS)

    assert "<script>alert" not in page and "<img" not in page and "<b>bold" not in page and "<h1>big" not in page
    assert page.count("</script>") == 1
    assert report_from_html(page) == hostile


def test_a_page_that_carries_no_report_is_said_to():
    with pytest.raises(ExecutionReportException, match="holds no execution report"):
        report_from_html("<html><body><table><tr><td>a package's own report</td></tr></table></body></html>")


def test_a_page_whose_block_is_not_a_report_is_refused():
    with pytest.raises(ExecutionReportException):
        report_from_html(f'<script type="application/json" id="{BLOCK_ID}">not json</script>')
    with pytest.raises(ExecutionReportException):
        report_from_html(f'<script type="application/json" id="{BLOCK_ID}">{{"schema": 1}}</script>')


# ----------------------------------------------------------------------
# Files
# ----------------------------------------------------------------------

@pytest.mark.parametrize("source", [
    "api_success.json", "web_success.json", "desktop_success.xml", "load_success.json", "pytest.junit.xml",
])
@pytest.mark.parametrize("wanted", ["json", "html"])
def test_any_report_exported_and_opened_again_is_the_same_report(tmp_path, source, wanted):
    report = read_report(FIXTURES / source)
    target = tmp_path / f"exported.{FORMATS[wanted].extension}"

    write_report(report, target, FORMATS[wanted], WORDS)

    assert read_report(target) == report


@pytest.mark.parametrize("source", ["api_success.json", "web_success.json", "desktop_success.xml", "load_success.json"])
def test_any_report_exported_as_junit_is_read_as_junit_with_the_same_endings(tmp_path, source):
    report = read_report(FIXTURES / source)
    target = tmp_path / "exported.xml"

    write_report(report, target, FORMATS["junit"], WORDS)

    back = read_report(target)
    assert back.framework == "junit"
    assert [(result.name, result.status) for result in back.walk() if not result.children] == [
        (result.name, result.status) for result in report.walk() if not result.children]


def test_the_ways_a_report_is_written_are_json_junit_and_html():
    assert [(each.key, each.extension) for each in EXPORT_FORMATS] == [
        ("json", "json"), ("junit", "xml"), ("html", "html")]
    assert all(each.label_key in WORDS for each in EXPORT_FORMATS)


@pytest.mark.parametrize(("name", "content"), [
    ("empty.json", ""), ("words.txt", "just some words"), ("list.json", "[1, 2, 3]"),
    ("other.json", '{"name": "not a report"}'), ("other.xml", "<project><name>x</name></project>"),
    ("page.html", "<html><body>nothing here</body></html>"), ("broken.xml", "<testsuite"),
    ("both_empty_success.json", "{}"),
])
def test_a_file_that_is_no_report_is_refused(tmp_path, name, content):
    (tmp_path / name).write_text(content, encoding="utf-8")

    with pytest.raises(ExecutionReportException):
        read_report(tmp_path / name)


def test_a_file_larger_than_a_report_is_not_opened(tmp_path, monkeypatch):
    monkeypatch.setattr(report_files, "MAX_REPORT_BYTES", 10)
    (tmp_path / "big.json").write_text(json.dumps(ExecutionReport("mcp").to_dict()), encoding="utf-8")

    with pytest.raises(ExecutionReportException):
        read_report(tmp_path / "big.json")


def test_a_file_in_the_machines_own_encoding_is_read(tmp_path):
    text = (FIXTURES / "desktop_success.xml").read_text(encoding="utf-8").replace("set_mouse_position", "café")
    (tmp_path / "local_success.xml").write_bytes(text.encode("latin-1"))

    report = read_report(tmp_path / "local_success.xml")

    assert len(report.results) == 2


def test_a_file_with_a_byte_order_mark_is_read(tmp_path):
    (tmp_path / "bom_success.json").write_bytes(b"\xef\xbb\xbf" + (FIXTURES / "load_success.json").read_bytes())

    assert read_report(tmp_path / "bom_success.json").framework == LOAD_DENSITY


def test_a_missing_file_is_an_error_of_its_own(tmp_path):
    with pytest.raises(OSError):
        read_report(tmp_path / "gone.json")


_RESULTS = st.recursive(
    st.builds(
        lambda name, status, seconds: (name, status, seconds, ()),
        st.text(max_size=8), st.sampled_from(list(Status)), st.one_of(st.none(), st.floats(0, 100))),
    lambda inner: st.builds(lambda name, children: (name, None, None, tuple(children)), st.text(max_size=8),
                            st.lists(inner, min_size=1, max_size=3)),
    max_leaves=8)


def _built(spec, parent: str, seen: dict) -> ExecutionResult:
    name, status, seconds, children = spec
    occurrence = seen.setdefault((parent, name), 0)
    seen[parent, name] += 1
    own_id = stable_id(parent, name, occurrence)
    made = tuple(_built(child, own_id, seen) for child in children)
    return ExecutionResult(
        id=own_id, name=name, status=status or max((child.status for child in made), key=list(Status).index),
        kind=ResultKind.SUITE if made else ResultKind.TEST, duration=seconds, children=made)


@settings(max_examples=60)
@given(specs=st.lists(_RESULTS, max_size=4), name=st.text(max_size=10))
def test_whatever_the_report_json_and_html_give_it_back_and_junit_keeps_every_ending(specs, name):
    seen: dict = {}
    report = ExecutionReport("any", tuple(_built(spec, "any", seen) for spec in specs), name)

    assert ExecutionReport.from_dict(json.loads(FORMATS["json"].write(report, WORDS))) == report
    assert report_from_html(html_from_report(report, WORDS)) == report
    endings = sorted(result.status.value for result in report.walk() if not result.children)
    back = report_from_junit(junit_from_report(report))
    assert sorted(result.status.value for result in back.walk() if not result.children) == endings

"""The report adapters read what the installed packages' own report generators write.

The fixtures under ``fixtures/reports`` are in the packages' layouts but were
written by hand. Here each package's real generator is run, in a process of its
own (the IDE and its tests do not import ``je_auto_control``), on a few records
put into its record list the way a run puts them, and the files it writes are
read with the adapter. A package that is not installed, or cannot be imported
on this machine, is skipped.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from pybreeze.utils.execution_report.record_reports import API_TESTKA, AUTO_CONTROL, LOAD_DENSITY, WEB_RUNNER
from pybreeze.utils.execution_report.report_files import read_report
from pybreeze.utils.execution_report.report_schema import Status
from pybreeze.utils.subprocess_util import utf8_subprocess_env

_NOT_HERE = 42

_API = """
from je_api_testka.utils.test_record.test_record_class import test_record_instance
from je_api_testka.utils.generate_report.json_report import generate_json_report
from je_api_testka.utils.generate_report.xml_report import generate_xml_report
test_record_instance.test_record_list.append({
    "status_code": 200, "text": "ok", "content": b"ok", "headers": {"A": "b"}, "history": [], "encoding": "utf-8",
    "cookies": {}, "elapsed": "0:00:00.250000", "request_time_sec": 0.25, "request_method": "GET",
    "request_url": "https://example.com/users", "request_body": None,
    "start_time": "2026-10-08 09:00:00.000000", "end_time": "2026-10-08 09:00:00.250000"})
test_record_instance.error_record_list.append([
    {"http_method": "post", "test_url": "https://example.com/login", "soap": False, "record_request_info": True,
     "clean_record": False, "result_check_dict": {"status_code": 200}}, repr(AssertionError("status was 500"))])
"""

_ACTIONS = """
from {package}.utils.test_record.{module} import record_action_to_list, test_record_instance
from {package}.utils.generate_report.generate_json_report import generate_json_report
from {package}.utils.generate_report.generate_xml_report import generate_xml_report
test_record_instance.init_record = True
record_action_to_list({first!r}, {{"x": 1}}, None)
record_action_to_list({second!r}, {{"y": 2}}, RuntimeError("it broke <here>"))
"""

_LOAD = """
from je_load_density.utils.test_record.test_record_class import test_record_instance
from je_load_density.utils.generate_report.generate_json_report import generate_json_report
from je_load_density.utils.generate_report.generate_xml_report import generate_xml_report
test_record_instance.test_record_list.append({
    "Method": "GET", "test_url": "https://example.com/", "name": "/", "status_code": 200, "text": "ok",
    "content": b"ok", "headers": {"A": "b"}})
test_record_instance.error_record_list.append({
    "Method": "POST", "test_url": "https://example.com/login", "name": "/login", "status_code": 503,
    "error": "HTTPError('503 Server Error')"})
"""

_WRITE = """
generate_json_report("real")
generate_xml_report("real")
"""

# Each package: the records it is given, the names its two results get, and how the second ended
PACKAGES = {
    API_TESTKA: (_API, ["GET https://example.com/users", "post https://example.com/login"], Status.FAILED),
    AUTO_CONTROL: (_ACTIONS.format(package="je_auto_control", module="record_test_class", first="click_mouse",
                                   second="locate_image_center"),
                   ["click_mouse", "locate_image_center"], Status.ERROR),
    WEB_RUNNER: (_ACTIONS.format(package="je_web_runner", module="test_record_class",
                                 first="webdriver wrapper to_url", second="webdriver wrapper find_element"),
                 ["webdriver wrapper to_url", "webdriver wrapper find_element"], Status.ERROR),
    LOAD_DENSITY: (_LOAD, ["GET /", "POST /login"], Status.FAILED),
}


def _generated(tmp_path, framework: str) -> None:
    """Have *framework*'s own generators write ``real_*`` files into *tmp_path*; skip when it cannot be imported."""
    records, _names, _ending = PACKAGES[framework]
    script = f"import sys\ntry:\n    import {framework}\nexcept Exception:\n    sys.exit({_NOT_HERE})\n{records}{_WRITE}"
    done = subprocess.run(  # noqa: S603 — fixed argv: this interpreter and a script built from literals
        [sys.executable, "-c", script], cwd=tmp_path, capture_output=True, timeout=180, check=False, shell=False,
        env=utf8_subprocess_env())
    if done.returncode == _NOT_HERE:
        pytest.skip(f"{framework} is not installed here, or cannot be imported on this machine")
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")[-2000:]


@pytest.mark.parametrize("framework", list(PACKAGES))
@pytest.mark.parametrize("extension", ["json", "xml"])
def test_what_a_packages_own_generator_writes_is_read_as_its_run(tmp_path, framework, extension):
    _generated(tmp_path, framework)
    _records, names, ending = PACKAGES[framework]

    report = read_report(tmp_path / f"real_success.{extension}")

    assert (report.framework, report.name) == (framework, "real")
    assert [result.name for result in report.results] == names
    assert [result.status for result in report.results] == [Status.PASSED, ending]
    assert report.results[1].error is not None and report.results[1].error.message
    assert read_report(tmp_path / f"real_failure.{extension}") == report

"""A captured request, through every target and back: the script that is generated asks for that request.

Each fixture in ``fixtures/import`` is a request as it is captured (a cURL
command, a HAR export). For every target it is generated, and the output is
then *read back*: a Python script is run against stand-ins for the packages it
imports, which record the call it makes instead of making it, and a JSON action
list is parsed. What comes back is compared with the request the fixture holds.

Nothing here sends anything, which the last tests hold the importers to as
well: they import no package that could.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from urllib.parse import urlencode

import pytest

import pybreeze
from pybreeze.utils.curl_import.curl_parser import CurlRequest, parse_curl
from pybreeze.utils.har_import.har_parser import api_entries, parse_har
from pybreeze.utils.import_targets.builtin_targets import IMPORT_TARGETS
from pybreeze.utils.import_targets.normalized_request import NormalizedRequest, PayloadKind, normalize
from pybreeze.utils.import_targets.target_registry import RequestPart, parts_of

_FIXTURES = Path(__file__).parent / "fixtures" / "import"
_CURL_FIXTURES = sorted(path.name for path in _FIXTURES.glob("*.curl"))
_PYTHON_TARGETS = ("requests", "pytest", "apitestka_python", "loaddensity_python")
_UTILS = Path(pybreeze.__file__).parent / "utils"


def _curl(name: str) -> CurlRequest:
    return parse_curl((_FIXTURES / name).read_text(encoding="utf-8"))


def _session() -> list[CurlRequest]:
    """The API calls of the recorded session, in capture order (the image is left out)."""
    return [entry.request for entry in api_entries(parse_har((_FIXTURES / "session.har").read_text(encoding="utf-8")))]


class _Recorder:
    """Stand-ins for ``requests``, ``je_api_testka`` and ``je_load_density`` that record what they are asked."""

    def __init__(self, monkeypatch) -> None:
        self.calls: list[dict] = []
        response = SimpleNamespace(status_code=200, text="", json=dict)

        def request(method, url, **kwargs):
            self.calls.append({"method": method, "url": url, **kwargs})
            return response

        def test_api_method_requests(http_method, test_url, **kwargs):
            self.calls.append({"method": http_method, "url": test_url, **kwargs})
            return {"response_data": {}}

        def start_test(user_detail, **kwargs):
            self.calls.append({"user": user_detail, **kwargs})

        for name, attributes in (
                ("requests", {"request": request}),
                ("je_api_testka", {"test_api_method_requests": test_api_method_requests}),
                ("je_load_density", {"start_test": start_test})):
            module = ModuleType(name)
            vars(module).update(attributes)
            monkeypatch.setitem(sys.modules, name, module)

    def run(self, code: str) -> None:
        """Run a generated script; a pytest file's tests are then called, as pytest would."""
        scope: dict = {"__name__": "generated"}
        exec(compile(code, "<generated>", "exec"), scope)  # generated above from the tests' own fixtures
        for name, value in list(scope.items()):
            # Those the script defines: the APITestka import is named test_... too
            if name.startswith("test_") and getattr(value, "__globals__", None) is scope:
                value()


@pytest.fixture
def recorder(monkeypatch, capsys):
    return _Recorder(monkeypatch)


def _asked_url(call: dict) -> str:
    """The address a recorded call goes to: its URL with its ``params``, as the client would join them."""
    params = call.get("params")
    if not params:
        return call["url"]
    return f"{call['url']}{'&' if '?' in call['url'] else '?'}{urlencode(params, doseq=True)}"


def _as_form(files: object) -> list[tuple[str, bool, str]]:
    """A ``files=`` value as ``(name, is a file, value)``: a dict, or pairs when a field repeats."""
    pairs = files.items() if isinstance(files, dict) else files
    return [(name, value[0] is not None, value[1]) for name, value in pairs]


def _assert_same_payload(call: dict, sent: NormalizedRequest) -> None:
    kind = sent.payload.kind
    assert call.get("json") == (sent.payload.value if kind is PayloadKind.JSON else None)
    assert call.get("data") == (sent.payload.text if kind is PayloadKind.RAW else None)
    form = _as_form(call["files"]) if "files" in call else []
    assert form == (list(sent.payload.fields) if kind is PayloadKind.FORM else [])


def _assert_asks_for(call: dict, sent: NormalizedRequest, *, with_timeout: bool) -> None:
    """*call* is the request *sent*: what a script written for ``requests`` or APITestka must ask for."""
    assert call["method"] == sent.method
    assert _asked_url(call) == sent.url
    assert call.get("headers", {}) == dict(sent.headers)
    assert call.get("cookies", {}) == dict(sent.cookies)
    _assert_same_payload(call, sent)
    assert call.get("auth") == (None if sent.username is None else (sent.username, sent.password))
    assert call.get("timeout") == (sent.timeout if with_timeout else None)


class TestOneRequest:
    @pytest.mark.parametrize("fixture", _CURL_FIXTURES)
    @pytest.mark.parametrize("target", ["requests", "pytest"])
    def test_a_requests_script_asks_for_the_request(self, recorder, fixture, target):
        request = _curl(fixture)

        recorder.run(IMPORT_TARGETS.generate(target, [request]))

        assert len(recorder.calls) == 1
        _assert_asks_for(recorder.calls[0], normalize(request), with_timeout=True)

    @pytest.mark.parametrize("fixture", _CURL_FIXTURES)
    def test_an_apitestka_script_asks_for_the_request_without_its_time_limit(self, recorder, fixture):
        request = _curl(fixture)

        recorder.run(IMPORT_TARGETS.generate("apitestka_python", [request]))

        assert len(recorder.calls) == 1
        _assert_asks_for(recorder.calls[0], normalize(request), with_timeout=False)

    @pytest.mark.parametrize("fixture", _CURL_FIXTURES)
    def test_an_apitestka_action_holds_the_request(self, fixture):
        request = _curl(fixture)
        sent = normalize(request)

        [[command, parameters]] = json.loads(IMPORT_TARGETS.generate("apitestka_action", [request]))

        assert command == "AT_test_api_method"
        call = {"method": parameters.pop("http_method"), "url": parameters.pop("test_url"), **parameters}
        # JSON has lists where Python has tuples
        if "auth" in call:
            call["auth"] = tuple(call["auth"])
        if "files" in call:
            files = call["files"]
            call["files"] = ({name: tuple(value) for name, value in files.items()} if isinstance(files, dict)
                             else [(name, tuple(value)) for name, value in files])
        _assert_asks_for(call, sent, with_timeout=False)

    @pytest.mark.parametrize("fixture", _CURL_FIXTURES)
    def test_a_loaddensity_script_drives_the_requests_method_and_address(self, recorder, fixture):
        request = _curl(fixture)
        sent = normalize(request)

        recorder.run(IMPORT_TARGETS.generate("loaddensity_python", [request]))

        [call] = recorder.calls
        assert call["tasks"] == {sent.method.lower(): {"request_url": sent.url}}

    @pytest.mark.parametrize("fixture", _CURL_FIXTURES)
    def test_a_webrunner_action_list_visits_the_requests_address(self, fixture):
        request = _curl(fixture)
        sent = normalize(request)

        actions = json.loads(IMPORT_TARGETS.generate("webrunner_action", [request]))

        visited = [action[1]["url"] for action in actions if action[0] == "WR_to_url"]
        cookies = [(action[1]["cookie_dict"]["name"], action[1]["cookie_dict"]["value"])
                   for action in actions if action[0] == "WR_add_cookie"]
        assert set(visited) == {sent.url}
        assert tuple(cookies) == sent.cookies
        assert actions[0][0] == "WR_get_webdriver_manager"
        assert actions[-1] == ["WR_quit"]


class TestASession:
    def test_the_fixture_holds_three_api_calls(self):
        assert [(request.method, request.url) for request in _session()] == [
            ("GET", "https://api.example.test/v1/items"),
            ("POST", "https://api.example.test/v1/items"),
            ("DELETE", "https://api.example.test/v1/items/7")]

    @pytest.mark.parametrize("target", ["requests", "pytest"])
    def test_a_requests_script_asks_for_each_request_in_order(self, recorder, target):
        session = _session()

        recorder.run(IMPORT_TARGETS.generate(target, session))

        assert len(recorder.calls) == len(session)
        for call, request in zip(recorder.calls, session, strict=True):
            _assert_asks_for(call, normalize(request), with_timeout=True)

    def test_an_apitestka_script_asks_for_each_request_in_order(self, recorder):
        session = _session()

        recorder.run(IMPORT_TARGETS.generate("apitestka_python", session))

        for call, request in zip(recorder.calls, session, strict=True):
            _assert_asks_for(call, normalize(request), with_timeout=False)

    def test_an_apitestka_action_list_holds_each_request_in_order(self):
        session = _session()

        actions = json.loads(IMPORT_TARGETS.generate("apitestka_action", session))

        assert [(action[1]["http_method"], action[1]["test_url"]) for action in actions] == [
            (request.method, request.url) for request in session]

    def test_a_loaddensity_script_has_a_run_for_each_request(self, recorder):
        session = _session()

        recorder.run(IMPORT_TARGETS.generate("loaddensity_python", session))

        assert [call["tasks"] for call in recorder.calls] == [
            {request.method.lower(): {"request_url": request.full_url}} for request in session]

    def test_a_webrunner_action_list_visits_each_address_in_one_browser(self):
        session = _session()

        actions = json.loads(IMPORT_TARGETS.generate("webrunner_action", session))

        assert [action[0] for action in actions].count("WR_get_webdriver_manager") == 1
        visited = [action[1]["url"] for action in actions if action[0] == "WR_to_url"]
        # An address with cookies is visited, given them, and visited again
        expected = [url for request in session for url in [request.full_url] * (2 if request.cookies else 1)]
        assert visited == expected


class TestEveryTargetOnEveryFixture:
    @pytest.mark.parametrize("fixture", _CURL_FIXTURES)
    @pytest.mark.parametrize("target", IMPORT_TARGETS.targets(), ids=lambda target: target.key)
    def test_the_output_is_what_its_extension_says(self, target, fixture):
        output = target.generate_one(_curl(fixture))

        if target.extension == "json":
            json.loads(output)
        else:
            ast.parse(output)

    @pytest.mark.parametrize("target", IMPORT_TARGETS.targets(), ids=lambda target: target.key)
    def test_the_session_is_written_whole_in_that_form_too(self, target):
        output = target.generate_many(_session())

        if target.extension == "json":
            assert isinstance(json.loads(output), list)
        else:
            ast.parse(output)

    def test_every_python_target_is_run_above(self):
        python = {target.key for target in IMPORT_TARGETS.targets() if target.extension == "py"}

        assert python == set(_PYTHON_TARGETS)

    def test_the_fixtures_between_them_have_every_part_a_command_can_inline(self):
        # Files (an upload, a body or cookies read from one) need a file beside the script
        seen = {part for name in _CURL_FIXTURES for part in parts_of(_curl(name))}

        assert seen == set(RequestPart) - {RequestPart.FILE_UPLOAD, RequestPart.BODY_FILE, RequestPart.COOKIE_FILE}


# Packages a module of the import pipeline must not import: with none of them
# in reach, parsing and generating cannot send the request they describe
_COULD_SEND = frozenset({
    "requests", "urllib3", "httpx", "aiohttp", "http", "socket", "ssl", "subprocess", "webbrowser",
    "selenium", "je_web_runner", "je_api_testka", "je_load_density", "je_auto_control",
})
_PIPELINE = ("curl_import", "har_import", "import_targets")


def _imported(source: Path) -> set[str]:
    """The top-level packages *source* imports, and ``urllib.request`` when it is the one imported."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                 else [node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else [])
        for name in names:
            found.add("urllib.request" if name.startswith("urllib.request") else name.split(".")[0])
    return found


def test_importing_never_replays_a_captured_request():
    offenders = [
        f"{source.relative_to(_UTILS)}: {sorted(reach)}"
        for package in _PIPELINE for source in sorted((_UTILS / package).rglob("*.py"))
        if (reach := _imported(source) & (_COULD_SEND | {"urllib.request"}))
    ]

    assert offenders == []


def test_the_pipeline_has_modules_to_check():
    assert all(any((_UTILS / package).glob("*.py")) for package in _PIPELINE)

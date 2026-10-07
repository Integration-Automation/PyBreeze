"""The tutorials' examples do what the tutorials say they do.

A tutorial is only as good as its example. Each example is a file under
``docs/source/examples`` that the page includes (not a copy pasted into the
page), and this checks them: the action scripts against the keywords of the
installed frameworks, the generated code and the findings against the code that
produces them, the MCP server by talking to it, the JSON editing steps by doing
them. The two languages are held to the same pages and the same examples.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict as WORDS
from pybreeze.utils.curl_import.curl_parser import parse_curl
from pybreeze.utils.exception.exceptions import LanguageServiceException
from pybreeze.utils.har_import.har_parser import parse_har
from pybreeze.utils.header_tools.header_analyzer import analyze_headers
from pybreeze.utils.header_tools.header_sarif import to_sarif
from pybreeze.utils.import_targets.builtin_targets import IMPORT_TARGETS
from pybreeze.utils.language_service.action_adapter import ActionLanguageAdapter, framework_of
from pybreeze.utils.language_service.framework_profiles import FrameworkProfile
from pybreeze.utils.language_service.metadata_probe import read_metadata
from pybreeze.utils.language_service.service_adapter import TextDocument
from pybreeze.utils.mcp.mcp_client import McpClient
from pybreeze.utils.mcp.mcp_profile import McpServerProfile

SOURCE = Path(__file__).resolve().parents[2] / "docs" / "source"
EXAMPLES = SOURCE / "examples"
ENGLISH, CHINESE = SOURCE / "Eng" / "tutorials", SOURCE / "Zh" / "tutorials"
PAGES = sorted(page.name for page in ENGLISH.glob("t*.rst"))
_INCLUDED = re.compile(r"^\.\. literalinclude:: (\S+)", re.MULTILINE)
# APITestka has no language service of its own; it is asked the way the others are
API_TESTKA = FrameworkProfile(
    framework="je_api_testka", label="APITestka", document_key="api_testka",
    executor_module="je_api_testka.utils.executor.action_executor", distribution="je_api_testka",
    keyword_prefix="AT_")


def _text(name: str) -> str:
    return (EXAMPLES / name).read_text(encoding="utf-8")


def _page(name: str, folder: Path = ENGLISH) -> str:
    return (folder / name).read_text(encoding="utf-8")


def _block_after(page: str, marker: str) -> str:
    """The first indented block of *page* after *marker*, without its indent."""
    lines = page[page.index(marker):].splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(".. code-block::"))
    body = []
    for line in lines[start + 2:]:
        if line.strip() and not line.startswith("   "):
            break
        body.append(line[3:] if line.startswith("   ") else "")
    return "\n".join(body).strip("\n")


# ----------------------------------------------------------------------
# The pages
# ----------------------------------------------------------------------

def test_there_are_thirteen_tutorials_in_both_languages():
    assert len(PAGES) == 13
    assert sorted(page.name for page in CHINESE.glob("t*.rst")) == PAGES
    for folder in (ENGLISH, CHINESE):
        index = _page("index.rst", folder)
        assert all(page.removesuffix(".rst") in index for page in PAGES)


@pytest.mark.parametrize("page", PAGES)
def test_both_languages_of_a_tutorial_include_the_same_examples_and_each_exists(page):
    english = _INCLUDED.findall(_page(page))
    assert english == _INCLUDED.findall(_page(page, CHINESE))
    for included in english:
        assert (ENGLISH / included).resolve().is_file(), included


@pytest.mark.parametrize("page", PAGES)
def test_each_tutorial_says_what_to_expect(page):
    assert "Expected result" in _page(page)
    assert "預期結果" in _page(page, CHINESE)


def test_every_example_is_used_by_a_tutorial():
    used = {(ENGLISH / included).resolve() for page in PAGES for included in _INCLUDED.findall(_page(page))}
    named = "\n".join(_page(page) for page in PAGES)
    unused = [path.name for path in EXAMPLES.rglob("*")
              if path.is_file() and path.resolve() not in used and path.name not in named]
    assert unused == []


# ----------------------------------------------------------------------
# The action scripts
# ----------------------------------------------------------------------

def _diagnostics(name: str, profile: FrameworkProfile | None = None) -> list[tuple[int, str, str]]:
    """What the installed framework finds wrong with the example *name*: (line, code, message)."""
    text = _text(name)
    profile = profile or framework_of(text, {})
    try:
        metadata = read_metadata(profile)
    except LanguageServiceException as error:
        if "is not installed" in str(error):
            pytest.skip(f"{profile.framework} is not installed here")
        raise
    found = ActionLanguageAdapter(profile, metadata, WORDS).diagnose(TextDocument(f"file:///{name}", text))
    return [(each.range.start.line + 1, each.code, each.message) for each in found]


@pytest.mark.parametrize("name", [
    "first_browser_test.json", "first_desktop_automation.json", "first_load_scenario.json"])
def test_an_example_script_uses_only_keywords_and_parameters_the_installed_framework_has(name):
    assert _diagnostics(name) == []


def test_the_api_example_uses_only_keywords_and_parameters_apitestka_has():
    assert _diagnostics("first_api_test.json", API_TESTKA) == []


def test_the_broken_example_is_broken_the_way_its_tutorial_says():
    found = _diagnostics("broken_actions.json")

    assert [(line, code) for line, code, _message in found] == [
        (3, "unknown-keyword"), (4, "unknown-parameter"), (4, "missing-parameter")]
    quoted = _block_after(_page("t09_keywords_language_service.rst"), "Step 1 marks")
    for (line, _code, message), told in zip(found, quoted.splitlines()):
        version = re.search(r"WebRunner (\S+)\.", message)
        expected = message.replace(version.group(1), "0.0.66") if version else message
        assert told.strip() == f"line {line}  {expected}"


# ----------------------------------------------------------------------
# Generated code and findings
# ----------------------------------------------------------------------

def test_the_curl_example_generates_the_test_its_tutorial_shows():
    generated = IMPORT_TARGETS.generate("pytest", [parse_curl(_text("request.curl"))])

    assert generated.strip() == _block_after(_page("t06_curl_har_to_tests.rst"), "the generated code is")


def test_the_curl_example_generates_the_apitestka_script_its_tutorial_shows():
    generated = IMPORT_TARGETS.generate("apitestka_action", [parse_curl(_text("request.curl"))])

    shown = _block_after(_page("t06_curl_har_to_tests.rst"), "For **APITestka (JSON action)**")
    assert json.loads(generated) == json.loads(shown)


def test_the_har_example_generates_the_two_tests_its_tutorial_names():
    entries = parse_har(_text("session.har"))
    generated = IMPORT_TARGETS.generate("pytest", [entry.request for entry in entries])

    assert len(entries) == 2
    assert [node.name for node in ast.parse(generated).body if isinstance(node, ast.FunctionDef)] == [
        "test_get_users_json", "test_get_127_0_0_1"]


def test_the_header_example_has_the_findings_its_tutorial_lists():
    sarif = to_sarif(analyze_headers(_text("response_headers.txt")), "response_headers.txt")
    results = sarif["runs"][0]["results"]

    listed = _block_after(_page("t07_header_sarif_ci.rst"), "Two are warnings").splitlines()
    assert sarif["version"] == "2.1.0"
    assert [(result["level"], result["ruleId"]) for result in results] == [
        tuple(line.split()[:2]) for line in listed]
    for result, line in zip(results, listed):
        assert line.endswith(result["message"]["text"])
        started = result["locations"][0]["physicalLocation"]["region"]["startLine"]
        assert f"line {started} " in line


# ----------------------------------------------------------------------
# The MCP server, the tab and the plugin
# ----------------------------------------------------------------------

def test_the_mcp_example_is_a_server_the_client_can_use():
    client = McpClient(McpServerProfile("time", (sys.executable, str(EXAMPLES / "mcp_time_server.py")),
                                        timeout_seconds=30.0))
    try:
        server = client.connect()
        tools = client.list_tools()

        assert (server.name, server.version, sorted(server.capabilities)) == ("tutorial-time-server", "1.0.0", ["tools"])
        assert [(tool.name, tool.read_only) for tool in tools] == [("now", True), ("add", True)]
        assert client.call_tool("add", {"a": 2, "b": 3}).text == "5"
        assert client.call_tool("now", {}).text.endswith("UTC")
        assert client.call_tool("no_such_tool", {}).is_error
    finally:
        client.close()


def test_the_tab_example_registers_its_tab_before_the_editor_starts():
    tree = ast.parse(_text("hello_tab.py"))
    main = next(node for node in tree.body if isinstance(node, ast.If))
    done = [ast.unparse(statement) for statement in main.body]

    assert done == ["EDITOR_EXTEND_TAB['Hello'] = HelloTab", "start_editor()"]
    assert any(isinstance(node, ast.ClassDef) and node.name == "HelloTab" for node in tree.body)


def test_the_plugin_example_is_a_plugin():
    tree = ast.parse((EXAMPLES / "jeditor_plugins" / "todo_notes.py").read_text(encoding="utf-8"))
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assigned = {target.id for node in tree.body if isinstance(node, ast.Assign) for target in node.targets}

    assert "register" in names
    assert {"PLUGIN_NAME", "PLUGIN_VERSION"} <= assigned


# ----------------------------------------------------------------------
# The JSON editing steps
# ----------------------------------------------------------------------

def test_the_json_editing_steps_give_the_text_the_tutorial_shows():
    from PySide6.QtWidgets import QApplication

    from pybreeze.extend_multi_language.update_language_dict import update_language_dict
    from pybreeze.pybreeze_ui.tools_gui.json_editor_gui import JsonEditorGUI
    from pybreeze.utils.json_format.json_tree_edit import JsonKind

    _app = QApplication.instance() or QApplication([])
    update_language_dict()
    editor = JsonEditorGUI()
    try:
        editor.load_text(_text("settings.json"))
        panel = editor.tree_panel

        def give_type(kind: JsonKind) -> None:
            panel.type_select.activated.emit(panel.type_select.findData(kind))

        # Steps 2 to 5 of the tutorial
        panel.select_path(("servers",))
        panel.add_value()
        give_type(JsonKind.OBJECT)
        panel.add_value()
        panel.tree.currentItem().setText(0, "host")
        give_type(JsonKind.STRING)
        panel.select_path(("servers", 1, "host"))
        panel.tree.currentItem().setText(1, "127.0.0.1")
        panel.select_path(("retries",))
        panel.tree.currentItem().setText(1, "three")
        refused = editor.status.text()
        panel.select_path(("retries",))
        panel.tree.currentItem().setText(1, "5")
        panel.select_path(("name",))
        panel.move_down()
        panel.move_down()

        assert "not a JSON number" in refused
        shown = _block_after(_page("t08_visual_json_editing.rst"), "After step 5")
        assert editor.document.text.strip() == shown
        assert editor.is_modified()
    finally:
        editor.deleteLater()

"""MCP server profiles, where they are kept, what is taken out of logs, and the session as a report."""
from __future__ import annotations

import json
import stat
import sys

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pybreeze.utils.exception.exceptions import McpException
from pybreeze.utils.execution_report.report_schema import ExecutionReport, ResultKind, Status, stable_id
from pybreeze.utils.mcp import mcp_profile
from pybreeze.utils.mcp.mcp_call_log import CANCELLED, DECLINED, FRAMEWORK, TOOL_FAILED, McpCallLog
from pybreeze.utils.mcp.mcp_client import McpCancelled, McpServerInfo, McpTimeout, McpToolResult
from pybreeze.utils.mcp.mcp_profile import (
    DEFAULT_TIMEOUT_SECONDS,
    McpServerProfile,
    discovered_profiles,
    load_profiles,
    profile_from_entry,
    profiles_from_text,
    profiles_to_text,
    save_profiles,
)
from pybreeze.utils.mcp.mcp_redaction import REDACTED, is_secret_name, redact, redact_text

SECRET = "sk-live-8842aa19"
FILES = McpServerProfile(
    name="files", command=("npx", "-y", "@example/server-files", "C:/work"),
    environment={"API_TOKEN": SECRET, "REGION": "eu"}, working_directory="C:/work",
    timeout_seconds=45.0, trusted_tools=frozenset({"read_file", "list"}))


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A home folder of the test's own: ``~/.pybreeze`` is under it."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# ----------------------------------------------------------------------
# Profiles
# ----------------------------------------------------------------------

@pytest.mark.parametrize("command", [(), ("",), ("  ",), ("python", 5)])
def test_a_profile_needs_a_command_to_start_its_server_with(command):
    with pytest.raises(McpException, match="'broken' has no command"):
        McpServerProfile("broken", command)


def test_a_profiles_secrets_are_the_values_it_gives_the_server():
    assert sorted(FILES.secrets()) == ["eu", SECRET]
    assert McpServerProfile("plain", ("server",)).secrets() == []


def test_trusting_a_tool_gives_a_new_profile_and_leaves_the_old_one():
    trusting = FILES.trusting("write_file")

    assert trusting.trusted_tools == {"read_file", "list", "write_file"}
    assert FILES.trusted_tools == {"read_file", "list"}
    assert trusting.command == FILES.command


def test_a_profile_is_written_in_the_layout_mcp_clients_share():
    assert FILES.to_entry() == {
        "command": "npx", "args": ["-y", "@example/server-files", "C:/work"],
        "env": {"API_TOKEN": SECRET, "REGION": "eu"}, "cwd": "C:/work", "timeout": 45.0,
        "trustedTools": ["list", "read_file"]}
    assert McpServerProfile("plain", ("server",)).to_entry() == {"command": "server", "args": []}


def test_profiles_written_and_read_back_are_the_same():
    profiles = [FILES, McpServerProfile("plain", ("server", "--flag"))]

    assert profiles_from_text(profiles_to_text(profiles)) == profiles


def test_a_list_made_by_another_client_is_read():
    text = json.dumps({"mcpServers": {
        "git": {"command": "uvx", "args": ["mcp-server-git"], "env": {"GIT_TOKEN": "abc"}},
        "time": {"command": "python", "args": ["-m", "time_server"], "someOtherClientsField": True}}})

    profiles = profiles_from_text(text)

    assert [(profile.name, profile.command) for profile in profiles] == [
        ("git", ("uvx", "mcp-server-git")), ("time", ("python", "-m", "time_server"))]
    assert profiles[0].environment == {"GIT_TOKEN": "abc"}
    assert profiles[1].timeout_seconds == DEFAULT_TIMEOUT_SECONDS


@pytest.mark.parametrize("entry", [
    None, [], "python server.py", {}, {"command": ""}, {"command": 5}, {"command": "  "}, {"args": ["x"]},
])
def test_an_entry_without_a_usable_command_describes_no_server(entry):
    assert profile_from_entry("x", entry) is None


@pytest.mark.parametrize(("entry", "expected"), [
    ({"command": "s", "args": "not a list"}, ("s",)),
    ({"command": "s", "args": ["a", 5]}, ("s",)),
    ({"command": "s", "args": ["a", "b"]}, ("s", "a", "b")),
])
def test_arguments_that_are_not_a_list_of_texts_are_left_out(entry, expected):
    assert profile_from_entry("x", entry).command == expected


@pytest.mark.parametrize(("timeout", "expected"), [
    (45, 45.0), (0, 1.0), (-5, 1.0), (10 ** 9, 3600.0), ("30", DEFAULT_TIMEOUT_SECONDS), (True, DEFAULT_TIMEOUT_SECONDS),
    (float("nan"), DEFAULT_TIMEOUT_SECONDS), (float("inf"), DEFAULT_TIMEOUT_SECONDS), (None, DEFAULT_TIMEOUT_SECONDS),
])
def test_a_time_limit_is_kept_within_reason_whatever_the_file_says(timeout, expected):
    assert profile_from_entry("x", {"command": "s", "timeout": timeout}).timeout_seconds == expected


def test_fields_of_the_wrong_type_take_their_defaults():
    profile = profile_from_entry("x", {
        "command": "s", "env": ["A=1"], "cwd": 5, "trustedTools": "all of them"})

    assert (profile.environment, profile.working_directory, profile.trusted_tools) == ({}, "", frozenset())
    assert profile_from_entry("x", {"command": "s", "env": {"A": "1", "B": 2, 3: "c"}}).environment == {"A": "1"}


@pytest.mark.parametrize("text", ["", "not json", "[]", "{}", '{"mcpServers": []}', '{"servers": {}}', "[" * 100000],
                         ids=["empty", "a word", "a list", "no servers", "servers not an object", "another key", "nested too deep"])
def test_text_that_is_not_a_list_of_servers_is_refused(text):
    with pytest.raises(McpException, match="not a list of MCP servers"):
        profiles_from_text(text)


def test_entries_that_describe_no_server_are_passed_over_and_the_rest_are_read():
    text = json.dumps({"mcpServers": {"good": {"command": "s"}, "bad": {"args": []}, "": {"command": "s"}}})

    assert [profile.name for profile in profiles_from_text(text)] == ["good"]


# ----------------------------------------------------------------------
# Where they are kept
# ----------------------------------------------------------------------

def test_with_nothing_saved_there_are_no_profiles_and_no_folder_is_made(home):
    assert load_profiles() == []
    assert not (home / ".pybreeze").exists()


def test_saved_profiles_come_back(home):
    save_profiles([FILES])

    assert load_profiles() == [FILES]
    assert (home / ".pybreeze" / mcp_profile.PROFILES_FILE).is_file()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows keeps the profile's own access rules")
def test_the_file_is_the_owners_alone(home):
    save_profiles([FILES])

    mode = stat.S_IMODE((home / ".pybreeze" / mcp_profile.PROFILES_FILE).stat().st_mode)
    assert mode == 0o600


def test_a_saved_file_that_is_not_a_list_of_servers_is_said(home):
    save_profiles([FILES])
    (home / ".pybreeze" / mcp_profile.PROFILES_FILE).write_text("{broken", encoding="utf-8")

    with pytest.raises(McpException):
        load_profiles()


def test_saving_replaces_the_list(home):
    save_profiles([FILES])
    save_profiles([])

    assert load_profiles() == []


# ----------------------------------------------------------------------
# What a project brings
# ----------------------------------------------------------------------

def test_a_projects_servers_are_found_and_none_of_their_tools_is_trusted(tmp_path):
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {
        "project": {"command": "node", "args": ["server.js"], "trustedTools": ["delete_everything"]}}}),
        encoding="utf-8")

    (found,) = discovered_profiles(tmp_path)

    assert (found.name, found.command) == ("project", ("node", "server.js"))
    assert found.trusted_tools == frozenset()


@pytest.mark.parametrize("content", [None, "not json", "[]", '{"mcpServers": 5}'])
def test_a_folder_without_a_usable_file_brings_none(tmp_path, content):
    if content is not None:
        (tmp_path / ".mcp.json").write_text(content, encoding="utf-8")

    assert discovered_profiles(tmp_path) == []


def test_finding_a_projects_servers_starts_nothing(tmp_path):
    marker = tmp_path / "started"
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"trap": {
        "command": sys.executable, "args": ["-c", f"open({str(marker)!r}, 'w').close()"]}}}), encoding="utf-8")

    assert len(discovered_profiles(tmp_path)) == 1
    assert not marker.exists()


# ----------------------------------------------------------------------
# What is taken out
# ----------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "token", "access_token", "API_TOKEN", "password", "passwd", "DB_PASSWORD", "passphrase", "secret",
    "client-secret", "apiKey", "api_key", "X-Api-Key", "Authorization", "authorisation", "credentials",
    "cookie", "Set-Cookie", "private_key", "session_id",
])
def test_a_name_that_reads_like_a_secrets_is_one(name):
    assert is_secret_name(name)


@pytest.mark.parametrize("name", ["path", "text", "user", "url", "key", "keyword", "monkey", "", 5, None])
def test_an_ordinary_name_is_not(name):
    assert not is_secret_name(name)


def test_the_value_of_a_secret_name_is_taken_out_whatever_it_is():
    cleaned = redact({"path": "a.txt", "token": "abc", "nested": {"Password": ["x", "y"], "depth": 2}})

    assert cleaned == {"path": "a.txt", "token": REDACTED, "nested": {"Password": REDACTED, "depth": 2}}


def test_a_known_secret_is_taken_out_wherever_it_turns_up():
    value = {"note": f"used {SECRET} to log in", "items": [SECRET, {"deep": f"x{SECRET}y"}], f"key-{SECRET}": 1}

    assert redact(value, [SECRET]) == {
        "note": "used *** to log in", "items": [REDACTED, {"deep": "x***y"}], "key-***": 1}


def test_what_is_redacted_is_a_copy():
    value = {"token": "abc", "list": [SECRET]}

    redact(value, [SECRET])

    assert value == {"token": "abc", "list": [SECRET]}


@pytest.mark.parametrize("short", ["", "1", "true", "eu", "12345"])
def test_a_value_too_short_to_be_a_secret_is_not_searched_for(short):
    assert redact_text(f"region {short} is true 12345", [short]) == f"region {short} is true 12345"


def test_a_secret_that_holds_another_goes_whole():
    assert redact_text("abcdef-123456 and abcdef", ["abcdef", "abcdef-123456"]) == "*** and ***"


def test_what_is_not_text_or_a_container_is_left_as_it_is():
    assert redact([1, 2.5, True, None], [SECRET]) == [1, 2.5, True, None]
    assert redact(("a", SECRET), [SECRET]) == ["a", REDACTED]


def test_nesting_deeper_than_is_walked_is_replaced_whole():
    deep: object = SECRET
    for _level in range(200):
        deep = [deep]

    assert SECRET not in json.dumps(redact(deep, []))


@given(text=st.text(max_size=40), secret=st.text(min_size=6, max_size=12))
def test_no_known_secret_is_left_in_any_text(text, secret):
    assert secret not in redact_text(text + secret + text, [secret]) or secret in REDACTED * 5


# ----------------------------------------------------------------------
# The session as a report
# ----------------------------------------------------------------------

def _result(text: str, is_error: bool = False) -> McpToolResult:
    return McpToolResult(text, is_error, {"content": [{"type": "text", "text": text}], "isError": is_error})


def test_a_call_that_was_answered_is_a_step_that_passed():
    log = McpCallLog(FILES)

    kept = log.record("read_file", {"path": "a.txt"}, 1000.0, 0.25, _result("hello"))

    assert (kept.name, kept.status, kept.kind) == ("read_file", Status.PASSED, ResultKind.STEP)
    assert (kept.started, kept.duration, kept.stdout, kept.error) == (1000.0, 0.25, "hello", None)
    assert kept.raw == {"tool": "read_file", "arguments": {"path": "a.txt"},
                        "result": {"content": [{"type": "text", "text": "hello"}], "isError": False}}
    assert kept.id == stable_id(FRAMEWORK, "files/read_file", 0)


def test_a_tool_that_says_it_failed_is_a_failure_named_by_its_first_line():
    kept = McpCallLog(FILES).record("write_file", {}, 1000.0, 0.1, _result("the disk is full\nno space left", True))

    assert kept.status is Status.FAILED
    assert (kept.error.message, kept.error.kind) == ("the disk is full", TOOL_FAILED)
    assert kept.stdout == "the disk is full\nno space left"


def test_a_call_that_did_not_go_through_is_an_error_named_by_what_went_wrong():
    kept = McpCallLog(FILES).record_failure(
        "slow", {"seconds": 99}, 1000.0, 30.0, McpTimeout("the MCP server did not answer tools/call within 30 seconds"))

    assert kept.status is Status.ERROR
    assert (kept.error.kind, kept.duration) == ("McpTimeout", 30.0)
    assert "within 30 seconds" in kept.error.message
    assert "result" not in kept.raw


def test_a_cancelled_call_and_a_declined_one_are_skipped():
    log = McpCallLog(FILES)

    cancelled = log.record_failure("slow", {}, 1000.0, 0.5, McpCancelled("tools/call was cancelled"))
    declined = log.record_declined("write_file", {"path": "a.txt"}, 1001.0)

    assert (cancelled.status, cancelled.error.kind) == (Status.SKIPPED, CANCELLED)
    assert (declined.status, declined.error.kind, declined.duration) == (Status.SKIPPED, DECLINED, 0.0)
    assert declined.raw == {"tool": "write_file", "arguments": {"path": "a.txt"}}


def test_nothing_secret_is_kept_of_a_call():
    log = McpCallLog(FILES)

    answered = log.record("login", {"user": "me", "password": "hunter2", "note": f"with {SECRET}"}, 1.0, 0.1,
                          McpToolResult(f"token is {SECRET}", False, {"structuredContent": {"token": SECRET}}))
    refused = log.record_failure("login", {"api_key": SECRET}, 2.0, 0.1, McpTimeout(f"no answer for {SECRET}"))

    kept = json.dumps([answered.to_dict(), refused.to_dict(), log.report().to_dict()])
    assert SECRET not in kept and "hunter2" not in kept
    assert answered.raw["arguments"] == {"user": "me", "password": REDACTED, "note": "with ***"}
    assert answered.stdout == "token is ***"


def test_calls_of_the_same_tool_have_ids_of_their_own_that_are_the_same_in_every_session():
    def session() -> list[str]:
        log = McpCallLog(FILES)
        for _call in range(3):
            log.record("read_file", {}, 1.0, 0.1, _result("x"))
        log.record("list", {}, 1.0, 0.1, _result("x"))
        return [result.id for result in log.results()]

    first_session = session()
    second_session = session()
    assert len(set(first_session)) == 4
    assert first_session == second_session


def test_the_session_is_an_execution_report_that_can_be_written_and_read_back():
    log = McpCallLog(FILES)
    log.connected(McpServerInfo("files-server", "2.0", "2025-06-18", frozenset({"tools", "resources"})))
    log.record("read_file", {"path": "a.txt"}, 1000.0, 0.5, _result("hello"))
    log.record("write_file", {}, 1002.0, 1.5, _result("the disk is full", True))
    log.record_declined("delete", {}, 1004.0)

    report = log.report()

    assert (report.framework, report.name) == ("mcp", "files")
    assert (report.started, report.duration) == (1000.0, 4.0)
    assert report.status is Status.FAILED
    assert report.counts()[Status.PASSED] == 1 and report.counts()[Status.SKIPPED] == 1
    assert report.raw == {
        "command": ["npx", "-y", "@example/server-files", "C:/work"],
        "server": {"name": "files-server", "version": "2.0", "protocolVersion": "2025-06-18",
                   "capabilities": ["resources", "tools"]}}
    assert ExecutionReport.from_dict(json.loads(json.dumps(report.to_dict()))) == report


def test_a_session_with_no_call_is_an_empty_report_and_a_secret_in_the_command_is_taken_out():
    profile = McpServerProfile("s", ("server", f"--key={SECRET}"), environment={"KEY": SECRET})

    report = McpCallLog(profile).report()

    assert (report.results, report.started, report.duration) == ((), None, None)
    assert report.raw == {"command": ["server", "--key=***"], "server": None}

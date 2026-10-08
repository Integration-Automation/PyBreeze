"""The MCP client against a real server process: the handshake, what a server offers, calls, and what goes wrong.

The server is ``fixtures/mcp/fake_server.py``, started the way any MCP server
is: as a process spoken to on its standard input and output. Nothing here is Qt.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from pybreeze.utils.exception.exceptions import McpException
from pybreeze.utils.mcp.mcp_client import (
    PROTOCOL_VERSIONS,
    McpCancelled,
    McpClient,
    McpRemoteError,
    McpTimeout,
    block_text,
)
from pybreeze.utils.mcp.mcp_profile import McpServerProfile
from pybreeze.utils.mcp.mcp_transport import McpClosed, StdioTransport

FAKE_SERVER = Path(__file__).parent / "fixtures" / "mcp" / "fake_server.py"
TOKEN = "tok-3f9a1c77e2"


def _profile(*options: str, timeout_seconds: float = 20.0) -> McpServerProfile:
    return McpServerProfile(
        name="fake", command=(sys.executable, str(FAKE_SERVER), *options),
        environment={"FAKE_TOKEN": TOKEN}, timeout_seconds=timeout_seconds)


@pytest.fixture
def client():
    connected = McpClient(_profile(), "9.9.9")
    connected.connect()
    yield connected
    connected.close()


def _seen(client: McpClient) -> dict:
    return json.loads(client.call_tool("seen", {}).text)


# ----------------------------------------------------------------------
# The handshake
# ----------------------------------------------------------------------

def test_connecting_says_who_the_server_is_and_what_it_offers(client):
    server = client.server

    assert (server.name, server.version) == ("fake-server", "1.2.3")
    assert server.protocol_version == PROTOCOL_VERSIONS[0]
    assert server.capabilities == {"tools", "resources", "prompts"}
    assert server.instructions == "Be kind to the fake."
    assert not client.closed


def test_the_server_is_told_the_handshake_is_done(client):
    assert "notifications/initialized" in _seen(client)["notifications"]


@pytest.mark.parametrize("version", PROTOCOL_VERSIONS[1:])
def test_an_older_revision_the_client_speaks_is_taken(version):
    client = McpClient(_profile("--protocol", version))
    try:
        assert client.connect().protocol_version == version
    finally:
        client.close()


def test_a_server_speaking_a_revision_the_client_does_not_is_refused_and_ended():
    client = McpClient(_profile("--protocol", "1999-01-01"))

    with pytest.raises(McpException, match="1999-01-01"):
        client.connect()

    assert client.closed
    assert client.server is None


def test_a_server_that_never_answers_the_handshake_is_given_up_on():
    client = McpClient(_profile("--silent", timeout_seconds=1.0))
    started = time.monotonic()

    with pytest.raises(McpTimeout, match="initialize within 1 seconds"):
        client.connect()

    assert time.monotonic() - started < 10
    assert client.closed


def test_a_program_that_is_not_there_is_said_without_its_path(tmp_path):
    client = McpClient(McpServerProfile("gone", (str(tmp_path / "no_such_server"),)))

    with pytest.raises(McpException) as caught:
        client.connect()

    assert "could not be started" in str(caught.value)
    assert str(tmp_path) not in str(caught.value)


def test_a_program_that_is_not_an_mcp_server_ends_the_connection():
    client = McpClient(McpServerProfile("python", (sys.executable, "-c", "print('hello')"), timeout_seconds=20))

    with pytest.raises(McpClosed):
        client.connect()


# ----------------------------------------------------------------------
# What the server offers
# ----------------------------------------------------------------------

def test_the_tools_are_listed_with_what_the_server_says_of_each(client):
    tools = {tool.name: tool for tool in client.list_tools()}

    assert list(tools)[:3] == ["echo", "write_file", "slow"]
    assert (tools["echo"].read_only, tools["echo"].destructive, tools["echo"].title) == (True, False, "Echo")
    assert (tools["write_file"].read_only, tools["write_file"].destructive) == (False, True)
    assert tools["write_file"].title == "Write a file"
    assert tools["write_file"].required_arguments() == ["path", "content"]
    assert tools["slow"].input_schema["properties"] == {"seconds": {"type": "number"}}
    assert tools["fail"].required_arguments() == []


def test_a_listing_in_pages_is_followed_to_its_end():
    paged = McpClient(_profile("--pages"))
    try:
        paged.connect()
        assert [tool.name for tool in paged.list_tools()] == [
            "echo", "write_file", "slow", "fail", "refuse", "leak", "quit", "noise", "picture", "seen",
            "wrong_shape"]
    finally:
        paged.close()


def test_the_resources_are_listed_and_read(client):
    resources = client.list_resources()

    assert [(resource.uri, resource.name, resource.mime_type) for resource in resources] == [
        ("memo://greeting", "greeting", "text/plain"), ("memo://logo", "logo", "image/png")]
    assert resources[0].description == "A greeting."
    assert client.read_resource("memo://greeting") == "hello there"
    assert client.read_resource("memo://logo") == "[image/png: memo://logo]"


def test_the_prompts_are_listed_and_filled_in(client):
    (prompt,) = client.list_prompts()

    assert (prompt.name, prompt.description) == ("review", "Ask for a review of some code.")
    assert prompt.arguments == (("code", "The code to review.", True), ("tone", "How to say it.", False))
    assert client.get_prompt("review", {"code": "x = 1", "tone": "kind"}) == (
        "user:\nPlease review: x = 1\n\nassistant:\nIn a kind tone.")


# ----------------------------------------------------------------------
# Calls
# ----------------------------------------------------------------------

def test_a_tool_is_called_and_its_text_comes_back(client):
    result = client.call_tool("echo", {"text": "héllo 你好"})

    assert (result.text, result.is_error) == ("héllo 你好", False)
    assert result.raw == {"content": [{"type": "text", "text": "héllo 你好"}]}


def test_a_tool_that_ran_and_failed_says_so_in_its_result(client):
    result = client.call_tool("fail", {})

    assert result.is_error
    assert result.text == "the disk is full\nno space left"


def test_a_server_that_refuses_a_call_raises_with_its_code_and_words(client):
    with pytest.raises(McpRemoteError) as caught:
        client.call_tool("refuse", {})

    assert caught.value.code == -32602
    assert "not with these arguments" in caught.value.remote_message
    assert "tools/call" in str(caught.value)


def test_a_secret_the_server_was_given_is_taken_out_of_its_error(client):
    with pytest.raises(McpRemoteError) as caught:
        client.call_tool("refuse", {})

    assert TOKEN not in str(caught.value)
    assert "***" in caught.value.remote_message


def test_content_that_is_not_text_is_named_by_its_kind(client):
    assert client.call_tool("picture", {}).text == "[image: image/png]\n[link: memo://logo]\nhello"


@pytest.mark.parametrize(("block", "text"), [
    ({"type": "text", "text": "plain"}, "plain"),
    ({"type": "audio", "mimeType": "audio/wav", "data": "AAAA"}, "[audio: audio/wav]"),
    ({"type": "resource", "resource": {"uri": "file:///a.bin", "blob": "AAAA"}}, "[resource: file:///a.bin]"),
    ({"type": "something_new"}, "[something_new]"),
    ({}, "[content]"),
    ("not a block", ""),
    (None, ""),
])
def test_a_block_of_content_is_read_whatever_it_is(block, text):
    assert block_text(block) == text


def test_lines_that_are_not_messages_are_passed_over(client):
    assert client.call_tool("noise", {}).text == "after the noise"


def test_a_result_that_is_not_an_object_is_an_error_not_a_crash(client):
    with pytest.raises(McpException, match="not a reply"):
        client.call_tool("wrong_shape", {})

    assert client.call_tool("echo", {"text": "still here"}).text == "still here"


def test_a_method_the_server_does_not_have_is_its_error(client):
    with pytest.raises(McpRemoteError) as caught:
        client.request("no/such/method")

    assert caught.value.code == -32601


# ----------------------------------------------------------------------
# Time limits, cancelling, and a server that goes away
# ----------------------------------------------------------------------

def test_a_call_that_takes_too_long_is_given_up_on_and_the_server_is_told(client):
    with pytest.raises(McpTimeout, match="tools/call within 1 seconds"):
        client.request("tools/call", {"name": "slow", "arguments": {"seconds": 2}}, timeout_seconds=1)

    # The late answer is dropped; the connection goes on
    assert client.call_tool("echo", {"text": "after"}).text == "after"
    assert len(_seen(client)["cancelled"]) == 1


def test_a_call_is_cancelled_from_another_thread(client):
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    started = time.monotonic()

    with pytest.raises(McpCancelled, match="tools/call was cancelled"):
        client.call_tool("slow", {"seconds": 2}, cancel)

    assert time.monotonic() - started < 1.5
    assert client.call_tool("echo", {"text": "after"}).text == "after"
    assert len(_seen(client)["cancelled"]) == 1


def test_a_cancel_set_before_the_call_gives_it_up_at_once(client):
    cancel = threading.Event()
    cancel.set()

    with pytest.raises(McpCancelled):
        client.call_tool("echo", {"text": "never"}, cancel)


def test_a_server_that_goes_away_fails_the_call_that_was_waiting(client):
    with pytest.raises(McpClosed):
        client.call_tool("quit", {})

    assert client.closed
    with pytest.raises(McpClosed):
        client.call_tool("echo", {"text": "too late"})


def test_closing_fails_what_is_waiting_and_ends_the_server(client):
    failures: list[BaseException] = []

    def wait_for_slow():
        try:
            client.call_tool("slow", {"seconds": 30})
        except McpException as error:
            failures.append(error)

    waiting = threading.Thread(target=wait_for_slow)
    waiting.start()
    time.sleep(0.3)

    client.close()
    waiting.join(15)

    assert not waiting.is_alive()
    assert [type(failure) for failure in failures] == [McpClosed]
    assert client.closed


def test_closing_twice_and_closing_what_never_started_are_harmless():
    never = McpClient(_profile())
    never.close()
    never.close()

    assert never.closed
    with pytest.raises(McpClosed):
        never.request("ping")


def test_two_threads_can_ask_at_once(client):
    answers: dict[str, str] = {}

    def ask(text: str) -> None:
        answers[text] = client.call_tool("echo", {"text": text}).text

    threads = [threading.Thread(target=ask, args=(f"thread {number}",)) for number in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(20)

    assert answers == {f"thread {number}": f"thread {number}" for number in range(8)}


# ----------------------------------------------------------------------
# What the server asks and says
# ----------------------------------------------------------------------

def test_the_servers_ping_is_answered_and_what_this_client_does_not_offer_is_refused(client):
    # The answers are sent from the thread that reads the server: they may reach it after the next call does
    deadline = time.monotonic() + 10
    replies: dict = {}
    while len(replies) < 2 and time.monotonic() < deadline:
        replies = {reply["id"]: reply for reply in _seen(client)["replies"]}

    assert replies["server-1"] == {"jsonrpc": "2.0", "id": "server-1", "result": {}}
    assert replies["server-2"]["error"]["code"] == -32601


def test_a_notification_from_the_server_is_handed_on():
    heard: list[tuple[str, dict]] = []
    listening = McpClient(_profile())
    listening.on_notification = lambda method, params: heard.append((method, params))
    try:
        listening.connect()
        listening.call_tool("seen", {})
        assert ("notifications/message", {"level": "info", "data": "ready"}) in heard
    finally:
        listening.close()


def test_a_listener_that_fails_does_not_end_the_connection():
    def fails(_method, _params):
        raise RuntimeError("the listener broke")

    listening = McpClient(_profile())
    listening.on_notification = fails
    try:
        listening.connect()
        assert listening.call_tool("echo", {"text": "still"}).text == "still"
    finally:
        listening.close()


def test_the_servers_own_log_is_kept_without_its_secrets(client):
    client.call_tool("leak", {})
    deadline = time.monotonic() + 5
    while not client.log_tail() and time.monotonic() < deadline:
        time.sleep(0.02)

    assert client.log_tail() == ["starting with token ***"]


# ----------------------------------------------------------------------
# The transport
# ----------------------------------------------------------------------

def test_the_server_gets_the_profiles_variables_and_not_the_ides_own(monkeypatch):
    from pybreeze.utils.subprocess_util import IDE_ONLY

    monkeypatch.setenv("LOCUST_SKIP_MONKEY_PATCH", IDE_ONLY)
    script = "import json, os, sys; print(json.dumps({'env': sorted(os.environ)})); sys.stdout.flush(); sys.stdin.read()"
    received: list[dict] = []
    closed = threading.Event()
    transport = StdioTransport(
        McpServerProfile("env", (sys.executable, "-c", script), environment={"FAKE_TOKEN": TOKEN}),
        received.append, closed.set)

    transport.start()
    deadline = time.monotonic() + 20
    while not received and time.monotonic() < deadline:
        time.sleep(0.02)
    transport.close()

    assert closed.wait(15)
    assert "FAKE_TOKEN" in received[0]["env"]
    assert "LOCUST_SKIP_MONKEY_PATCH" not in received[0]["env"]


def test_sending_to_a_server_that_is_gone_says_so():
    closed = threading.Event()
    transport = StdioTransport(McpServerProfile("brief", (sys.executable, "-c", "pass")), lambda _message: None, closed.set)
    transport.start()
    assert closed.wait(20)
    time.sleep(0.1)

    with pytest.raises(McpClosed):
        for _attempt in range(50):
            transport.send({"jsonrpc": "2.0", "method": "ping"})
            time.sleep(0.02)


def test_a_transport_that_was_never_started_closes_and_refuses_quietly():
    transport = StdioTransport(_profile(), lambda _message: None, lambda: None)

    transport.close()

    assert transport.log_tail() == []
    with pytest.raises(McpClosed):
        transport.send({})

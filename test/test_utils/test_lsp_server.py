"""The action language server: the protocol's messages, its framing, and the process an editor starts.

The exchanges under ``fixtures/language_service/protocol`` are the protocol
fixtures: what an editor sends and what the server must answer, message for
message. Nothing here needs Qt, and no framework is imported: the keywords are
the metadata fixtures beside them.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from pybreeze.extend.language_server import server_main
from pybreeze.extend.language_server.launch import server_command
from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict as WORDS
from pybreeze.extend_multi_language.extend_traditional_chinese import pybreeze_traditional_chinese_word_dict
from pybreeze.utils.exception.exceptions import LanguageServiceException
from pybreeze.utils.language_service.framework_profiles import PROFILES, profile_of
from pybreeze.utils.language_service.keyword_metadata import FrameworkMetadata, Keyword, metadata_from_dict
from pybreeze.utils.language_service.lsp_server import (
    INTERNAL_ERROR,
    LOADING,
    MAX_MESSAGE_BYTES,
    PARSE_ERROR,
    READY,
    SERVER_NAME,
    UNAVAILABLE,
    ActionLanguageServer,
    ProtocolError,
    encode,
    read_message,
    serve,
)
from pybreeze.utils.subprocess_util import utf8_subprocess_env

FIXTURES = Path(__file__).parent / "fixtures" / "language_service"
EXCHANGES = sorted((FIXTURES / "protocol").glob("*.json"))
URI = "file:///project/script.json"
BROKEN_SCRIPT = '[["WR_to_urll", {"url": "x"}]]'


def _metadata(framework: str) -> FrameworkMetadata:
    return metadata_from_dict(json.loads((FIXTURES / f"{framework}.metadata.json").read_text(encoding="utf-8")))


def _server(*frameworks: str) -> ActionLanguageServer:
    server = ActionLanguageServer(WORDS, "test")
    for framework in frameworks:
        server.offer(_metadata(framework))
    return server


def _opened(text: str, uri: str = URI) -> dict:
    return {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
        "textDocument": {"uri": uri, "languageId": "json", "version": 1, "text": text}}}


def _request(request_id: int, method: str, params: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def _codes(messages: list[dict]) -> list[list[str]]:
    """The codes of the diagnostics each of *messages* publishes."""
    return [[found["code"] for found in message["params"]["diagnostics"]] for message in messages]


def _written(sink: bytes) -> list[dict]:
    stream = io.BytesIO(sink)
    return list(iter(lambda: read_message(stream), None))


# ----------------------------------------------------------------------
# The protocol fixtures
# ----------------------------------------------------------------------

def test_there_are_exchanges_for_each_framework_and_for_what_is_not_a_script():
    assert {path.stem for path in EXCHANGES} >= {
        "lifecycle", "webrunner_script", "autocontrol_script", "loaddensity_script", "other_json", "new_file",
        "bad_requests"}


@pytest.mark.parametrize("path", EXCHANGES, ids=lambda path: path.stem)
def test_the_server_answers_each_exchange_message_for_message(path):
    exchange = json.loads(path.read_text(encoding="utf-8"))
    server = _server(*exchange["frameworks"])

    for step, turn in enumerate(exchange["exchange"]):
        assert server.handle(turn["send"]) == turn["expect"], f"{path.stem}, step {step}: {turn['send']}"


def test_initialize_says_what_the_server_can_do():
    result = _server().handle(_request(1, "initialize"))[0]["result"]

    assert result["serverInfo"] == {"name": SERVER_NAME, "version": "test"}
    assert result["capabilities"]["textDocumentSync"]["change"] == 1
    assert result["capabilities"]["hoverProvider"] and result["capabilities"]["definitionProvider"]
    assert result["capabilities"]["completionProvider"] == {"triggerCharacters": ['"']}


def test_exit_stops_the_server_and_shutdown_alone_does_not():
    server = _server()

    server.handle(_request(1, "shutdown"))
    assert not server.stopped
    server.handle({"jsonrpc": "2.0", "method": "exit"})
    assert server.stopped


def test_the_diagnostics_are_in_the_language_the_server_was_given():
    server = ActionLanguageServer(pybreeze_traditional_chinese_word_dict, "test")
    server.offer(_metadata("je_web_runner"))

    message = server.handle(_opened(BROKEN_SCRIPT))[0]["params"]["diagnostics"][0]["message"]

    assert message == "WR_to_urll 不是 WebRunner 0.0.66 的關鍵字。你是指 WR_to_url 嗎？"


def test_a_request_that_fails_inside_is_answered_with_the_failures_name_only():
    server = _server("je_web_runner")

    def fails(_params):
        raise RuntimeError("C:/secret/path went wrong")

    server._requests["textDocument/hover"] = fails

    assert server.handle(_request(7, "textDocument/hover")) == [
        {"jsonrpc": "2.0", "id": 7, "error": {"code": INTERNAL_ERROR, "message": "RuntimeError"}}]


def test_a_notification_that_fails_inside_sends_nothing_and_the_server_goes_on():
    server = _server("je_web_runner")

    def fails(_params):
        raise RuntimeError("no")

    server._notifications["textDocument/didOpen"] = fails

    assert server.handle(_opened("[]")) == []
    assert server.handle(_request(1, "shutdown"))[0]["result"] is None


# ----------------------------------------------------------------------
# Keywords that arrive later, or never
# ----------------------------------------------------------------------

def test_a_framework_is_loading_until_its_keywords_come_or_are_declined():
    server = _server()
    assert [told["state"] for told in server.frameworks()] == [LOADING] * len(PROFILES)

    server.offer(_metadata("je_web_runner"))
    server.decline("je_auto_control", "je_auto_control is not installed for the interpreter that runs the scripts")

    told = {each["framework"]: each for each in server.frameworks()}
    assert (told["je_web_runner"]["state"], told["je_web_runner"]["version"]) == (READY, "0.0.66")
    assert told["je_web_runner"]["keywords"] == 6
    assert told["je_web_runner"]["capabilities"] == ["completion", "definition", "diagnostics", "hover"]
    assert told["je_auto_control"]["state"] == UNAVAILABLE
    assert "not installed" in told["je_auto_control"]["reason"]
    assert (told["je_load_density"]["state"], told["je_load_density"]["capabilities"]) == (LOADING, [])


def test_a_script_opened_before_its_keywords_came_is_checked_again_when_they_do():
    server = _server()
    assert _codes(server.handle(_opened(BROKEN_SCRIPT))) == [[]]

    published = server.offer(_metadata("je_web_runner"))

    assert [message["params"]["uri"] for message in published] == [URI]
    assert _codes(published) == [["unknown-keyword"]]


def test_while_its_keywords_are_not_at_hand_a_script_is_still_told_whether_it_is_json():
    server = _server("je_auto_control")

    assert _codes(server.handle(_opened('[["WR_quit"] ["WR_quit"]]'))) == [["json-syntax"]]
    assert _codes(server.handle(_opened('[["WR_no_such_keyword"]]'))) == [[]]


def test_a_script_is_its_frameworks_alone_also_while_that_framework_is_missing():
    server = _server("je_auto_control")
    server.handle(_opened('[["WR_'))

    items = server.handle(_request(1, "textDocument/completion", {
        "textDocument": {"uri": URI}, "position": {"line": 0, "character": 6}}))[0]["result"]["items"]

    assert items == []


def test_keywords_offered_twice_or_for_no_known_framework_change_nothing():
    server = _server("je_web_runner")
    server.handle(_opened(BROKEN_SCRIPT))

    assert server.offer(_metadata("je_web_runner")) == []
    assert server.offer(FrameworkMetadata("je_something_else", "1", {"X": Keyword("X")})) == []
    assert [told["framework"] for told in server.frameworks()] == [profile.framework for profile in PROFILES]


def test_a_decline_after_the_keywords_came_does_not_take_them_back():
    server = _server("je_web_runner")

    server.decline("je_web_runner", "too late")

    assert server.frameworks()[0]["state"] == READY


# ----------------------------------------------------------------------
# Framing
# ----------------------------------------------------------------------

@pytest.mark.parametrize("message", [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"text": "關鍵字 \U0001F600 é"}},
])
def test_a_message_framed_and_read_back_is_the_same(message):
    framed = encode(message)

    assert framed.startswith(b"Content-Length: ")
    assert read_message(io.BytesIO(framed)) == message


def test_the_length_counts_bytes_not_characters():
    framed = encode({"text": "é"})
    header, body = framed.split(b"\r\n\r\n")

    assert int(header.split(b": ")[1]) == len(body) == len('{"text":"é"}'.encode())


def test_messages_are_read_one_after_another_until_the_stream_ends():
    stream = io.BytesIO(encode({"id": 1}) + encode({"id": 2}))

    assert [read_message(stream), read_message(stream), read_message(stream)] == [{"id": 1}, {"id": 2}, None]


def test_other_headers_and_any_capitals_are_accepted():
    body = b'{"id": 1}'
    framed = (b"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n"
              b"CONTENT-LENGTH: " + str(len(body)).encode() + b"\r\n\r\n" + body)

    assert read_message(io.BytesIO(framed)) == {"id": 1}


def test_a_message_cut_short_is_the_end_of_the_stream():
    assert read_message(io.BytesIO(encode({"id": 1})[:-3])) is None
    assert read_message(io.BytesIO(b"Content-Length: 5\r\n")) is None


@pytest.mark.parametrize("framed", [
    b"\r\n{}",
    b"Content-Length: abc\r\n\r\n{}",
    b"Content-Length: -1\r\n\r\n{}",
    b"Content-Length: " + str(MAX_MESSAGE_BYTES + 1).encode() + b"\r\n\r\n{}",
    b"Content-Length: 8\r\n\r\nnot json",
    b"Content-Length: 2\r\n\r\n[]",
    b"Content-Length: 2\r\n\r\n\xff\xfe",
])
def test_bytes_that_are_not_a_message_are_refused(framed):
    with pytest.raises(ProtocolError):
        read_message(io.BytesIO(framed))


# ----------------------------------------------------------------------
# Serving a stream
# ----------------------------------------------------------------------

def test_a_stream_is_answered_message_by_message_until_exit():
    server = _server("je_web_runner")
    source = io.BytesIO(b"".join(encode(message) for message in [
        _request(1, "initialize"), _opened(BROKEN_SCRIPT), _request(2, "shutdown"),
        {"jsonrpc": "2.0", "method": "exit"}, _request(3, "initialize")]))
    sink = io.BytesIO()

    serve(server, source, sink)

    written = _written(sink.getvalue())
    assert [message.get("id", message.get("method")) for message in written] == [
        1, "textDocument/publishDiagnostics", 2]
    assert server.stopped
    # What came after exit was not read
    assert read_message(source) == _request(3, "initialize")


def test_the_end_of_the_stream_ends_the_serving():
    server = _server()
    sink = io.BytesIO()

    serve(server, io.BytesIO(encode(_request(1, "initialize"))), sink)

    assert [message["id"] for message in _written(sink.getvalue())] == [1]
    assert not server.stopped


def test_bytes_that_are_not_a_message_are_answered_once_and_end_the_serving():
    sink = io.BytesIO()

    serve(_server(), io.BytesIO(b"Content-Length: 3\r\n\r\nabc" + encode(_request(1, "initialize"))), sink)

    assert _written(sink.getvalue()) == [
        {"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "not a protocol message"}}]


def _serve_while_reading(metadata: FrameworkMetadata, messages_after: list[dict]) -> list[dict]:
    """Serve an opened script while *metadata* is being read, send *messages_after* once it is in, and return what was written."""
    server = _server()
    read_end, write_end = os.pipe()
    sink = io.BytesIO()
    taken_in = threading.Event()

    def read_keywords():
        # Reading takes longer than answering: the script is opened and answered first
        deadline = time.monotonic() + 10
        while not sink.getvalue() and time.monotonic() < deadline:
            time.sleep(0.01)

        def give():
            try:
                return server.offer(metadata)
            finally:
                taken_in.set()
        return give

    with os.fdopen(read_end, "rb") as source, os.fdopen(write_end, "wb") as feed:
        feed.write(encode(_opened(BROKEN_SCRIPT)))
        feed.flush()
        serving = threading.Thread(target=serve, args=(server, source, sink, [read_keywords]))
        serving.start()
        assert taken_in.wait(10)
        for message in (*messages_after, {"jsonrpc": "2.0", "method": "exit"}):
            feed.write(encode(message))
        feed.flush()
        serving.join(10)
        assert not serving.is_alive()
    return _written(sink.getvalue())


def test_keywords_read_meanwhile_are_taken_in_between_two_messages():
    written = _serve_while_reading(_metadata("je_web_runner"), [_request(5, "pybreeze/frameworks")])

    assert _codes(written[:2]) == [[], ["unknown-keyword"]]
    assert written[2]["id"] == 5 and written[2]["result"][0]["state"] == READY


def test_a_task_that_fails_costs_its_own_result_only():
    def fails():
        raise RuntimeError("the framework could not be asked")

    sink = io.BytesIO()

    serve(_server(), io.BytesIO(encode(_request(1, "shutdown"))), sink, [fails])

    assert [message["id"] for message in _written(sink.getvalue())] == [1]


# ----------------------------------------------------------------------
# The process
# ----------------------------------------------------------------------

def test_the_servers_words_are_those_of_a_maintained_language_or_english():
    assert server_main.words_of("Traditional_Chinese") is pybreeze_traditional_chinese_word_dict
    assert server_main.words_of("English") is WORDS
    assert server_main.words_of("Japanese") is WORDS
    assert isinstance(server_main.server_version(), str)


def test_a_framework_that_answers_is_offered_and_one_that_does_not_is_declined(monkeypatch):
    server = _server()
    profile = profile_of("je_web_runner")

    monkeypatch.setattr(server_main, "read_metadata", lambda asked, interpreter: _metadata(asked.framework))
    assert server_main.ask_framework(server, profile, "python")() == []
    assert server.frameworks()[0]["state"] == READY

    def not_there(asked, interpreter):
        raise LanguageServiceException(f"{asked.framework} is not installed for the interpreter that runs the scripts")

    monkeypatch.setattr(server_main, "read_metadata", not_there)
    server_main.ask_framework(server, profile_of("je_auto_control"), "python")()
    assert server.frameworks()[1]["state"] == UNAVAILABLE


def _start(tmp_path, *arguments) -> subprocess.Popen:
    # A package called pybreeze in the folder the server is started in must not be the one imported
    decoy = tmp_path / "pybreeze"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("raise SystemExit(99)\n", encoding="utf-8")
    command = [*server_command(str(tmp_path / "no_such_python"), "English"), *arguments]
    environment = utf8_subprocess_env()
    environment.pop("PYTHONPATH", None)
    return subprocess.Popen(  # noqa: S603 — fixed argv: this interpreter and the server's own entry
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=tmp_path,
        env=environment, shell=False)


def test_the_process_an_editor_starts_answers_and_ends_cleanly(tmp_path):
    server = _start(tmp_path)
    try:
        for message in (_request(1, "initialize"), _opened('[["WR_quit"] ["WR_quit"]]'), _request(2, "shutdown"),
                        {"jsonrpc": "2.0", "method": "exit"}):
            server.stdin.write(encode(message))
        server.stdin.flush()
        output, errors = server.communicate(timeout=60)
    finally:
        server.kill()

    written = _written(output)
    assert server.returncode == 0, errors.decode("utf-8", "replace")
    assert errors == b""
    assert written[0]["result"]["serverInfo"]["name"] == SERVER_NAME
    assert _codes([message for message in written if message.get("method")][:1]) == [["json-syntax"]]
    assert written[-1] == {"jsonrpc": "2.0", "id": 2, "result": None}


def test_the_process_ends_when_the_editor_goes_away(tmp_path):
    server = _start(tmp_path)
    try:
        server.stdin.write(encode(_request(1, "initialize")))
        server.stdin.close()
        assert server.wait(timeout=60) == 0
        assert _written(server.stdout.read())[0]["id"] == 1
    finally:
        server.kill()
        server.stdout.close()
        server.stderr.close()


def test_the_server_can_be_started_as_a_module_and_says_how(tmp_path):
    done = subprocess.run(  # noqa: S603 — fixed argv: this interpreter and the server's module
        [sys.executable, "-m", "pybreeze.extend.language_server", "--help"], capture_output=True, timeout=60,
        cwd=Path(__file__).resolve().parents[2], env=utf8_subprocess_env(), shell=False, check=False)

    assert done.returncode == 0
    assert b"--interpreter" in done.stdout and b"--language" in done.stdout

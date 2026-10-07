"""A language server for action scripts: the Language Server Protocol, answered from the frameworks' adapters.

An editor that speaks the protocol (JEditor's own client does) gets the same
completion, diagnostics, hover and go-to-definition for a WebRunner, an
AutoControl and a LoadDensity script, from one server. The server is a process
of its own: what a framework's package does when it is asked about its
keywords happens there, and at worst the editor loses a list of completions.

Two parts, kept apart so that the first can be tested message by message:

- :class:`ActionLanguageServer` takes one protocol message and gives back the
  messages to send. It holds the open documents and the adapters, reads no
  stream and starts no thread.
- :func:`serve` reads messages from a stream, hands them over one at a time,
  and writes the answers. Whatever takes long (asking a framework for its
  keywords) runs on a thread of its own and is taken in between two
  messages, so the server answers while it waits.

Pure logic: no Qt, and no framework is imported here.
"""
from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable, Mapping
from typing import BinaryIO

from pybreeze.utils.language_service.action_adapter import (
    ActionLanguageAdapter, framework_of, syntax_diagnostics,
)
from pybreeze.utils.language_service.framework_profiles import PROFILES, profile_of
from pybreeze.utils.language_service.keyword_metadata import FrameworkMetadata
from pybreeze.utils.language_service.service_adapter import (
    CompletionItem, Diagnostic, LanguageService, LanguageServiceRegistry, Position, Range, TextDocument,
)
from pybreeze.utils.logging.logger import pybreeze_logger

SERVER_NAME = "pybreeze-action-language-server"

# JSON-RPC's error codes
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND = -32700, -32600, -32601
INVALID_PARAMS, INTERNAL_ERROR = -32602, -32603
# The protocol's: a document is sent whole on every change
_FULL_SYNC = 1
# A message larger than this is not read: nothing an editor sends comes near it
MAX_MESSAGE_BYTES = 64 * 1024 * 1024
_LENGTH_HEADER = b"content-length:"

# What a framework's keywords are doing, as the editor is told
LOADING, READY, UNAVAILABLE = "loading", "ready", "unavailable"


class ProtocolError(Exception):
    """Bytes on the stream that are not a protocol message."""


def encode(message: dict) -> bytes:
    """*message* as the protocol frames it: a ``Content-Length`` header, a blank line, the JSON."""
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body


def read_message(stream: BinaryIO) -> dict | None:
    """The next message on *stream*, or ``None`` when the stream has ended.

    :raises ProtocolError: when what is there is not a message; the stream is
        then at an unknown place and cannot be read further
    """
    length = None
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        if line.lower().startswith(_LENGTH_HEADER):
            length = line[len(_LENGTH_HEADER):].strip()
    if length is None or not length.isdigit() or int(length) > MAX_MESSAGE_BYTES:
        raise ProtocolError("a message without a usable Content-Length")
    body = stream.read(int(length))
    if len(body) < int(length):
        return None
    try:
        message = json.loads(body.decode("utf-8"))
    except ValueError as error:
        raise ProtocolError("a message that is not JSON") from error
    if not isinstance(message, dict):
        raise ProtocolError("a message that is not an object")
    return message


def _position(position: Position) -> dict:
    return {"line": position.line, "character": position.character}


def _range(span: Range) -> dict:
    return {"start": _position(span.start), "end": _position(span.end)}


def _diagnostic(diagnostic: Diagnostic) -> dict:
    return {"range": _range(diagnostic.range), "severity": diagnostic.severity.value, "code": diagnostic.code,
            "source": diagnostic.source, "message": diagnostic.message}


def _completion(item: CompletionItem) -> dict:
    written = {"label": item.label, "detail": item.detail, "documentation": item.documentation}
    if item.insert_text is not None:
        written["insertText"] = item.insert_text
    return written


class _BadParams(Exception):
    """A request whose parameters are not what its method takes."""


def _asked_about(params: object) -> tuple[str, Position]:
    """The document and the position a request is about."""
    try:
        uri = params["textDocument"]["uri"]
        position = Position(int(params["position"]["line"]), int(params["position"]["character"]))
    except (KeyError, TypeError, ValueError) as error:
        raise _BadParams from error
    if not isinstance(uri, str):
        raise _BadParams
    return uri, position


class ActionLanguageServer:
    """The protocol's messages, answered from the frameworks' adapters.

    :param words: the messages of the diagnostics, by language key (a PyBreeze dictionary)
    :param version: the server's version, as it tells the editor
    """

    def __init__(self, words: Mapping[str, str], version: str = "") -> None:
        self._words = words
        self._version = version
        self._documents: dict[str, TextDocument] = {}
        self._registry = LanguageServiceRegistry()
        self._metadata: dict[str, FrameworkMetadata] = {}
        self._unavailable: dict[str, str] = {}
        self.stopped = False
        self._requests: dict[str, Callable[[object], object]] = {
            "initialize": self._initialize,
            "shutdown": lambda _params: None,
            "textDocument/completion": self._completion,
            "textDocument/hover": self._hover,
            "textDocument/definition": self._definition,
            "pybreeze/frameworks": lambda _params: self.frameworks(),
        }
        self._notifications: dict[str, Callable[[object], list[dict]]] = {
            "exit": self._exit,
            "textDocument/didOpen": self._opened,
            "textDocument/didChange": self._changed,
            "textDocument/didSave": self._saved,
            "textDocument/didClose": self._closed,
        }

    # ------------------------------------------------------------------
    # The frameworks
    # ------------------------------------------------------------------

    def offer(self, metadata: FrameworkMetadata) -> list[dict]:
        """Take a framework's keywords; the open documents are checked again with them.

        :return: the diagnostics to publish
        """
        profile = profile_of(metadata.framework)
        if profile is None or metadata.framework in self._metadata:
            return []
        self._metadata[metadata.framework] = metadata
        self._unavailable.pop(metadata.framework, None)
        self._registry.register(ActionLanguageAdapter(profile, metadata, self._words))
        return [self._published(document) for document in self._documents.values()]

    def decline(self, framework: str, reason: str) -> list[dict]:
        """Note that *framework*'s keywords cannot be had, and why; its scripts get no answers."""
        if framework not in self._metadata:
            self._unavailable[framework] = reason
        return []

    def frameworks(self) -> list[dict]:
        """Each framework, whether its keywords are at hand, and what can be done with them."""
        told = []
        for profile in PROFILES:
            metadata = self._metadata.get(profile.framework)
            service = self._registry.service_for(profile.framework)
            reason = self._unavailable.get(profile.framework, "")
            told.append({
                "framework": profile.framework,
                "label": profile.label,
                "state": READY if metadata is not None else UNAVAILABLE if reason else LOADING,
                "version": metadata.version if metadata is not None else "",
                "keywords": len(metadata.own_keywords()) if metadata is not None else 0,
                "capabilities": sorted(capability.value for capability in service.capabilities())
                if service is not None else [],
                "reason": reason,
            })
        return told

    def _services(self, text: str) -> tuple[list[LanguageService], bool]:
        """The services to ask about *text*, and whether *text* is known to be one framework's script.

        A script that is one framework's is that framework's alone, also when
        its keywords are not at hand. Text that is nobody's yet (a new file) is
        asked of every framework: what it becomes depends on what is completed.
        """
        profile = framework_of(text, self._metadata)
        if profile is None:
            return [self._registry.service_for(name) for name in self._registry.frameworks()], False
        service = self._registry.service_for(profile.framework)
        return ([service] if service is not None else []), True

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def handle(self, message: dict) -> list[dict]:
        """Answer one message.

        :return: the messages to send: the reply to a request, and any notifications
        """
        method = message.get("method")
        if not isinstance(method, str):
            # A reply to something this server asked; it asks nothing
            return []
        if "id" not in message:
            return self._guarded(self._notifications.get(method, lambda _params: []), message.get("params"), [])
        request = self._requests.get(method)
        if request is None:
            return [self._error(message["id"], METHOD_NOT_FOUND, method)]
        try:
            result = request(message.get("params"))
        except _BadParams:
            return [self._error(message["id"], INVALID_PARAMS, method)]
        except Exception as error:  # noqa: BLE001 — a request must be answered whatever went wrong
            pybreeze_logger.error("lsp_server.py %s failed: %r", method, error)
            return [self._error(message["id"], INTERNAL_ERROR, type(error).__name__)]
        return [{"jsonrpc": "2.0", "id": message["id"], "result": result}]

    @staticmethod
    def _guarded(notified: Callable[[object], list[dict]], params: object, nothing: list[dict]) -> list[dict]:
        try:
            return notified(params)
        except _BadParams:
            return nothing
        except Exception as error:  # noqa: BLE001 — a notification has no reply to carry the failure
            pybreeze_logger.error("lsp_server.py notification failed: %r", error)
            return nothing

    @staticmethod
    def _error(request_id: object, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def reject(self) -> list[dict]:
        """The reply to bytes that were not a message."""
        return [self._error(None, PARSE_ERROR, "not a protocol message")]

    def _initialize(self, _params: object) -> dict:
        return {
            "capabilities": {
                "textDocumentSync": {"openClose": True, "change": _FULL_SYNC, "save": {"includeText": True}},
                "completionProvider": {"triggerCharacters": ['"']},
                "hoverProvider": True,
                "definitionProvider": True,
            },
            "serverInfo": {"name": SERVER_NAME, "version": self._version},
        }

    def _exit(self, _params: object) -> list[dict]:
        self.stopped = True
        return []

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    def _published(self, document: TextDocument) -> dict:
        """The diagnostics of *document*, as the notification that publishes them."""
        services, known = self._services(document.text)
        if known and services:
            found = [diagnostic for service in services for diagnostic in service.diagnose(document)]
        else:
            # Any other JSON file, or a script whose framework has no keywords at hand
            # (yet): only whether it is JSON
            found = syntax_diagnostics(document.text, self._words)
        return {"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics", "params": {
            "uri": document.uri, "version": document.version,
            "diagnostics": [_diagnostic(diagnostic) for diagnostic in found]}}

    def _keep(self, uri: object, text: object, version: object) -> list[dict]:
        if not isinstance(uri, str) or not isinstance(text, str):
            raise _BadParams
        document = TextDocument(uri, text, version if isinstance(version, int) else 0)
        self._documents[uri] = document
        return [self._published(document)]

    def _opened(self, params: object) -> list[dict]:
        try:
            given = params["textDocument"]
            return self._keep(given["uri"], given["text"], given.get("version"))
        except (KeyError, TypeError, AttributeError) as error:
            raise _BadParams from error

    def _changed(self, params: object) -> list[dict]:
        try:
            given = params["textDocument"]
            return self._keep(given["uri"], params["contentChanges"][-1]["text"], given.get("version"))
        except (KeyError, TypeError, IndexError, AttributeError) as error:
            raise _BadParams from error

    def _saved(self, params: object) -> list[dict]:
        try:
            uri = params["textDocument"]["uri"]
            text = params.get("text")
        except (KeyError, TypeError, AttributeError) as error:
            raise _BadParams from error
        known = self._documents.get(uri)
        if isinstance(text, str):
            return self._keep(uri, text, known.version if known is not None else 0)
        return [self._published(known)] if known is not None else []

    def _closed(self, params: object) -> list[dict]:
        try:
            uri = params["textDocument"]["uri"]
        except (KeyError, TypeError) as error:
            raise _BadParams from error
        if self._documents.pop(uri, None) is None:
            return []
        # What was said about a file that is no longer open is taken back
        return [{"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                 "params": {"uri": uri, "diagnostics": []}}]

    # ------------------------------------------------------------------
    # Requests about a position
    # ------------------------------------------------------------------

    def _asked(self, params: object) -> tuple[TextDocument, Position, list[LanguageService]] | None:
        uri, position = _asked_about(params)
        document = self._documents.get(uri)
        if document is None:
            return None
        return document, position, self._services(document.text)[0]

    def _completion(self, params: object) -> dict:
        asked = self._asked(params)
        items: dict[str, CompletionItem] = {}
        if asked is not None:
            document, position, services = asked
            for service in services:
                for item in service.complete(document, position):
                    items.setdefault(item.label, item)
        return {"isIncomplete": False, "items": [_completion(item) for item in items.values()]}

    def _hover(self, params: object) -> dict | None:
        asked = self._asked(params)
        if asked is None:
            return None
        document, position, services = asked
        for service in services:
            hover = service.hover(document, position)
            if hover is not None:
                shown: dict = {"contents": {"kind": "plaintext", "value": hover.contents}}
                if hover.range is not None:
                    shown["range"] = _range(hover.range)
                return shown
        return None

    def _definition(self, params: object) -> list[dict]:
        asked = self._asked(params)
        if asked is None:
            return []
        document, position, services = asked
        return [{"uri": location.uri, "range": _range(location.range)}
                for service in services for location in service.definition(document, position)]


def _send(sink: BinaryIO, outgoing: list[dict]) -> None:
    for message in outgoing:
        sink.write(encode(message))
    sink.flush()


def _run_task(task: Callable[[], Callable[[], list[dict]]], sink: BinaryIO, turn: threading.Lock) -> None:
    """Run *task* on this thread, then do what it leaves to be done when no message is being answered."""
    try:
        finish = task()
    except Exception as error:  # noqa: BLE001 — one framework's failure must not end the thread unseen
        pybreeze_logger.error("lsp_server.py background task failed: %r", error)
        return
    with turn:
        _send(sink, finish())


def serve(server: ActionLanguageServer, source: BinaryIO, sink: BinaryIO,
          tasks: Iterable[Callable[[], Callable[[], list[dict]]]] = ()) -> None:
    """Answer the messages of *source* on *sink* until the editor says ``exit`` or the stream ends.

    Messages are read and answered on the calling thread, one at a time. The
    stream is not read on a thread of its own: one still waiting in a read
    when the interpreter shuts down brings the process down with a fatal
    error instead of an exit code.

    :param server: what answers
    :param source: where messages are read from (the process's standard input)
    :param sink: where answers are written (its standard output)
    :param tasks: slow things to do meanwhile, each on a thread of its own. A
        task returns what is left to do with its result (give the server a
        framework's keywords); that is done between two messages, never
        during one, and gives the messages to send.
    """
    turn = threading.Lock()
    for task in tasks:
        threading.Thread(target=_run_task, args=(task, sink, turn), daemon=True).start()
    while not server.stopped:
        try:
            message = read_message(source)
        except ProtocolError as error:
            pybreeze_logger.error("lsp_server.py stream not read: %r", error)
            with turn:
                _send(sink, server.reject())
            break
        except (OSError, ValueError) as error:
            pybreeze_logger.info("lsp_server.py stream closed: %r", error)
            break
        if message is None:
            break
        with turn:
            _send(sink, server.handle(message))
    # Kept for good: a task that finishes after this writes nothing to a stream that is being closed
    turn.acquire()

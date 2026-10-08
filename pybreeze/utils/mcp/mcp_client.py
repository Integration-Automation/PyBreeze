"""A client for the Model Context Protocol: connect to a server, see what it offers, call it.

An MCP server offers **tools** (things to call), **resources** (things to read)
and **prompts** (texts to fill in). :class:`McpClient` speaks the protocol to
one server over a transport (``mcp_transport.py``): the opening handshake, the
three listings, a tool call, a resource read, a prompt.

Every request is answered or given up on: it has a time limit (the profile's),
it can be cancelled from another thread, and when either happens the server is
told (``notifications/cancelled``) and the late answer is dropped. A server
that goes away fails whatever was waiting. Calls block the thread that makes
them, so a user interface makes them on a worker thread; nothing here is Qt.

What a server sends is data from another program. It is read field by field
into the types below, and a reply of the wrong shape is an error, not a crash.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from pybreeze.utils.exception.exception_tags import (
    mcp_cancelled_error,
    mcp_remote_error,
    mcp_reply_error,
    mcp_timeout_error,
    mcp_version_error,
)
from pybreeze.utils.exception.exceptions import McpException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.mcp.mcp_profile import McpServerProfile
from pybreeze.utils.mcp.mcp_redaction import redact_text
from pybreeze.utils.mcp.mcp_transport import McpClosed, StdioTransport

# The protocol revisions this client speaks, the newest first: it offers the
# first, and takes whichever of them the server answers with
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
CLIENT_NAME = "PyBreeze"
# JSON-RPC: the method asked for is not one this side has
_METHOD_NOT_FOUND = -32601
# How often a waiting request looks whether it was cancelled or the server is gone
_POLL_SECONDS = 0.05
# A listing is followed through this many pages at most: a server that always
# names a next page would otherwise be read for ever
_MAX_PAGES = 100
# A remote error's message is cut to this: it is the server's text, shown in a status line
_MESSAGE_CHARACTERS = 500


class McpTimeout(McpException):
    """The server did not answer in time."""


class McpCancelled(McpException):
    """The request was cancelled before the server answered."""


class McpRemoteError(McpException):
    """The server answered with an error.

    :param method: what was asked
    :param code: the server's error code
    :param message: the server's own words, cut short
    """

    def __init__(self, method: str, code: object, message: str) -> None:
        super().__init__(mcp_remote_error.format(method=method, code=code, message=message))
        self.code = code
        self.remote_message = message


@dataclass(frozen=True)
class McpServerInfo:
    """What a server said of itself as the connection opened."""

    name: str
    version: str
    protocol_version: str
    capabilities: frozenset[str]
    instructions: str = ""


@dataclass(frozen=True)
class McpTool:
    """A tool a server offers.

    :param read_only: the server says the tool changes nothing. A hint, and the server's own: it is shown, not trusted
    :param destructive: the server says the tool may destroy something
    """

    name: str
    title: str = ""
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    read_only: bool = False
    destructive: bool = False

    def required_arguments(self) -> list[str]:
        """The arguments the tool's schema says a call must give."""
        required = self.input_schema.get("required")
        return [name for name in required if isinstance(name, str)] if isinstance(required, list) else []


@dataclass(frozen=True)
class McpToolResult:
    """What a tool call gave back.

    :param text: its content as text: text as it is, anything else named by its kind
    :param is_error: the tool ran and says it failed
    :param raw: the server's whole result
    """

    text: str
    is_error: bool
    raw: dict


@dataclass(frozen=True)
class McpResource:
    """Something a server offers to be read."""

    uri: str
    name: str = ""
    description: str = ""
    mime_type: str = ""


@dataclass(frozen=True)
class McpPrompt:
    """A text a server offers to fill in; *arguments* are (name, description, required)."""

    name: str
    description: str = ""
    arguments: tuple[tuple[str, str, bool], ...] = ()


def _text(data: object, key: str) -> str:
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, str) else ""


def _records(result: dict, key: str) -> list[dict]:
    """The objects under *key* of *result*; what is not an object is passed over."""
    found = result.get(key)
    return [record for record in found if isinstance(record, dict)] if isinstance(found, list) else []


def block_text(block: object) -> str:
    """One block of content as text: text as it is, anything else named by its kind and where it is."""
    if not isinstance(block, dict):
        return ""
    kind = _text(block, "type")
    if kind == "text":
        return _text(block, "text")
    resource = block.get("resource")
    if kind == "resource" and isinstance(resource, dict):
        return _text(resource, "text") or f"[resource: {_text(resource, 'uri')}]"
    if kind == "resource_link":
        return f"[link: {_text(block, 'uri')}]"
    described = _text(block, "mimeType")
    return f"[{kind or 'content'}: {described}]" if described else f"[{kind or 'content'}]"


class _Waiting:
    """A request that has been sent: what wakes it, and the reply once it has one."""

    def __init__(self) -> None:
        self.answered = threading.Event()
        self.reply: dict | None = None


class McpClient:
    """One connection to one MCP server.

    :param profile: the server, and how long a request to it may take
    :param client_version: PyBreeze's version, told to the server
    :param transport: what carries the messages; the standard-input-and-output one when not given
    """

    def __init__(self, profile: McpServerProfile, client_version: str = "", transport: type = StdioTransport) -> None:
        self._profile = profile
        self._client_version = client_version
        self._transport = transport(profile, self._received, self._lost)
        self._waiting: dict[int, _Waiting] = {}
        self._guard = threading.Lock()
        self._next_id = 1
        self._closed = False
        self.server: McpServerInfo | None = None
        #: Called with (method, params) for each notification the server sends, on the reading thread
        self.on_notification: Callable[[str, dict], None] | None = None

    # ------------------------------------------------------------------
    # The connection
    # ------------------------------------------------------------------

    @property
    def closed(self) -> bool:
        """Whether the server is gone or the connection was closed."""
        return self._closed

    def connect(self) -> McpServerInfo:
        """Start the server and open the connection.

        :raises McpException: when the server cannot be started, does not
            answer, or speaks a protocol revision this client does not
        """
        self._transport.start()
        try:
            result = self.request("initialize", {
                "protocolVersion": PROTOCOL_VERSIONS[0], "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": self._client_version}})
            version = _text(result, "protocolVersion")
            if version not in PROTOCOL_VERSIONS:
                raise McpException(mcp_version_error.format(version=version))
            self._transport.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except McpException:
            self.close()
            raise
        capabilities = result.get("capabilities")
        self.server = McpServerInfo(
            name=_text(result.get("serverInfo"), "name"), version=_text(result.get("serverInfo"), "version"),
            protocol_version=version,
            capabilities=frozenset(capabilities) if isinstance(capabilities, dict) else frozenset(),
            instructions=_text(result, "instructions"))
        return self.server

    def close(self) -> None:
        """Close the connection and end the server; whatever was waiting fails with :class:`McpClosed`."""
        self._lost()
        self._transport.close()

    def log_tail(self) -> list[str]:
        """The last lines of the server's own log (its standard error), its secrets taken out."""
        return self._transport.log_tail()

    def _lost(self) -> None:
        """The server is gone: nothing more will be answered."""
        with self._guard:
            self._closed = True
            waiting, self._waiting = list(self._waiting.values()), {}
        for each in waiting:
            each.answered.set()

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def _received(self, message: dict) -> None:
        """Take one message from the server: a reply, a request of its own, or a notification."""
        method = message.get("method")
        if not isinstance(method, str):
            with self._guard:
                waiting = self._waiting.pop(message.get("id"), None)
            if waiting is not None:
                waiting.reply = message
                waiting.answered.set()
            return
        if "id" in message:
            self._answer(message["id"], method)
            return
        params = message.get("params")
        notify = self.on_notification
        if notify is not None:
            try:
                notify(method, params if isinstance(params, dict) else {})
            except Exception as error:  # noqa: BLE001 — whoever listens must not end the thread that reads the server
                pybreeze_logger.error("mcp_client.py notification %s not taken: %r", method, error)

    def _answer(self, request_id: object, method: str) -> None:
        """Answer a request the server makes: a ping, and nothing else (this client offers the server nothing)."""
        reply: dict = {"jsonrpc": "2.0", "id": request_id}
        if method == "ping":
            reply["result"] = {}
        else:
            reply["error"] = {"code": _METHOD_NOT_FOUND, "message": "not offered by this client"}
        try:
            self._transport.send(reply)
        except McpClosed as error:
            pybreeze_logger.debug("mcp_client.py %s not answered: %r", method, error)

    def request(self, method: str, params: dict | None = None, *, timeout_seconds: float | None = None,
                cancel: threading.Event | None = None) -> dict:
        """Ask the server for *method* and wait for its result.

        :param timeout_seconds: how long to wait; the profile's time when not given
        :param cancel: set from another thread to give the request up
        :raises McpTimeout: when the server does not answer in time
        :raises McpCancelled: when *cancel* was set first
        :raises McpRemoteError: when the server answers with an error
        :raises McpClosed: when the server is gone
        :raises McpException: when the answer is not a result
        """
        if cancel is not None and cancel.is_set():
            # Given up before it was sent: the server is not asked at all
            raise McpCancelled(mcp_cancelled_error.format(method=method))
        waiting = _Waiting()
        with self._guard:
            if self._closed:
                raise McpClosed
            request_id, self._next_id = self._next_id, self._next_id + 1
            self._waiting[request_id] = waiting
        message: dict = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        limit = self._profile.timeout_seconds if timeout_seconds is None else timeout_seconds
        try:
            self._transport.send(message)
            self._wait(waiting, request_id, method, limit, cancel)
        finally:
            with self._guard:
                self._waiting.pop(request_id, None)
        return self._result(method, waiting.reply)

    def _wait(self, waiting: _Waiting, request_id: int, method: str, limit: float,
              cancel: threading.Event | None) -> None:
        """Wait until the request is answered, cancelled, out of time, or the server is gone."""
        deadline = time.monotonic() + limit
        while not waiting.answered.wait(_POLL_SECONDS):
            if cancel is not None and cancel.is_set():
                self._give_up(request_id, "cancelled")
                raise McpCancelled(mcp_cancelled_error.format(method=method))
            if time.monotonic() >= deadline:
                self._give_up(request_id, "timed out")
                raise McpTimeout(mcp_timeout_error.format(method=method, seconds=round(limit)))

    def _give_up(self, request_id: int, reason: str) -> None:
        """Tell the server a request is no longer waited for; its answer, if one still comes, is dropped."""
        try:
            self._transport.send({"jsonrpc": "2.0", "method": "notifications/cancelled",
                                  "params": {"requestId": request_id, "reason": reason}})
        except McpClosed as error:
            pybreeze_logger.debug("mcp_client.py cancellation not sent: %r", error)

    def _result(self, method: str, reply: dict | None) -> dict:
        """The result *reply* carries, or the error it is."""
        if reply is None:
            raise McpClosed
        error = reply.get("error")
        if isinstance(error, dict):
            said = redact_text(_text(error, "message"), self._profile.secrets())[:_MESSAGE_CHARACTERS]
            raise McpRemoteError(method, error.get("code"), said)
        result = reply.get("result")
        if not isinstance(result, dict):
            raise McpException(mcp_reply_error.format(method=method))
        return result

    # ------------------------------------------------------------------
    # What the server offers
    # ------------------------------------------------------------------

    def _listed(self, method: str, key: str, cancel: threading.Event | None) -> list[dict]:
        """Every record of a listing, page after page."""
        records: list[dict] = []
        cursor: str | None = None
        for _page in range(_MAX_PAGES):
            result = self.request(method, {"cursor": cursor} if cursor else None, cancel=cancel)
            records.extend(_records(result, key))
            cursor = _text(result, "nextCursor") or None
            if cursor is None:
                break
        return records

    def list_tools(self, cancel: threading.Event | None = None) -> list[McpTool]:
        """The tools the server offers."""
        tools = []
        for record in self._listed("tools/list", "tools", cancel):
            hints = record.get("annotations") if isinstance(record.get("annotations"), dict) else {}
            schema = record.get("inputSchema")
            tools.append(McpTool(
                name=_text(record, "name"), title=_text(record, "title") or _text(hints, "title"),
                description=_text(record, "description"), input_schema=schema if isinstance(schema, dict) else {},
                read_only=hints.get("readOnlyHint") is True, destructive=hints.get("destructiveHint") is True))
        return [tool for tool in tools if tool.name]

    def call_tool(self, name: str, arguments: dict, cancel: threading.Event | None = None) -> McpToolResult:
        """Call the tool *name* with *arguments*.

        :return: what it gave back; ``is_error`` when the tool ran and says it failed
        :raises McpException: when the call itself did not go through (see :meth:`request`)
        """
        result = self.request("tools/call", {"name": name, "arguments": arguments}, cancel=cancel)
        content = result.get("content")
        text = "\n".join(filter(None, (block_text(block) for block in content))) if isinstance(content, list) else ""
        return McpToolResult(text=text, is_error=result.get("isError") is True, raw=result)

    def list_resources(self, cancel: threading.Event | None = None) -> list[McpResource]:
        """The resources the server offers."""
        found = [McpResource(uri=_text(record, "uri"), name=_text(record, "name"),
                             description=_text(record, "description"), mime_type=_text(record, "mimeType"))
                 for record in self._listed("resources/list", "resources", cancel)]
        return [resource for resource in found if resource.uri]

    def read_resource(self, uri: str, cancel: threading.Event | None = None) -> str:
        """What the resource at *uri* holds, as text; what is not text is named by its kind."""
        result = self.request("resources/read", {"uri": uri}, cancel=cancel)
        return "\n".join(_text(part, "text") or f"[{_text(part, 'mimeType') or 'binary'}: {_text(part, 'uri')}]"
                         for part in _records(result, "contents"))

    def list_prompts(self, cancel: threading.Event | None = None) -> list[McpPrompt]:
        """The prompts the server offers."""
        prompts = []
        for record in self._listed("prompts/list", "prompts", cancel):
            arguments = tuple((_text(argument, "name"), _text(argument, "description"), argument.get("required") is True)
                              for argument in _records(record, "arguments") if _text(argument, "name"))
            prompts.append(McpPrompt(_text(record, "name"), _text(record, "description"), arguments))
        return [prompt for prompt in prompts if prompt.name]

    def get_prompt(self, name: str, arguments: dict[str, str], cancel: threading.Event | None = None) -> str:
        """The prompt *name* filled in with *arguments*, as text: each message under the role that says it."""
        result = self.request("prompts/get", {"name": name, "arguments": arguments}, cancel=cancel)
        return "\n\n".join(f"{_text(message, 'role')}:\n{block_text(message.get('content'))}"
                           for message in _records(result, "messages"))

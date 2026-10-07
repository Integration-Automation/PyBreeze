"""An MCP server as a process: one JSON message a line, on its standard input and output.

This is the protocol's standard transport. The client starts the server's
program, writes each message to its standard input as one line of JSON and
reads the server's messages the same way from its standard output; what the
server writes to standard error is its log.

The process is started from an argument list, never a shell line, with the
IDE's environment for a child (``utf8_subprocess_env()``) and the profile's own
variables on top. A thread reads each of its two outputs; nothing here touches
Qt, and whoever uses the transport is called back on those threads.
"""
from __future__ import annotations

import json
import subprocess  # nosec B404 — the server's command is the user's own, run as an argument list
import threading
from collections import deque
from collections.abc import Callable

from pybreeze.utils.exception.exception_tags import mcp_closed_error, mcp_start_error
from pybreeze.utils.exception.exceptions import McpException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.mcp.mcp_profile import McpServerProfile
from pybreeze.utils.mcp.mcp_redaction import redact_text
from pybreeze.utils.subprocess_util import (
    no_window_creationflags, own_session_options, stop_tree, utf8_subprocess_env,
)

# A message longer than this is not read: the server is cut off instead
MAX_MESSAGE_BYTES = 32 * 1024 * 1024
# How many of the server's last log lines are kept, to say why it stopped
_KEPT_LOG_LINES = 50
# A log line is cut to this: it is shown in a status line and written to the log
_LOG_LINE_CHARACTERS = 500
# How long a server is given to end by itself once its input is closed
_CLOSE_SECONDS = 2.0


class McpClosed(McpException):
    """The server is gone: it ended, or the connection was closed."""

    def __init__(self) -> None:
        super().__init__(mcp_closed_error)


class StdioTransport:
    """One MCP server process.

    :param profile: what starts it
    :param on_message: called with each message the server sends, on the reading thread
    :param on_closed: called once when the server's output ends, on the reading thread
    """

    def __init__(self, profile: McpServerProfile, on_message: Callable[[dict], None],
                 on_closed: Callable[[], None]) -> None:
        self._profile = profile
        self._on_message = on_message
        self._on_closed = on_closed
        self._process: subprocess.Popen | None = None
        self._writing = threading.Lock()
        self._log: deque[str] = deque(maxlen=_KEPT_LOG_LINES)

    def start(self) -> None:
        """Start the server.

        :raises McpException: when its program cannot be started; the reason is
            the failure's name, not its message, which names paths
        """
        # The protocol's messages are UTF-8. A server written in Python reads and writes its
        # standard streams in the console's code page on Windows unless it is told otherwise
        environment = {**utf8_subprocess_env(), **self._profile.environment}
        try:
            self._process = subprocess.Popen(  # nosec B603  # nosemgrep — the user's own command, as an argument list
                list(self._profile.command), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                shell=False, env=environment, cwd=self._profile.working_directory or None,
                creationflags=no_window_creationflags(), **own_session_options())
        except (OSError, ValueError) as error:
            pybreeze_logger.info("mcp_transport.py %s not started: %r", self._profile.name, error)
            raise McpException(mcp_start_error.format(reason=type(error).__name__)) from error
        threading.Thread(target=self._read_messages, name="pybreeze-mcp-read", daemon=True).start()
        threading.Thread(target=self._read_log, name="pybreeze-mcp-log", daemon=True).start()

    def _read_messages(self) -> None:
        """Hand each line of the server's output on as a message, until the output ends."""
        output = self._process.stdout
        try:
            while True:
                line = output.readline(MAX_MESSAGE_BYTES + 1)
                if not line or len(line) > MAX_MESSAGE_BYTES:
                    break
                message = self._parsed(line)
                if message is not None:
                    self._on_message(message)
        except (OSError, ValueError) as error:
            pybreeze_logger.debug("mcp_transport.py %s output closed: %r", self._profile.name, error)
        finally:
            self._on_closed()

    def _parsed(self, line: bytes) -> dict | None:
        """The message *line* writes; ``None`` for a blank line or one that is not a message, which is passed over."""
        if not line.strip():
            return None
        try:
            message = json.loads(line.decode("utf-8"))
        except (ValueError, RecursionError) as error:
            pybreeze_logger.info("mcp_transport.py %s sent a line that is not JSON: %r", self._profile.name, error)
            return None
        return message if isinstance(message, dict) else None

    def _read_log(self) -> None:
        """Keep the last lines the server wrote to standard error, its secrets taken out."""
        secrets = self._profile.secrets()
        try:
            for line in self._process.stderr:
                text = redact_text(line.decode("utf-8", "replace").rstrip(), secrets)[:_LOG_LINE_CHARACTERS]
                if text:
                    self._log.append(text)
        except (OSError, ValueError) as error:
            pybreeze_logger.debug("mcp_transport.py %s log closed: %r", self._profile.name, error)

    def log_tail(self) -> list[str]:
        """The last lines of the server's own log, oldest first."""
        return list(self._log)

    def send(self, message: dict) -> None:
        """Write *message* to the server as one line.

        :raises McpClosed: when the server is gone
        """
        line = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        process = self._process
        if process is None or process.poll() is not None:
            raise McpClosed
        try:
            with self._writing:
                process.stdin.write(line)
                process.stdin.flush()
        except (OSError, ValueError) as error:
            raise McpClosed from error

    def close(self) -> None:
        """End the server: its input is closed, and what is left of it after a moment is stopped, with what it started."""
        process = self._process
        if process is None:
            return
        try:
            with self._writing:
                process.stdin.close()
        except (OSError, ValueError) as error:
            pybreeze_logger.debug("mcp_transport.py %s input already closed: %r", self._profile.name, error)
        try:
            process.wait(_CLOSE_SECONDS)
        except subprocess.TimeoutExpired:
            stop_tree(process)

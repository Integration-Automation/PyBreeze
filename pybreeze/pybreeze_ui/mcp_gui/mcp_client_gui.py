"""A tool tab that is a client for Model Context Protocol servers.

Pick a server, connect, and the tab lists what it offers: **tools** to call,
**resources** to read, **prompts** to fill in. Every call to the server is made
on a worker thread and can be cancelled; the tab only shows what came of it.

A tool can do anything its server lets it: write files, send mail, delete
things. So a call is **asked about first**, with the tool, the server and the
arguments as they will be sent, unless the user has said that tool of that
server needs no asking. What a server says of its own tool ("changes nothing")
is shown and not relied on. A server found in the project's ``.mcp.json`` is
asked about before it is even started.

Every call is kept in the session's log as a result of an execution report
(``utils/mcp/mcp_call_log.py``), with secrets taken out, and the session can be
exported.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from importlib import metadata as installed
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFileDialog, QMessageBox, QSplitter, QTabWidget, QVBoxLayout, QWidget
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.design.panels import StatusLine
from pybreeze.pybreeze_ui.design.tokens import State
from pybreeze.pybreeze_ui.error_text import error_text
from pybreeze.pybreeze_ui.mcp_gui.mcp_panels import McpCallsPanel, McpItemsPanel, McpToolsPanel
from pybreeze.pybreeze_ui.mcp_gui.mcp_server_panel import McpServerPanel
from pybreeze.pybreeze_ui.mcp_gui.mcp_worker import McpWorker
from pybreeze.pybreeze_ui.plain_text import as_text
from pybreeze.utils.exception.exceptions import McpException
from pybreeze.utils.file_process.replace_file import replace_text
from pybreeze.utils.json_format.view_safe import dumps_for_view
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.mcp.mcp_call_log import McpCallLog
from pybreeze.utils.mcp.mcp_client import (
    McpClient, McpPrompt, McpResource, McpServerInfo, McpTool, McpToolResult,
)
from pybreeze.utils.mcp.mcp_profile import McpServerProfile


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


def _client_version() -> str:
    """The installed PyBreeze's version, told to the server; empty when it runs from a source tree."""
    try:
        return installed.version("pybreeze")
    except installed.PackageNotFoundError:
        return ""


@dataclass(frozen=True)
class _Session:
    """A connection that has opened, and what its server offers."""

    client: McpClient
    profile: McpServerProfile
    server: McpServerInfo
    tools: list[McpTool]
    resources: list[McpResource]
    prompts: list[McpPrompt]


def _opened(client: McpClient, profile: McpServerProfile) -> _Session:
    """Connect *client* and list what its server offers. Runs on a worker thread.

    :raises McpException: when the server cannot be started or does not answer;
        the server is ended before the failure is passed on
    """
    server = client.connect()
    try:
        tools = client.list_tools() if "tools" in server.capabilities else []
        resources = client.list_resources() if "resources" in server.capabilities else []
        prompts = client.list_prompts() if "prompts" in server.capabilities else []
    except McpException:
        client.close()
        raise
    return _Session(client, profile, server, tools, resources, prompts)


@dataclass(frozen=True)
class _Call:
    """A tool call on its way: what was asked, and when (by the clock, and by a timer that only goes forward)."""

    tool: str
    arguments: dict
    started: float
    timer: float


class McpClientGUI(QWidget):
    """Connect to an MCP server, see its tools, resources and prompts, and call them."""

    def __init__(self) -> None:
        super().__init__()
        self._session: _Session | None = None
        self._log: McpCallLog | None = None
        # Set while a worker is on its way: its slots clear it. Not the thread's own
        # state, which still says "running" for a moment after it has answered
        self._busy = False
        self._call: _Call | None = None
        self._cancel = threading.Event()

        self.server_panel = McpServerPanel(Path.cwd())
        self.server_panel.connect_asked.connect(self.connect_server)
        self.server_panel.disconnect_asked.connect(self.disconnect_server)
        self.tools_panel = McpToolsPanel()
        self.tools_panel.call_button.clicked.connect(self.call_tool)
        self.tools_panel.cancel_button.clicked.connect(self.cancel)
        self.resources_panel = McpItemsPanel("mcp_resources_read_button")
        self.resources_panel.action_button.clicked.connect(self.read_resource)
        self.prompts_panel = McpItemsPanel("mcp_prompts_get_button", "mcp_prompts_arguments_label")
        self.prompts_panel.action_button.clicked.connect(self.get_prompt)
        self.calls_panel = McpCallsPanel()
        self.calls_panel.export_button.clicked.connect(self.export_session)

        self.pages = QTabWidget()
        for panel, key in ((self.tools_panel, "mcp_page_tools"), (self.resources_panel, "mcp_page_resources"),
                           (self.prompts_panel, "mcp_page_prompts"), (self.calls_panel, "mcp_page_calls")):
            self.pages.addTab(panel, _word(key))
        self.status = StatusLine()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.server_panel)
        splitter.addWidget(self.pages)
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout()
        layout.addWidget(splitter, 1)
        layout.addWidget(self.status)
        self.setLayout(layout)

        if self.server_panel.load_problem:
            self.status.show_state(State.ERROR, _word("mcp_client_servers_unreadable").format(
                reason=error_text(self.server_panel.load_problem)))
        else:
            self.status.show_state(State.NEUTRAL, _word("mcp_client_not_connected"))

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def is_busy(self) -> bool:
        """Whether something has been asked of the server and has not ended yet."""
        return self._busy

    def is_connected(self) -> bool:
        """Whether a server is connected."""
        return self._session is not None and not self._session.client.closed

    def _start(self, work, on_done, waiting_text: str) -> None:
        """Run *work* on a worker thread; *on_done* gets its result, :meth:`_failed` its failure."""
        worker = McpWorker(work)
        worker.done.connect(on_done)
        worker.failed.connect(self._failed)
        self._show_busy(True)
        self.status.show_state(State.NEUTRAL, waiting_text)
        worker.start_kept()

    def _show_busy(self, busy: bool) -> None:
        self._busy = busy
        self.server_panel.setEnabled(not busy)
        self.tools_panel.set_busy(busy)
        self.resources_panel.set_busy(busy)
        self.prompts_panel.set_busy(busy)

    def cancel(self) -> None:
        """Give up what is on its way: the worker stops waiting and the server is told."""
        self._cancel.set()

    def _failed(self, error: McpException) -> None:
        """Something asked of the server did not go through: say why, and keep a tool call that failed in the log."""
        call, self._call = self._call, None
        if call is not None and self._log is not None:
            self._log.record_failure(call.tool, call.arguments, call.started, time.monotonic() - call.timer, error)
            self.calls_panel.show_results(self._log.results())
        reason = error_text(str(error))
        session = self._session
        if session is not None and session.client.closed:
            # The server went away: what it last wrote says why more often than the protocol does
            last_words = session.client.log_tail()
            if last_words:
                reason = _word("mcp_client_failed_with_log").format(reason=reason, line=last_words[-1])
            self._session = None
            self._show_offer(None)
        self._show_busy(False)
        self.status.show_state(State.ERROR, reason)

    # ------------------------------------------------------------------
    # The connection
    # ------------------------------------------------------------------

    def connect_server(self) -> bool:
        """Connect to the selected server, letting go of the one connected; return whether a connection was started."""
        chosen = self.server_panel.selected()
        if chosen is None or self._busy:
            return False
        profile, own = chosen
        if not own and not self._may_start_found(profile):
            return False
        self._let_go()
        self._show_offer(None)
        client = McpClient(profile, _client_version())
        self._start(lambda: _opened(client, profile), self._connected,
                    _word("mcp_client_connecting").format(name=profile.name))
        return True

    def _may_start_found(self, profile: McpServerProfile) -> bool:
        """Ask before a server a project's file names is started: it runs a command the user did not write."""
        word = language_wrapper.language_word_dict
        box = QMessageBox(QMessageBox.Icon.Question, word.get("mcp_found_title"), "", parent=self)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.setText(as_text(word.get("mcp_found_question").format(name=profile.name)))
        box.setInformativeText(as_text("\n".join(profile.command)))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _connected(self, session: _Session) -> None:
        self._session = session
        self._log = McpCallLog(session.profile)
        self._log.connected(session.server)
        self.calls_panel.show_results(())
        self._show_offer(session)
        self._show_busy(False)
        self.status.show_state(State.SUCCESS, _word("mcp_client_connected").format(
            server=f"{session.server.name} {session.server.version}".strip() or session.profile.name,
            tools=len(session.tools), resources=len(session.resources), prompts=len(session.prompts)))

    def _show_offer(self, session: _Session | None) -> None:
        """Show what *session*'s server offers on the pages; nothing for no session."""
        self.tools_panel.show_tools(session.tools if session is not None else [])
        self.resources_panel.show_items([
            (resource.name or resource.uri, "\n".join(filter(None, (
                resource.uri, resource.mime_type, resource.description))), resource, {})
            for resource in (session.resources if session is not None else [])])
        self.prompts_panel.show_items([
            (prompt.name, "\n".join(filter(None, (prompt.description, *(
                f"{name}: {description}" for name, description, _required in prompt.arguments)))), prompt,
             {name: "" for name, _description, required in prompt.arguments if required})
            for prompt in (session.prompts if session is not None else [])])
        self.server_panel.show_connected(session is not None)

    def _let_go(self) -> None:
        """End the connected server, if any, without waiting for it on this thread."""
        session, self._session = self._session, None
        self._cancel.set()
        if session is not None:
            threading.Thread(target=session.client.close, name="pybreeze-mcp-close", daemon=True).start()

    def disconnect_server(self) -> None:
        """Let the connected server go. The session's calls stay on their page, to be exported."""
        name = self._session.profile.name if self._session is not None else ""
        self._let_go()
        self._show_offer(None)
        if name:
            self.status.show_state(State.NEUTRAL, _word("mcp_client_disconnected").format(name=name))

    def closeEvent(self, event) -> None:
        """End the connected server with the tab."""
        self._let_go()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def call_tool(self) -> bool:
        """Call the selected tool with the arguments typed, after asking; return whether the call was sent."""
        tool = self.tools_panel.selected_tool()
        session = self._session
        if session is None or tool is None or self._busy:
            return False
        arguments = self.tools_panel.arguments()
        if arguments is None:
            self.status.show_state(State.ERROR, _word("mcp_client_arguments_not_object"))
            return False
        started = time.time()
        if tool.name not in session.profile.trusted_tools and not self._confirmed(session, tool, arguments):
            self._log.record_declined(tool.name, arguments, started)
            self.calls_panel.show_results(self._log.results())
            self.status.show_state(State.NEUTRAL, _word("mcp_client_declined").format(tool=tool.name))
            return False
        self._cancel = threading.Event()
        self._call = _Call(tool.name, arguments, started, time.monotonic())
        client, cancel, name = session.client, self._cancel, tool.name
        self._start(lambda: client.call_tool(name, arguments, cancel), self._called,
                    _word("mcp_client_calling").format(tool=name))
        return True

    def _confirmed(self, session: _Session, tool: McpTool, arguments: dict) -> bool:
        """Ask whether *tool* may be called with *arguments*; a yes with the box ticked is kept for that tool."""
        word = language_wrapper.language_word_dict
        box = QMessageBox(QMessageBox.Icon.Question, word.get("mcp_confirm_title"), "", parent=self)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.setText(as_text(word.get("mcp_confirm_question").format(tool=tool.name, server=session.profile.name)))
        box.setInformativeText(as_text("\n\n".join((
            McpToolsPanel.hint_of(tool), word.get("mcp_confirm_arguments"), dumps_for_view(arguments, indent=2)))))
        trust = QCheckBox(word.get("mcp_confirm_trust").format(tool=tool.name, server=session.profile.name))
        box.setCheckBox(trust)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        agreed = box.exec() == QMessageBox.StandardButton.Yes
        if agreed and trust.isChecked():
            trusting = self.server_panel.trust(session.profile, tool.name)
            self._session = _Session(session.client, trusting, session.server, session.tools, session.resources,
                                     session.prompts)
        return agreed

    def _called(self, result: McpToolResult) -> None:
        call, self._call = self._call, None
        took = time.monotonic() - call.timer
        self._log.record(call.tool, call.arguments, call.started, took, result)
        self.calls_panel.show_results(self._log.results())
        self.tools_panel.show_result(result.text)
        self._show_busy(False)
        if result.is_error:
            self.status.show_state(State.ERROR, _word("mcp_client_tool_failed").format(tool=call.tool))
        else:
            self.status.show_state(State.SUCCESS, _word("mcp_client_called").format(
                tool=call.tool, seconds=f"{took:.2f}"))

    # ------------------------------------------------------------------
    # Resources and prompts
    # ------------------------------------------------------------------

    def read_resource(self) -> bool:
        """Read the selected resource; return whether the reading was started."""
        resource = self.resources_panel.selected()
        if self._session is None or resource is None or self._busy:
            return False
        self._cancel = threading.Event()
        client, cancel, uri = self._session.client, self._cancel, resource.uri
        self._start(lambda: client.read_resource(uri, cancel), self._read,
                    _word("mcp_client_fetching").format(name=uri))
        return True

    def _read(self, text: str) -> None:
        self.resources_panel.show_content(text)
        self._show_busy(False)
        self.status.show_state(State.SUCCESS, _word("mcp_client_fetched"))

    def get_prompt(self) -> bool:
        """Get the selected prompt, filled in with the arguments typed; return whether it was asked for."""
        prompt = self.prompts_panel.selected()
        if self._session is None or prompt is None or self._busy:
            return False
        arguments = self.prompts_panel.arguments()
        if arguments is None:
            self.status.show_state(State.ERROR, _word("mcp_client_arguments_not_object"))
            return False
        # A prompt's arguments are texts
        texts = {name: value if isinstance(value, str) else dumps_for_view(value) for name, value in arguments.items()}
        self._cancel = threading.Event()
        client, cancel, name = self._session.client, self._cancel, prompt.name
        self._start(lambda: client.get_prompt(name, texts, cancel), self._got,
                    _word("mcp_client_fetching").format(name=name))
        return True

    def _got(self, text: str) -> None:
        self.prompts_panel.show_content(text)
        self._show_busy(False)
        self.status.show_state(State.SUCCESS, _word("mcp_client_fetched"))

    # ------------------------------------------------------------------
    # The session
    # ------------------------------------------------------------------

    def export_session(self) -> str | None:
        """Save the session's calls as an execution report (JSON); return the path, or ``None``."""
        if self._log is None:
            return None
        path, _selected = QFileDialog.getSaveFileName(
            self, _word("mcp_calls_export_title"), "mcp_session.json", _word("mcp_calls_file_filter"))
        if not path:
            return None
        try:
            replace_text(Path(path), dumps_for_view(self._log.report().to_dict(), indent=2) + "\n")
        except (OSError, UnicodeEncodeError) as error:
            pybreeze_logger.error("mcp_client_gui.py session not saved: %r", error)
            reason = error.strerror if isinstance(error, OSError) and error.strerror else type(error).__name__
            self.status.show_state(State.ERROR, _word("output_actions_save_failed_message").format(
                file=Path(path).name, error=reason))
            return None
        self.status.show_state(State.SUCCESS, _word("mcp_client_exported").format(file=Path(path).name))
        return path

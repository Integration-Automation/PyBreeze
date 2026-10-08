"""What was asked of an MCP server in a session, kept as an execution report.

Each tool call becomes one result of an :class:`ExecutionReport` whose
framework is ``mcp``: when it was made, how long it took, how it ended, what it
gave back, and the call itself beside it (``raw``). The report viewer then
shows an MCP session the way it shows a test run, and a session can be saved
and compared.

How a call ended, in the report's terms:

- **passed**: the tool ran and gave a result;
- **failed**: the tool ran and says it failed (``isError``);
- **error**: the call did not go through: no answer in time, the server
  refused it or went away;
- **skipped**: it was not made, or not waited for: the user said no when asked,
  or cancelled it.

Nothing secret is kept: arguments and results go through ``mcp_redaction``
before they are stored, with the profile's environment values as known secrets.
"""
from __future__ import annotations

from pybreeze.utils.exception.exceptions import McpException
from pybreeze.utils.execution_report.report_schema import (
    ErrorDetail, ExecutionReport, ExecutionResult, ResultKind, Status, stable_id,
)
from pybreeze.utils.mcp.mcp_client import McpCancelled, McpServerInfo, McpToolResult
from pybreeze.utils.mcp.mcp_profile import McpServerProfile
from pybreeze.utils.mcp.mcp_redaction import redact, redact_text

FRAMEWORK = "mcp"
# What kind of ending an error detail names, beside the exception's own name
DECLINED, CANCELLED, TOOL_FAILED = "declined", "cancelled", "tool"


class McpCallLog:
    """The calls of one session with one server.

    :param profile: the server; its environment values are what is taken out of everything kept
    """

    def __init__(self, profile: McpServerProfile) -> None:
        self._profile = profile
        self._server: McpServerInfo | None = None
        self._results: list[ExecutionResult] = []
        self._calls_of: dict[str, int] = {}

    def connected(self, server: McpServerInfo) -> None:
        """Note which server answered, for the report."""
        self._server = server

    def _clean(self, value: object) -> object:
        return redact(value, self._profile.secrets())

    def _add(self, tool: str, arguments: object, status: Status, timing: tuple[float, float], *,
             output: str = "", error: ErrorDetail | None = None, result: object = None) -> ExecutionResult:
        """Keep one call. *timing* is when it was made (seconds since the epoch) and how long it took."""
        occurrence = self._calls_of.get(tool, 0)
        self._calls_of[tool] = occurrence + 1
        raw: dict = {"tool": tool, "arguments": self._clean(arguments)}
        if result is not None:
            raw["result"] = self._clean(result)
        added = ExecutionResult(
            id=stable_id(FRAMEWORK, f"{self._profile.name}/{tool}", occurrence), name=tool, status=status,
            kind=ResultKind.STEP, started=timing[0], duration=timing[1],
            stdout=redact_text(output, self._profile.secrets()), error=error, raw=raw)
        self._results.append(added)
        return added

    def record(self, tool: str, arguments: dict, started: float, duration: float,
               result: McpToolResult) -> ExecutionResult:
        """Keep a call the server answered.

        :param started: when it was made, in seconds since the epoch
        :param duration: how long the answer took, in seconds
        """
        text = redact_text(result.text, self._profile.secrets())
        failed = ErrorDetail(message=text.splitlines()[0] if text else tool, kind=TOOL_FAILED) if result.is_error else None
        return self._add(tool, arguments, Status.FAILED if result.is_error else Status.PASSED,
                         (started, duration), output=result.text, error=failed, result=result.raw)

    def record_failure(self, tool: str, arguments: dict, started: float, duration: float,
                       failure: McpException) -> ExecutionResult:
        """Keep a call that did not go through: cancelled, out of time, refused, or the server gone."""
        cancelled = isinstance(failure, McpCancelled)
        message = redact_text(str(failure), self._profile.secrets())
        return self._add(
            tool, arguments, Status.SKIPPED if cancelled else Status.ERROR, (started, duration),
            error=ErrorDetail(message=message, kind=CANCELLED if cancelled else type(failure).__name__))

    def record_declined(self, tool: str, arguments: dict, started: float) -> ExecutionResult:
        """Keep a call the user was asked about and said no to: it was never sent."""
        return self._add(tool, arguments, Status.SKIPPED, (started, 0.0),
                         error=ErrorDetail(message=f"{tool} was not called", kind=DECLINED))

    def results(self) -> tuple[ExecutionResult, ...]:
        """The calls kept so far, in the order they were made."""
        return tuple(self._results)

    def report(self) -> ExecutionReport:
        """The session as an execution report."""
        started = next((result.started for result in self._results if result.started is not None), None)
        ends = [result.started + (result.duration or 0.0) for result in self._results if result.started is not None]
        server = self._server
        raw = {
            "command": [redact_text(part, self._profile.secrets()) for part in self._profile.command],
            "server": None if server is None else {
                "name": server.name, "version": server.version, "protocolVersion": server.protocol_version,
                "capabilities": sorted(server.capabilities)},
        }
        return ExecutionReport(
            framework=FRAMEWORK, results=tuple(self._results), name=self._profile.name, started=started,
            duration=max(ends) - started if started is not None and ends else None, raw=raw)

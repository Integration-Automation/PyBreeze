# 0011. An MCP client that asks before every call, over the standard transport only

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/utils/mcp/` (`mcp_profile.py`, `mcp_transport.py`, `mcp_client.py`,
  `mcp_redaction.py`, `mcp_call_log.py`), `pybreeze/pybreeze_ui/mcp_gui/`; `test_mcp_client.py`,
  `test_mcp_profile.py`, `test_mcp_client_gui.py`, `fixtures/mcp/fake_server.py`

## Context

Phase 7 of the roadmap makes the Model Context Protocol a part of the IDE: servers a user sets up
and keeps, a tab that shows a server's tools, resources and prompts, a confirmation before a call
that changes something, calls recorded in the unified execution model, secrets kept out of logs and
reports, reconnecting, time limits and cancelling, and the client logic free of Qt.

An MCP server is a program that does things on the user's machine with the user's rights. Its
tools are named and described by the server itself, and a list of servers can arrive with a
project someone else wrote. That is what the decisions below are about.

## Decision

1. **The standard transport, and only it.** A server is a process the client starts and speaks to
   on its standard input and output, one JSON message a line (`StdioTransport`). The command is an
   argument list, never a shell line, started with `utf8_subprocess_env()` and the profile's own
   variables.
2. **A profile is what starts a server, plus what the user decided about it.** Name, command,
   environment, folder, a time limit for one request, and the tools that may be called without
   being asked (`McpServerProfile`). Profiles are kept in `~/.pybreeze/mcp_servers.json`, written
   for the owner alone, in the `mcpServers` layout other clients write, so a list made elsewhere
   can be read.
3. **Every call is asked about, unless the user said that tool of that server needs no asking.**
   The question shows the tool, the server and the arguments as they will be sent, and defaults to
   No. What the server says of its own tool (`readOnlyHint`, `destructiveHint`) is shown in the
   question and decides nothing: it is the server's word about itself.
4. **A server a project brings is found, never started on being found.** `.mcp.json` in the
   project folder is listed, marked as the project's. Connecting to one asks first and shows the
   command; none of its tools is trusted whatever its file says; saving it with Edit makes it the
   user's own.
5. **The client is synchronous and thread-safe, and nothing in it is Qt.** `McpClient.request()`
   blocks its caller until the answer, the profile's time limit, a `cancel` event set from another
   thread, or the server's end; on the two middle ones the server is sent
   `notifications/cancelled` and a late answer is dropped. The tab makes each call on a worker
   thread (`McpWorker`, a `KeptThread`) and keeps its own note of whether one is in flight.
6. **A session is an execution report.** Each tool call becomes a step of an
   `ExecutionReport(framework="mcp")` (`McpCallLog`): passed, failed (the tool says so), error (no
   answer, refused, server gone) or skipped (declined, cancelled), with the call beside it. The
   session can be exported as JSON; the report viewer of Phase 8 reads the same shape.
7. **Nothing secret reaches a log or a report.** The value of anything named like a secret is
   replaced, and so is every occurrence of a value the profile gave the server as an environment
   variable: in arguments, results, error messages, the command and the server's own log lines
   (`mcp_redaction.py`). What the user is shown before a call is not redacted.
8. **Everything a server says is text.** Names, descriptions, schemas, results and errors go into
   plain-text views and escaped message boxes; a reply of the wrong shape is an error, not a crash.

## Alternatives considered

- **Asking only for tools that are not read-only.** The hint comes from the server. A server that
  lies, or is wrong, would then act without a question. The user's own "do not ask again for this
  tool" does the same job with the user deciding.
- **The HTTP transport as well.** Most HTTP servers of this kind run on the same machine, and the
  project's rule for outbound requests refuses loopback and private addresses (CLAUDE.md, Network).
  Allowing them here is a decision about that rule, not about MCP: it is left open
  (`progress.md`).
- **Offering the server sampling, roots or elicitation.** Each lets a server ask something of the
  user's side. The client declares none and refuses such requests; a ping is answered.
- **Starting a project's servers when the project is opened**, as some clients do after one
  approval. Opening a folder would then run what a file in it names.
- **An asynchronous client (`asyncio`).** The IDE's workers are `QThread`s, and a second event loop
  beside Qt's would have to be driven from one of them. A blocking call with a time limit and a
  cancel event is the same thing, said once.
- **Keeping the environment's values in the system keyring.** One more dependency for every
  platform, and the prthinker keys are already kept the way these are (a file only the owner can
  read, under a folder only the owner can enter).

## Consequences

- A further transport is a class with `start()`, `send()`, `close()` and `log_tail()`, given to
  `McpClient`.
- The tab follows `listChanged` notifications by not following them: a server whose tools change
  is reconnected to see them (`progress.md`).
- A tool's arguments are typed as a JSON object. A form made from the tool's schema is not built.
- The servers file holds secrets in the clear, as every client's does; it is the user's alone on
  POSIX, and Windows keeps the profile's own access rules.
- Protocol revisions `2025-06-18`, `2025-03-26` and `2024-11-05` are spoken; a server answering
  with another is refused and ended.
- A Python server gets `PYTHONIOENCODING=utf-8` from the IDE: without it, on Windows, it reads the
  protocol's UTF-8 in the console's code page (found with the test server: `你好` came back as
  other characters).

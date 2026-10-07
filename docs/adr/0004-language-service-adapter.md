# 0004. Language features are asked through one adapter contract, behind a guard

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/utils/language_service/service_adapter.py`,
  `test/test_utils/test_language_service.py`

## Context

AutoControl, WebRunner and LoadDensity scripts are JSON action lists whose keywords come from the
package (`AC_click_mouse`, `WR_to_url`, `LD_start_test`). What the IDE knows of those keywords is a
hand-kept list per package in `pybreeze_ui/syntax/syntax_keyword.py`, used for highlighting only:
names without parameters or documentation, and no tie to the version installed.

The roadmap's Phase 6 wants completion and diagnostics for the three, hover and go-to-definition
where the framework can tell, metadata read from the installed package, and a framework's failure
kept from crashing the IDE. It expects the frameworks to differ and answers with "a common minimum
contract + optional capabilities". One of the three, `je_auto_control`, must not be imported in the
IDE process at all: it changes the process's DPI awareness as it imports (`CLAUDE.md`,
Conventions).

## Decision

1. **One adapter contract.** A `LanguageServiceAdapter` names its framework by the package's import
   name, the same name `ExecutionReport.framework` and the executors use.
2. **A minimum, and options.** `complete()` and `diagnose()` are abstract: every adapter has them.
   `hover()` and `definition()` give nothing unless an adapter overrides them.
3. **Capabilities are asked, each time.** `capabilities()` says what the adapter can do with the
   framework as it is installed now, and is asked before every request, so an upgraded or removed
   framework is noticed without a restart.
4. **The protocol's types.** Positions, ranges, diagnostics, completion items, hovers and locations
   are shaped as the Language Server Protocol shapes them, and a position counts UTF-16 code
   units, the protocol's default and what Qt's text cursor counts in.
5. **The editor asks a guard, never an adapter.** A `LanguageService` asks only for what the
   adapter says it can do; an adapter that raises is logged and answers with nothing.
6. **Pure and synchronous.** No Qt and no framework is imported by the contract. An adapter
   answers in the call.

## Alternatives considered

- **A language server per framework, now.** Three servers, a transport and their lifecycle before
  one feature exists. The protocol's types are used so that this stays open: see the first
  consequence.
- **Keep the static keyword lists and complete from them.** No parameters, no documentation, and a
  list that describes whichever version its author last looked at.
- **Register capabilities once, when the adapter is registered.** The answer would be that of the
  framework version found at start-up.
- **Make every method optional.** An adapter that provides nothing would then be a valid one;
  completion and diagnostics are what Phase 6 starts with for all three.

## Consequences

- JEditor 1.0.29 has a language-server client of its own: `CodeEditor.start_language_server()`
  starts the server configured for a file's suffix over stdio and asks it for completion, hover,
  definition and diagnostics (`je_editor/pyside_ui/code/lsp/lsp_client.py`,
  `je_editor/utils/lsp/language_servers.py`). A server process that hosts these adapters would
  reach the editor through that client without a change to the editor core, and would be the
  separate process point 6 leaves open. Whether Phase 6 goes that way is its decision; it would
  have to settle what happens to the JSON server JEditor lists for `.json` by default, and which
  JEditor release PyBreeze then requires.
- The guard stops exceptions and nothing else. A framework that crashes or hangs the interpreter
  is not stopped by a `try`, so an adapter must not load a framework's code in the IDE process: it
  reads the metadata in a child process, as the executors run scripts, and answers from what it
  read.
- Because an adapter answers in the call, a slow one holds its caller. Whatever calls a
  `LanguageService` from the UI does so off the UI thread, or the adapter answers from memory.
- Python code that works on a line of text needs `utf16_offset()` and `index_at()` to go between a
  `Position` and a string index: they differ after the first character outside the Basic
  Multilingual Plane.
- No adapter exists yet. `syntax_keyword.py` stays as it is until Phase 6 gives its keywords
  another source (WebRunner first, then AutoControl, then LoadDensity).

# 0010. One language server for the three frameworks' action scripts, fed by the installed packages

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/utils/language_service/` (`framework_profiles.py`, `keyword_metadata.py`,
  `metadata_probe.py`, `json_scan.py`, `action_adapter.py`, `lsp_server.py`),
  `pybreeze/extend/language_server/`, `pybreeze/pybreeze_ui/tools_gui/keyword_reference_gui.py`;
  the tests named after them, and `fixtures/language_service/`

## Context

WebRunner, AutoControl and LoadDensity scripts are JSON lists of actions, `["keyword"]` or
`["keyword", arguments]`. The IDE ran them and knew nothing about what was in them: a misspelt
keyword was found when the run failed. [0004](0004-language-service-adapter.md) settled the one way
an editor asks a framework for completion and diagnostics, and left the adapters to be written.
Phase 6 of the roadmap asks for them: completion and diagnostics first, hover and go-to-definition
where the metadata permits, keywords taken from the installed packages and not copied into the UI,
capabilities that follow the installed version, a framework's failure kept away from the IDE, and
protocol tests that need no Qt. Order: WebRunner, AutoControl, LoadDensity.

Three facts shaped the answer. The three scripts have the same shape, and each framework's
executor keeps its keywords in the same place (`<package>.utils.executor.action_executor`,
`executor.event_dict`). JEditor's editor already speaks the Language Server Protocol and starts a
server chosen by a file's suffix. And the IDE must not import `je_auto_control` (CLAUDE.md,
Conventions).

## Decision

1. **One adapter, three profiles.** `ActionLanguageAdapter` answers for any framework from a
   `FrameworkProfile` (the package, its key in an object-shaped script, its executor module, its
   keywords' prefix) and that framework's metadata. A further framework is one profile.
2. **Keywords are read from the installed package, in a process of its own.**
   `metadata_probe.read_metadata()` has the interpreter that runs the scripts execute a fixed,
   standard-library-only script that imports the executor module and writes, as JSON, every name
   in `event_dict`: parameters (from `inspect.signature`), documentation, file and line, whether it
   is one of Python's built-ins, and the distribution's version. Nothing about a keyword is written
   down in PyBreeze. The child has a time limit (60 s) and runs from the interpreter's own folder.
3. **What an adapter can do is what the metadata allows.** Completion, diagnostics and hover need
   only names and signatures; go-to-definition is offered when a keyword says where it is defined.
   A keyword whose parameters Python cannot tell (some built-ins) gets no check of its arguments.
   Messages name the framework with the version that answered.
4. **A language server, started by the editor.** `lsp_server.ActionLanguageServer` answers
   `initialize`, the `textDocument/did*` notifications (publishing diagnostics), `completion`,
   `hover` and `definition`, over the protocol's framing on standard input and output.
   `python -m pybreeze.extend.language_server` is the process; PyBreeze puts its command in
   JEditor's `DEFAULT_SERVERS` for `.json`, and JEditor's own client does the rest. The server asks
   the three frameworks for their keywords as it starts, each on a thread, and checks the open
   documents again as each answers.
5. **Whose script a file is, is read from the file.** An object with a framework's key is that
   framework's; a list is the framework's whose keywords it uses most (by the metadata, or by
   prefix while there is none). Any other JSON file is nobody's and is told only whether it is
   JSON. A file that is nobody's yet is offered every framework's keywords where an action's name
   goes.
6. **Two readings of the text.** A text that is JSON is read into values that know their place
   (`json_scan.locate`), for diagnostics, hover and definition. The text before the cursor, JSON or
   not, is read into the objects and arrays still open there (`context_at`), for completion.
7. **Diagnostics are in the IDE's language.** The server is given the language as it is started
   and formats its messages from PyBreeze's dictionary for it.
8. **The same keywords, visible.** The Automation Keywords tab reads the same metadata for the same
   interpreter and shows each framework's version, what the editor offers for it, every keyword,
   or why there are none.

## Alternatives considered

- **Keyword tables kept in PyBreeze** (as `pybreeze_ui/syntax/` keeps names for highlighting). They
  are right for one version of each package and wrong, silently, for every other.
- **Importing the frameworks in the IDE** to ask them. `je_auto_control` changes the process's DPI
  awareness as it is imported, locust patches the process, and the scripts may run with another
  interpreter than the IDE's.
- **Answering inside the IDE process, without a protocol.** The contract of 0004 allows it, and the
  Automation Keywords tab does read metadata that way. But the editor is JEditor's: its completion
  popup, its diagnostics marks and its hover are driven by its language client, which speaks to a
  server process. A server is the one way in that needs nothing of JEditor changed, and it serves
  any other editor that speaks the protocol.
- **A JSON Schema per framework, generated from the metadata, for `vscode-json-language-server`.**
  It would need that server installed (Node), cannot say "did you mean", and cannot lead to a
  definition.
- **`python -m` to start the server.** `-m` puts the folder the process is started in first on the
  import path. The IDE's working folder is whatever project is open: a `pybreeze` package there
  would be imported, on opening a JSON file. The entry is started by its path instead and puts the
  folder PyBreeze is in at the head of the path. The probe runs from the interpreter's folder for
  the same reason.
- **Reading the stream on a thread** and handling messages from a queue. A thread still blocked in
  a read of standard input when the interpreter shuts down brings the process down with a fatal
  error (exit code 0xC0000005 on Windows, found while trying it). Messages are read on the main
  thread; what a worker thread finished is taken in between two messages, under one lock.
- **Unknown keywords as warnings.** A script can only name what `event_dict` holds when it runs;
  a keyword added by `add_command_to_executor` in Python code is not in a JSON script run from the
  IDE. An unknown keyword fails the run, so it is an error.

## Consequences

- The keywords follow the installation: upgrading a framework changes what is completed and
  checked at the next start of the server, with no release of PyBreeze.
- JEditor's `DEFAULT_SERVERS` is one more name PyBreeze takes from a path JEditor has not promised
  (`architecture.md` §6, `test_jeditor_contract.py`). For `.json`, PyBreeze's server replaces
  `vscode-json-language-server` there; a JSON file that is not an action script gets syntax
  diagnostics only.
- Each framework's `executor.event_dict`, its key (`webdriver_wrapper`, `auto_control`,
  `load_density`) and its prefix (`WR_`, `AC_`, `LD_`) are relied on. `test_metadata_probe.py` asks
  the installed packages and reads their executors' source for the key.
- The server reads the keywords for the interpreter known when the IDE starts; a different one
  chosen later is used by the Automation Keywords tab at once and by the server after a restart.
  A packaged build has no interpreter to run the server with and offers none (`progress.md`).
- Opening a JSON file imports the installed frameworks in a child process. That is code the user
  installed and runs anyway; it is not code from the folder being looked at.
- Measured here: the server answers `initialize` 0.3 s after it is started, and all three
  frameworks' keywords are in after 2.7 s (WebRunner 0.9 s, AutoControl 0.6 s, LoadDensity 2.5 s,
  in parallel).

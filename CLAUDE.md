# PyBreeze

Automation-first Python IDE built on PySide6 + JEditor, integrating Web/API/GUI/Load testing into a single environment.

**This file is the only home for project rules.** Anything that constrains how work is done here — conventions, security requirements, quality gates, commit policy — belongs in this file. Do not put rules in `progress.md` (it holds outstanding work only), a scratch notes file, or any other side document: a rule kept somewhere else is a rule nobody reads. Reference material that is not a rule (the architecture map, the plugin API) lives in its own file and is linked from here.

## Architecture

```
pybreeze/
├── __init__.py                  # Facade: start_editor, PyBreezeMainWindow, EDITOR_EXTEND_TAB
├── __main__.py                  # python -m pybreeze
├── pybreeze_ui/                 # Presentation layer (PySide6)
│   ├── editor_main/             # Main window (extends JEditor) + file tree context menu
│   ├── menu/                    # Menu builders: automation / install / tools (tabs and docks) / plugin,
│   │                            #   menu_utils, extend_jeditor_tab_menu (the JupyterLab tab entry)
│   ├── tools_gui/               # Tool tabs: cURL, HAR, JWT, diff, regex, headers, …
│   ├── diagram_editor/          # WYSIWYG diagram editor (QGraphicsScene, Mermaid import)
│   ├── extend_ai_gui/           # CoT code review, prompt editors, skill send
│   ├── connect_gui/             # ssh/ (terminal + SFTP tree), url/ (AI review client)
│   ├── jupyter_lab_gui/         # JupyterLab tab (QWebEngineView)
│   ├── show_code_window/        # CodeWindow — subprocess output display
│   ├── thread_keeper.py         # let_run_out: a worker QThread outlives its closed widget; if_alive: weak slots
│   ├── gui_thread_gc.py         # Garbage collected on a GUI-thread timer, never on a worker
│   ├── plain_text.py            # as_text: server/file text shown in message boxes as text, not markup
│   ├── exact_text.py            # exact_text: a text box read as typed (toPlainText changes U+00A0, U+2028)
│   ├── terminal_view.py         # Terminal output in a text view: colours, the pty size, a lone \r rewinding the line
│   ├── fixed_pitch.py           # use_fixed_pitch_font: the system's fixed-pitch font, whatever the theme names
│   ├── run_shortcut.py          # press_on_ctrl_enter: Ctrl+Enter in a panel presses its main button
│   ├── error_text.py            # error_text: a tool's English error (exception_tags) in the IDE language
│   ├── code_result_logs.py      # Only warnings and errors from loggers reach the editor's Code Result panel
│   ├── closing.py               # may_close / AskingDock: tabs and docks with unsaved work are asked first
│   ├── busy_cursor.py           # busy_cursor: the wait cursor while something slow runs on the UI thread
│   ├── dialog/                  # prthinker settings dialog
│   └── syntax/                  # Automation keyword highlighting definitions
├── extend/
│   ├── process_executor/        # Process isolation layer
│   │   ├── python_task_process_manager.py  # TaskProcessManager (subprocess + threads + QTimer)
│   │   ├── process_executor_utils.py       # build_process / start_process / run_dir_files_*
│   │   ├── file_runner_process.py          # FileRunnerProcess — plugin run configs (any language)
│   │   ├── queue_pump.py                   # Shared pipe reader + per-tick queue drain
│   │   ├── run_notice.py                   # run_notice: a run window's own [Error]/[Run]/… lines, translated
│   │   ├── test_pioneer/        # python -m test_pioneer -e <yaml> via start_module_process
│   │   └── prthinker/           # Code review via start_module_process (secrets via env)
│   ├── mail_thunder_extend/     # Post-test email report hook
│   └── prthinker_extend/        # prthinker settings + argument assembly (pure logic, no Qt)
├── extend_multi_language/       # Built-in i18n (English, Traditional Chinese)
└── utils/                       # Pure logic, no Qt — unit-testable
    ├── curl_import/ har_import/ # Request parsing + script generation
    ├── header_tools/ jwt_tools/ hash_tools/ timestamp_tools/
    ├── regex_tools/ query_tools/ url_tools/ diff_tools/
    ├── http_reference/ json_format/ response_inspector/
    ├── network/                 # url_validation (SSRF), public_http (pinned connections), http_client (capped reads)
    ├── exception/               # ITEException hierarchy
    ├── logging/ file_process/ app_dirs.py / subprocess_util.py
    ├── terminal_text.py         # Escape sequences and controls stripped from terminal output (SSH, run window)
    ├── terminal_style.py        # SGR colours and emphasis read into a TextStyle (SSH terminal)
    └── manager/package_manager/ # PackageManager — holds syntax_check_list
```

**Patterns:** Facade (`__init__.py`) · Template Method (`TaskProcessManager` lifecycle) · Observer (Queue + QTimer → UI thread) · Factory (`build_automation_menu`, `package_run_actions`, `_WIDGET_FACTORIES`) · State (`DiagramScene.ToolMode`) · Command (`DiagramSnapshotCommand`) · Plugin (auto-discovery from `jeditor_plugins/`)

**Keep `architecture_explore.md` current (mandatory).** It is the module-by-module map. Update it *in the same change* that makes it stale — whenever a module/package/class is added, removed, renamed or moved; a layer boundary, executor or threading flow changes; a menu, tool tab or dock is added or removed; persisted data or the test/CI layout changes; or one of its listed observations is fixed. Re-measure any line counts it quotes, and mirror structural edits into the tree above.

## Key types

- `PyBreezeMainWindow` — main window (extends `EditorMain`); holds `tab_widget`, `current_run_code_window`, `python_compiler`
- `TaskProcessManager` — core executor; subprocess + reader threads + QTimer UI pump
- `FileRunnerProcess` — non-Python executor driven by plugin run configs
- `CodeWindow` — output widget passed to the executors
- `EDITOR_EXTEND_TAB: dict[str, type[QWidget]]` — registry for custom tabs

## Branching & CI

- `main`: stable. On every push to `main`, the `publish` job in `stable.yml` bumps the patch version in `pyproject.toml`, uploads `pybreeze` to PyPI, then commits and tags the bump. `dev`: development. `dev.yml` runs the tests and SonarCloud and publishes nothing
- Never edit a version by hand: CI owns `pyproject.toml`'s, and `dev` is always behind `origin/main`
- `dev.toml` describes a `pybreeze_dev` package that no workflow builds; PyPI's `pybreeze_dev` stopped at the 1.0.14 it names. Whether CI should publish it or `dev.toml` should be deleted is undecided (workspace X-13). Until then, keep its `dependencies` identical to `pyproject.toml`'s, and `requirements.txt` listing the same packages (`test_requirement_pins.py` fails otherwise)
- `unit-tests` job: GitHub Actions on Windows, Python 3.10–3.14 — install deps → pytest `test/test_utils/` → `start_automation_test` → `extend_automation_test`. `setup-python` caches pip's downloads (keyed on the requirements files); versions are still resolved from PyPI on every run, so the unpinned dependencies are tested at their newest
- `sonarcloud` job: CI-based SonarQube Cloud analysis (`sonar-project.properties`), `needs: unit-tests` so it can consume the `coverage-xml` artifact that leg uploads. Automatic Analysis is off and must stay off — the two modes are mutually exclusive and the scanner refuses to run alongside it
- SonarCloud's plan for this organization exposes results for `main` and for pull requests only. An analysis pushed for another branch succeeds but its results read back 403, so `dev.yml` scans on pull requests only; `stable.yml` also scans pushes to `main`. Do not "fix" this by scanning every `dev` push — the numbers are not readable
- Every `uses:` in a workflow names a full commit SHA with its release as a comment (`actions/checkout@<sha>  # v7.0.1`), never a movable tag, and each action has one version across both files; Dependabot's `github-actions` entry bumps them on `dev`, a release no sooner than 7 days old (`cooldown`, on the `pip` entry too). Every checkout sets `persist-credentials`: `false`, except the `publish` job, which pushes the version bump. `test_workflow_actions.py` fails otherwise
- Coverage comes from the 3.12 matrix leg (`pytest --cov`), configured by `.coveragerc`. `relative_files = True` is required: the report is produced on Windows and consumed by a Linux scanner, so it must not carry machine-specific paths. `patch = subprocess` is required too: pytest-cov 7 no longer measures child processes, and without it nothing the tests run in a child interpreter (the real main window, `started_window.py`) counts. coverage traces only the threads Python starts, so `test/test_utils/conftest.py` gives every `QThread` subclass a `run` that installs its tracer on Qt's thread; without it no `QThread.run` counts as covered

## Development

```bash
python -m pip install -r dev_requirements.txt
python -m pytest test/test_utils/ -v --tb=short   # run before submitting any change
python -m pybreeze                                # launch the IDE
ruff check pybreeze/                              # before committing non-trivial changes
```

- `ruff` is pinned to 0.15 in `dev_requirements.txt`, and Dependabot proposes no 0.16: 0.16 enables 413 rules by default instead of 59, and there is no `[tool.ruff]` table. Moving to it (sorting imports, the rules the `# noqa` comments name) is a change of its own
- Unit tests: `test/test_utils/` — pure logic + headless Qt widgets (`QT_QPA_PLATFORM=offscreen`), Hypothesis property tests
- Startup tests: `test/unit_test/start_automation/` — launches the IDE in `debug_mode`, verifies startup and extend tab

## Conventions

- Python 3.10+: `X | Y` unions, `from __future__ import annotations`, `TYPE_CHECKING` guard for hint-only imports
- **Never update UI from a worker thread** — Queue + QTimer (see `TaskProcessManager`) or Qt Signal/Slot
- A slot on a thread (or any object) the widget keeps must not hold the widget: connect a bound method, or `thread_keeper.if_alive(weakref.ref(self), ...)`. A lambda capturing `self` there is a cycle through Qt that Python's collector cannot see, and the closed widget is never freed
- Automatic garbage collection is off in the IDE: `start_editor()` collects on a GUI-thread timer (`gui_thread_gc.py`), because a collection on a worker destroys Qt objects there. Never call `gc.enable()`
- Custom exceptions inherit from `ITEException`; log via `pybreeze_logger` (lazy `%s` formatting, never `print()`)
- Plugin API: `register_programming_language()` / `register_natural_language()` from `je_editor.plugins`
- A QAction built for a menu must be kept alive: store it on the main window or give it the menu as its parent. A menu does not own the actions added to it, so one held only by a local variable is deleted when the builder returns and its entry disappears
- A context menu or dialog built on each use with a parent (`QMenu(self)`, `SomeDialog(self)`) is deleted once `exec()` returns (`deleteLater()`, or `WA_DeleteOnClose` for a message box): its parent keeps it otherwise, one more per use
- A process the IDE starts gets `child_environment()` or `utf8_subprocess_env()` (`utils/subprocess_util.py`) as its `env`, never `os.environ` as it is: a variable the IDE sets for itself alone has the value `IDE_ONLY` and stays out (`LOCUST_SKIP_MONKEY_PATCH`, which a load test must not inherit). `test_child_process_environment.py` fails on a `subprocess` call without `env`
- Import `je_auto_control` only where it is used, never at the top of a module the IDE loads as it starts: it makes the process system DPI aware as it imports, which keeps Qt from making the IDE per-monitor aware. The automation packages' GUIs and the SSH client (paramiko) are likewise imported by the entry that opens them, which keeps almost two seconds off the start; `test_startup_imports.py` fails when one of them is imported as the IDE starts
- An instance attribute of a Qt class never takes the name of a member of its Qt base (`self.actions`, `self.thread`, `self.layout`, …): it hides the method from everything that calls it on the widget. `test_no_qt_member_shadowing.py` fails on one
- Delete unused code immediately — no dead imports, unreachable branches, commented-out blocks, or `_old_` prefixes
- Follow PEP 8 and standard Pythonic practice; `ruff` is the arbiter

## README & translations

**`README.md` and every translated README must stay in sync with the code.** This repo ships
`README.md`, `README/README_zh-TW.md` and `README/README_zh-CN.md`. Any user-facing change —
features, commands, CLI flags, install/setup, configuration or requirements — updates `README.md`
**and every language variant in the same commit**, structure and content aligned. Never update one
language and leave the others stale. No README-parity test guards this, so it is a manual check
across the three files above.

## Security

**General**
- Never `eval()` / `exec()` / `pickle.loads()` on untrusted data; `json.loads` for serialisation; `yaml.safe_load` only
- Never log or display secrets, tokens, passwords or API keys — API URLs may embed tokens, so treat them as credentials
- Validate all input at system boundaries (file dialogs, URL inputs, network data); never leak stack traces or paths to the user

**Network (SSRF)** — every outbound request to a user-supplied URL must first pass validation:
1. `http://` / `https://` only — block `file://`, `ftp://`, `data:`, `gopher://`
2. Resolve the hostname and reject private / loopback / link-local / reserved IPs
3. Enforce timeouts (15 s downloads, 30 s API calls) and response size caps (20 MB binary). A read timeout restarts with every byte, so a request that may run long also gets an overall bound: `public_http.overall_deadline()` around the request (image downloads: 120 s) and `read_capped_text`'s `max_seconds`
4. `allow_redirects=False`, or re-validate every redirect target. `public_session()` follows no redirect and leaves a 3xx unread whatever `allow_redirects` says (`requests` otherwise reads its whole body and parses its `Location` to prepare `Response.next`)
5. Connect only to the address checked: send through `public_session()` (requests) or `PublicHTTPHandler` / `PublicHTTPSHandler` (urllib) from `utils/network/public_http.py`, which check again as they connect and connect only to the addresses checked (each in turn), so a name that resolves differently after validation (DNS rebinding) gets nowhere private. `test_http_goes_through_public_connections.py` fails on a direct `requests.*` or `urlopen` call

Reference implementations: `utils/network/url_validation.py` (`validate_url`), `utils/network/public_http.py` (`public_session`), `utils/network/http_client.py` (`read_capped_text`), `diagram_editor/diagram_net_utils.py` (`safe_download_image`). Never pass a user URL to `urlopen()` / `requests.*` unvalidated, and never set `verify=False`.

**SSH** — never `paramiko.AutoAddPolicy()` or `WarningPolicy()`. Use `apply_host_key_policy(client, parent)` from `connect_gui/ssh/ssh_host_key_policy.py`: it shows the SHA256 fingerprint for confirmation on first connect and persists to `~/.pybreeze/ssh_known_hosts`. Every `connect()` passes `disabled_algorithms=SHA1_ALGORITHMS` (`connect_gui/ssh/ssh_connect_thread.py`): `requirements.txt` does not pin paramiko, and paramiko 4 still offers SHA-1 signatures and key exchanges (CVE-2026-44405).

**Subprocess** — always argument lists, explicit `shell=False`, `timeout` on every `subprocess.run()`. Never interpolate user input into a command string. Secrets travel as `env`, never argv (see `prthinker_setting.environment_for`). The IDE intentionally runs user-authored scripts — this hardening guards against accidental shell injection, not against malicious local files.

**JupyterLab** — the embedded server is localhost-only; the empty token and password (`--IdentityProvider.token`/`--PasswordIdentityProvider.hashed_password`, and jupyter_server 1.x's `--ServerApp.token`/`password`, which 2.x still reads) and `--ServerApp.disable_check_xsrf=True` are safe *only* because of that. Never change `--ServerApp.ip` to an externally reachable address, and never set `--ServerApp.allow_origin`: a loopback bind does not stop a browser, and with the origin open any page the user visits can drive a tokenless server. The view loads from the same origin and needs nothing relaxed, and its page (`jupyter_lab_gui/lab_page.LabPage`) keeps it there: a page elsewhere, or a link for a new tab, goes to the system's browser, `http`/`https` only. The server outlives its launcher thread, so its tab stops it on close whatever the thread's state.

**File I/O** — dialog-chosen paths are trusted; paths loaded from saved data (`.diagram.json`) are not: check `is_file()` and an extension allowlist, or run URLs through SSRF validation. Use `pathlib`, never string concatenation. Write to `~/.pybreeze/` via `app_dirs.pybreeze_data_dir()` with `encoding="utf-8"`; read through `pybreeze_data_path()`, which creates nothing. Replace a file the user would lose through `utils/file_process/replace_file.replace_text` (written beside it, then moved into place), never an in-place `write_text`; a file something else writes (an image, an SVG export) goes through `replace_written`. Resolve symlinks with `Path.resolve(strict=True)` and verify the result stays in bounds.

**Qt** — `QGraphicsTextItem` text interaction must not be on by default (double-click to edit). Text from a server or a file (a remote path, an error message, a host name, a file name) never reaches a `QMessageBox` or `QLabel` as it is: Qt reads markup in it (`Qt::AutoText`) and loads an `<img>`. Pass it through `pybreeze_ui/plain_text.as_text()`, or give the label `Qt.TextFormat.PlainText`; `test_message_boxes_show_text.py` fails on a `QMessageBox` text that is neither a literal, a word-dict entry as it is, nor `as_text(...)`. JSON (or a generated Python string) a tool shows in a text box is written with `utils/json_format/view_safe.dumps_for_view()` / `escape_for_view()`: Qt gives U+2029, U+FDD0 and U+FDD1 back as newlines and drops a lone surrogate, so Copy and Save wrote something else. Plugin loading takes only `.py` files, skipping `_`/`.` prefixes. `QWebEngineView.setUrl()` only for localhost or user-confirmed URLs; never `setHtml()` with unsanitised content.

**Secrets** — SSH passwords and passphrases stay in memory for the session only. A secret that must persist (the prthinker keys and token) is written with `replace_text(..., private=True)` under the `0700` data folder. Password fields use `QLineEdit.EchoMode.Password`.

**Dependencies** — pin exact versions in `requirements.txt` / `dev_requirements.txt`. Review any new dependency's maintenance and CVE history; prefer stdlib over a single-function package.

## Code quality gates (SonarQube / Codacy)

Per function: cyclomatic and cognitive complexity ≤ 15 (hard cap 20) · ≤ 75 lines of code · ≤ 7 parameters · ≤ 4 levels of nesting. Per file: ≤ 1000 lines. Per class: split responsibilities past ~15 instance attributes.

- Never bare `except:`; catch `Exception` only to log-and-re-raise with context. Never `pass` silently in `except` — at minimum `pybreeze_logger.debug()` with context. Use `raise ... from err` / `from None`. No `return`/`break`/`continue` inside `finally`.
- Never `assert` for runtime validation (stripped under `-O`) — test code only
- A string literal used 3+ times in a module becomes a module-level constant; an identical 6+ line block in 2+ places becomes a helper
- Magic numbers (beyond 0, 1, -1) become named constants when repeated or non-obvious
- No hardcoded IPs or hostnames outside documented loopback
- No `TODO` / `FIXME` without an issue reference (`# TODO(#123): ...`)
- Justify each `# noqa: RULE` with a short reason — never blanket-disable

## Stage commits, `progress.md`, `docs/updates/` and `architecture.md`

Workspace rule shared by every repository under `D:\Codes` (full text: `D:\Codes\CLAUDE.md`).

- **Commit at every stage.** A stage is the smallest piece of work that leaves the repository consistent and passes this project's checks (definition of done, tests, lint): one finished `progress.md` item, or one self-contained step of a larger one. Commit it before starting the next stage, before switching to another repository, and before the session ends. Do not leave work uncommitted across sessions; if a stage cannot be finished, commit the consistent part and record the rest in `progress.md`.
  - Stage only the files that stage touched (`git add <path>`, never `git add -A`), follow this file's commit-message rules, and never add AI attribution.
  - Committing is not pushing: push or open a PR only as this project's branch flow says or when asked.
- **`progress.md`** (repository root, tracked) holds outstanding work only: no finished items, no history, no rules.
- **`docs/updates/`** records finished work: one batch file per month (`YYYY-MM.md`), one entry per piece of work headed `## U-YYYYMMDD-NN · date · title · #tags`, and an index with query commands in `docs/updates/README.md`. When a `progress.md` item is done, delete it and add a `#done` entry plus its index row in the same commit.
- **`architecture.md`** (repository root) is the short architecture overview: layers, entry points, main flows, extension points, cross-project boundaries. Update it in the same commit whenever a change alters any of those. `architecture_explore.md` stays the detailed per-module map under its own rule in this file.
- **Cross-project contracts** are listed in `architecture.md` §6: what other repositories rely on here (CLI flags, import paths, constructor arguments, file layouts) and what this repository relies on elsewhere. No test here protects them, so never rename or remove one without changing its consumers in the same round, and update §6 whenever a contract is added or changes.

## Commit & PR rules

- Commit messages: short imperative sentence ("Update stable version", "Fix github actions")
- **No AI attribution (mandatory)** — never mention any AI tool, assistant, agent, model or vendor in commit messages, trailers, branch names, PR titles or bodies, issues, code comments or documentation. No `Co-Authored-By` referencing an AI, no "Generated with …" footers. PR text describes *what changed and why*, never how it was authored.
- PR target: `dev` for development work, `main` for stable releases
- **SonarCloud / Codacy findings.** When a PR or commit fails a SonarCloud or Codacy check, look the findings up through their APIs instead of guessing. The keys are in environment variables: `SonarCloudToken` (SonarCloud, e.g. `curl -s -u "$SonarCloudToken:" "https://sonarcloud.io/api/issues/search?componentKeys=<key>&pullRequest=<n>&resolved=false"`) and `CODACY_PROJECT_TOKEN` (a Codacy project token, valid only for its own project: any other repository answers "Bad credentials", so for a public repository query `https://app.codacy.com/api/v3/analysis/organizations/gh/<org>/repositories/<repo>/pull-requests/<n>/issues?status=new` without a key). **Never reveal a key or any personal credential while doing so**: refer to the variables by name only, never echo or print their values, and never put them in files, commit messages, PR or issue text, logs, or any output that leaves the machine.

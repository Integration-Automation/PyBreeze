# PyBreeze

Automation-first Python IDE built on PySide6 + JEditor, integrating Web/API/GUI/Load testing into a single environment.

**This file is the only home for project rules.** Anything that constrains how work is done here — conventions, security requirements, quality gates, commit policy — belongs in this file. Do not put rules in `progress.md` (it holds outstanding work only), a scratch notes file, or any other side document: a rule kept somewhere else is a rule nobody reads. Reference material that is not a rule (the architecture map, the plugin API) lives in its own file and is linked from here.

## Architecture

```
pybreeze/
├── __init__.py                  # Facade: start_editor, PyBreezeMainWindow, EDITOR_EXTEND_TAB
├── pybreeze_ui/                 # Presentation layer (PySide6)
│   ├── editor_main/             # Main window (extends JEditor) + file tree context menu
│   ├── menu/                    # Menu builders: automation / install / tools / plugin / dock
│   ├── tools_gui/               # Tool tabs: cURL, HAR, JWT, diff, regex, headers, …
│   ├── diagram_editor/          # WYSIWYG diagram editor (QGraphicsScene, Mermaid import)
│   ├── extend_ai_gui/           # CoT code review, prompt editors, skill send
│   ├── connect_gui/             # ssh/ (terminal + SFTP tree), url/ (AI review client)
│   ├── jupyter_lab_gui/         # JupyterLab tab (QWebEngineView)
│   ├── show_code_window/        # CodeWindow — subprocess output display
│   ├── dialog/                  # prthinker settings dialog
│   └── syntax/                  # Automation keyword highlighting definitions
├── extend/
│   ├── process_executor/        # Process isolation layer (Strategy)
│   │   ├── python_task_process_manager.py  # TaskProcessManager (subprocess + threads + QTimer)
│   │   ├── process_executor_utils.py       # build_process / start_process / run_dir_files_*
│   │   ├── file_runner_process.py          # FileRunnerProcess — plugin run configs (any language)
│   │   ├── queue_pump.py                   # Shared pipe reader + per-tick queue drain
│   │   ├── api_testka/ auto_control/ web_runner/ load_density/
│   │   ├── file_automation/ mail_thunder/  # Each delegates to build_process with its package name
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
    ├── network/                 # url_validation (SSRF), http_client (capped reads)
    ├── exception/               # ITEException hierarchy
    ├── logging/ file_process/ app_dirs.py / subprocess_util.py
    └── manager/package_manager/ # PackageManager — holds syntax_check_list
```

**Patterns:** Facade (`__init__.py`) · Strategy (automation modules → `build_process`) · Template Method (`TaskProcessManager` lifecycle) · Observer (Queue + QTimer → UI thread) · Factory (`build_automation_menu`, `_WIDGET_FACTORIES`) · State (`DiagramScene.ToolMode`) · Command (`DiagramSnapshotCommand`) · Plugin (auto-discovery from `jeditor_plugins/`)

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
- `dev.toml` describes a `pybreeze_dev` package that no workflow builds; PyPI's `pybreeze_dev` stopped at the 1.0.14 it names. Whether CI should publish it or `dev.toml` should be deleted is undecided (workspace X-13). Until then, keep its `dependencies` identical to `pyproject.toml`'s
- `unit-tests` job: GitHub Actions on Windows, Python 3.10–3.14 — install deps → pytest `test/test_utils/` → `start_automation_test` → `extend_automation_test`
- `sonarcloud` job: CI-based SonarQube Cloud analysis (`sonar-project.properties`), `needs: unit-tests` so it can consume the `coverage-xml` artifact that leg uploads. Automatic Analysis is off and must stay off — the two modes are mutually exclusive and the scanner refuses to run alongside it
- SonarCloud's plan for this organization exposes results for `main` and for pull requests only. An analysis pushed for another branch succeeds but its results read back 403, so `dev.yml` scans on pull requests only; `stable.yml` also scans pushes to `main`. Do not "fix" this by scanning every `dev` push — the numbers are not readable
- Coverage comes from the 3.12 matrix leg (`pytest --cov`), configured by `.coveragerc`. `relative_files = True` is required: the report is produced on Windows and consumed by a Linux scanner, so it must not carry machine-specific paths

## Development

```bash
python -m pip install -r dev_requirements.txt
python -m pytest test/test_utils/ -v --tb=short   # run before submitting any change
python -m pybreeze                                # launch the IDE
ruff check pybreeze/                              # before committing non-trivial changes
```

- Unit tests: `test/test_utils/` — pure logic + headless Qt widgets (`QT_QPA_PLATFORM=offscreen`), Hypothesis property tests
- Startup tests: `test/unit_test/start_automation/` — launches the IDE in `debug_mode`, verifies startup and extend tab

## Conventions

- Python 3.10+: `X | Y` unions, `from __future__ import annotations`, `TYPE_CHECKING` guard for hint-only imports
- **Never update UI from a worker thread** — Queue + QTimer (see `TaskProcessManager`) or Qt Signal/Slot
- Custom exceptions inherit from `ITEException`; log via `pybreeze_logger` (lazy `%s` formatting, never `print()`)
- Plugin API: `register_programming_language()` / `register_natural_language()` from `je_editor.plugins`
- A QAction built for a menu must be kept alive: store it on the main window or give it the menu as its parent. A menu does not own the actions added to it, so one held only by a local variable is deleted when the builder returns and its entry disappears
- Delete unused code immediately — no dead imports, unreachable branches, commented-out blocks, or `_old_` prefixes
- Follow PEP 8 and standard Pythonic practice; `ruff` is the arbiter

## Security

**General**
- Never `eval()` / `exec()` / `pickle.loads()` on untrusted data; `json.loads` for serialisation; `yaml.safe_load` only
- Never log or display secrets, tokens, passwords or API keys — API URLs may embed tokens, so treat them as credentials
- Validate all input at system boundaries (file dialogs, URL inputs, network data); never leak stack traces or paths to the user

**Network (SSRF)** — every outbound request to a user-supplied URL must first pass validation:
1. `http://` / `https://` only — block `file://`, `ftp://`, `data:`, `gopher://`
2. Resolve the hostname and reject private / loopback / link-local / reserved IPs
3. Enforce timeouts (15 s downloads, 30 s API calls) and response size caps (20 MB binary)
4. `allow_redirects=False`, or re-validate every redirect target

Reference implementations: `utils/network/url_validation.py` (`validate_url`), `utils/network/http_client.py` (`read_capped_text`), `diagram_editor/diagram_net_utils.py` (`safe_download_image`). Never pass a user URL to `urlopen()` / `requests.*` unvalidated, and never set `verify=False`.

**SSH** — never `paramiko.AutoAddPolicy()` or `WarningPolicy()`. Use `apply_host_key_policy(client, parent_widget)` from `connect_gui/ssh/ssh_host_key_policy.py`: it shows the SHA256 fingerprint for confirmation on first connect and persists to `~/.pybreeze/ssh_known_hosts`.

**Subprocess** — always argument lists, explicit `shell=False`, `timeout` on every `subprocess.run()`. Never interpolate user input into a command string. Secrets travel as `env`, never argv (see `prthinker_setting.environment_for`). The IDE intentionally runs user-authored scripts — this hardening guards against accidental shell injection, not against malicious local files.

**JupyterLab** — the embedded server is localhost-only; the empty `--ServerApp.token`/`password` and `--ServerApp.disable_check_xsrf=True` are safe *only* because of that. Never change `--ServerApp.ip` to an externally reachable address, and never set `--ServerApp.allow_origin`: a loopback bind does not stop a browser, and with the origin open any page the user visits can drive a tokenless server. The view loads from the same origin and needs nothing relaxed. The server outlives its launcher thread, so its tab stops it on close whatever the thread's state.

**File I/O** — dialog-chosen paths are trusted; paths loaded from saved data (`.diagram.json`) are not: check `is_file()` and an extension allowlist, or run URLs through SSRF validation. Use `pathlib`, never string concatenation. Write to `~/.pybreeze/` via `app_dirs.pybreeze_data_dir()` with `encoding="utf-8"`. Resolve symlinks with `Path.resolve(strict=True)` and verify the result stays in bounds.

**Qt** — `QGraphicsTextItem` text interaction must not be on by default (double-click to edit). Plugin loading takes only `.py` files, skipping `_`/`.` prefixes. `QWebEngineView.setUrl()` only for localhost or user-confirmed URLs; never `setHtml()` with unsanitised content.

**Secrets** — SSH passwords and passphrases stay in memory for the session only. Password fields use `QLineEdit.EchoMode.Password`.

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

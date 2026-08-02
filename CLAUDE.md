# PyBreeze

Automation-first Python IDE built on PySide6 + JEditor, integrating Web/API/GUI/Load testing into a single environment.

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
│   │   ├── queue_pump.py                   # Shared per-tick queue drain
│   │   ├── api_testka/ auto_control/ web_runner/ load_density/
│   │   ├── file_automation/ mail_thunder/  # Each delegates to build_process with its package name
│   │   ├── test_pioneer/        # TestPioneerProcess (custom variant)
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

- `main`: stable, publishes `pybreeze` · `dev`: development, publishes `pybreeze_dev`
- Version config: `pyproject.toml` (stable), `dev.toml` (dev) — keep both in sync when bumping
- GitHub Actions on Windows, Python 3.10–3.14: install deps → pytest `test/test_utils/` → `start_automation_test` → `extend_automation_test`

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
- A QAction built for a menu must be stored on the main window — Qt holds no reference and a GC'd action silently stops responding
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

**JupyterLab** — the embedded server is localhost-only; the empty `--ServerApp.token`/`password` and `--ServerApp.disable_check_xsrf=True` are safe *only* because of that. Never change `--ServerApp.ip` to an externally reachable address.

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

## Commit & PR rules

- Commit messages: short imperative sentence ("Update stable version", "Fix github actions")
- **No AI attribution (mandatory)** — never mention any AI tool, assistant, agent, model or vendor in commit messages, trailers, branch names, PR titles or bodies, issues, code comments or documentation. No `Co-Authored-By` referencing an AI, no "Generated with …" footers. PR text describes *what changed and why*, never how it was authored.
- PR target: `dev` for development work, `main` for stable releases

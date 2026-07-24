# PyBreeze

Automation-first Python IDE built on PySide6 + JEditor, integrating Web/API/GUI/Load testing into a single environment.

## Architecture

**Layered architecture with Facade + Strategy patterns:**

```
pybreeze/
├── __init__.py                  # Public API facade (start_editor, plugin re-exports)
├── pybreeze_ui/                 # Presentation layer (PySide6 widgets)
│   ├── editor_main/             # Main window (extends JEditor)
│   ├── menu/                    # Menu bar builders (automation, install, tools, plugins)
│   ├── connect_gui/ssh/         # SSH client widgets
│   ├── extend_ai_gui/           # LLM code review & prompt editors
│   ├── jupyter_lab_gui/         # JupyterLab tab integration
│   ├── syntax/                  # Automation keyword highlighting definitions
│   └── show_code_window/        # CodeWindow - output display widget
├── extend/
│   ├── process_executor/        # Process isolation layer (Strategy pattern)
│   │   ├── python_task_process_manager.py  # Core: TaskProcessManager (subprocess + thread + QTimer)
│   │   ├── process_executor_utils.py       # Factory functions: build_process / start_process
│   │   ├── file_runner_process.py          # FileRunnerProcess for plugin run configs
│   │   ├── api_testka/          # Each module delegates to build_process with its package name
│   │   ├── auto_control/
│   │   ├── web_runner/
│   │   ├── load_density/
│   │   ├── file_automation/
│   │   ├── mail_thunder/
│   │   └── test_pioneer/        # TestPioneerProcess (custom variant)
│   └── mail_thunder_extend/     # Post-test email report hook
├── extend_multi_language/       # Built-in i18n (English, Traditional Chinese)
└── utils/
    ├── exception/               # Exception hierarchy (ITEException base)
    ├── logging/                 # pybreeze_logger
    ├── file_process/            # File/directory utilities
    ├── json_format/             # JSON processing
    ├── network/                 # URL validation (SSRF prevention)
    └── manager/package_manager/ # PackageManager class
```

**Key design patterns in use:**
- **Facade**: `pybreeze/__init__.py` exposes `start_editor()`, `EDITOR_EXTEND_TAB`, and plugin APIs
- **Strategy**: Each automation module (`api_testka`, `web_runner`, etc.) is a strategy that delegates to `TaskProcessManager` via `build_process()`
- **Template Method**: `TaskProcessManager` defines the subprocess lifecycle (start -> read stdout/stderr threads -> QTimer poll -> drain -> exit)
- **Observer**: QTimer-based polling bridges subprocess output to PySide6 UI thread via thread-safe Queues
- **Plugin System**: Auto-discovery from `jeditor_plugins/` directory; plugins register via `register()` function

## Key types

- `PyBreezeMainWindow` — main window class (extends JEditor), holds `tab_widget` and `current_run_code_window`
- `TaskProcessManager` — core process executor; manages subprocess, I/O threads, and QTimer UI updates
- `CodeWindow` — output display widget passed to `TaskProcessManager`
- `PackageManager` — pip wrapper for installing automation modules
- `EDITOR_EXTEND_TAB: dict` — registry for custom tabs (key=name, value=QWidget subclass)

## Branching & CI

- `main` branch: stable releases, publishes `pybreeze` to PyPI
- `dev` branch: development, publishes `pybreeze_dev` to PyPI
- Version config: `pyproject.toml` (stable), `dev.toml` (dev) — keep both in sync when bumping
- CI runs on GitHub Actions (Windows, Python 3.10/3.11/3.12)
- CI steps: install deps -> pytest `test/test_utils/` -> start_automation_test -> extend_automation_test

## Development

```bash
python -m pip install -r dev_requirements.txt
python -m pytest test/test_utils/ -v --tb=short
python -m pybreeze                              # launch the IDE
```

**Testing:**
- Unit tests: `test/test_utils/` (pure logic: exceptions, JSON, logger, file utils, package manager, venv path, jupyter helpers)
- Integration tests: `test/unit_test/start_automation/` (launches IDE in debug_mode, verifies startup and extend tab)
- Run all tests before submitting changes: `python -m pytest test/test_utils/ -v`

## Conventions

- Python 3.10+ — use `X | Y` union syntax, not `Union[X, Y]`
- Use `from __future__ import annotations` for deferred type evaluation
- Use `TYPE_CHECKING` guard for imports only needed by type hints (avoid circular imports)
- PySide6 threading: never update UI from worker threads — use Queue + QTimer pattern (see `TaskProcessManager`)
- Exception hierarchy: all custom exceptions inherit from `ITEException`
- Logging: use `pybreeze_logger` from `pybreeze.utils.logging.logger`
- Plugin API: `register_programming_language()` and `register_natural_language()` from `je_editor.plugins`
- Delete all unused code — do not leave dead imports, unreachable functions, commented-out blocks, or unused variables. If code is not called by any execution path, remove it entirely. No `# TODO: remove later` or `_old_` prefixes — delete immediately.

## Security

All code must follow secure-by-default principles. Review every change against the checklist below before committing.

### General rules
- Never use `eval()`, `exec()`, or `pickle.loads()` on untrusted data
- Never use `subprocess.Popen(..., shell=True)` — always pass argument lists
- Never log or display secrets, tokens, passwords, or API keys
- Use `json.loads()` / `json.dumps()` for serialisation — never pickle
- Never use `yaml.load()` — always use `yaml.safe_load()`
- Validate all user input at system boundaries (file dialogs, URL inputs, network data)
- Handle exceptions without leaking stack traces, file paths, or internal state to the user

### Network requests (SSRF prevention)
- **All** outbound HTTP requests to user-specified URLs must validate the target before connecting:
  1. Only `http://` and `https://` schemes — block `file://`, `ftp://`, `data:`, `gopher://`
  2. Resolve the hostname and check IPs against private/loopback/link-local/reserved ranges (`ipaddress.is_private`, `is_loopback`, `is_link_local`, `is_reserved`)
  3. Enforce connection timeouts (default: 15 s for downloads, 30 s for API calls)
  4. Enforce response size limits where applicable (default: 20 MB for binary downloads)
- Reference implementation: `diagram_net_utils._validate_url()` and `safe_download_image()`
- For API-style requests (`requests.get/post`): create or reuse a URL validation helper that performs scheme + IP checks, then call it before every `requests.*` call
- Disable automatic redirect following (`allow_redirects=False`) or re-validate the redirect target to prevent redirect-based SSRF
- Never pass user-supplied URLs directly to `urlopen()` or `requests.*` without validation

### Network requests (TLS / SSH)
- All HTTPS requests must use default TLS verification — never set `verify=False`
- SSH connections: never use `paramiko.AutoAddPolicy()` or `paramiko.WarningPolicy()` — both silently accept unknown host keys and are vulnerable to MITM. Use `InteractiveHostKeyPolicy` from `pybreeze.pybreeze_ui.connect_gui.ssh.ssh_host_key_policy` (via `apply_host_key_policy(client, parent_widget)`), which prompts the user with the SHA256 fingerprint on first connection and persists confirmed keys to `~/.pybreeze/ssh_known_hosts`

### Subprocess execution
- Always pass argument lists to `subprocess.Popen` / `subprocess.run` — never `shell=True`
- Explicitly set `shell=False` for clarity in new code
- Never interpolate user input into command strings — pass as separate list elements
- Set `timeout` on all `subprocess.run()` calls to prevent hangs
- The IDE intentionally runs user-authored scripts; this is trusted local execution, not arbitrary remote code. Subprocess hardening protects against accidental shell injection, not against malicious local files

### JupyterLab integration
- The embedded JupyterLab server binds to `localhost` only and is intended for local development
- `--ServerApp.token=` and `--ServerApp.password=` are deliberately empty to enable seamless embedding — this is safe only because the server is localhost-only
- Do not change `--ServerApp.ip` to `0.0.0.0` or any externally-reachable address
- `--ServerApp.disable_check_xsrf=True` is required for the embedded QWebEngineView; do not expose the server externally with XSRF disabled

### File I/O
- File read/write paths from user dialogs (`QFileDialog`) are trusted (user-initiated)
- File paths loaded from saved data (`.diagram.json`) must be validated before access:
  - Local paths: check `path.is_file()` and verify extension is in an allowlist
  - URLs: pass through the same SSRF validation as user-entered URLs
- Never construct file paths by string concatenation with user input — use `pathlib.Path` with validation
- When writing to data directories (`.pybreeze/`), create the directory with `os.makedirs(exist_ok=True)` and always use `encoding="utf-8"`
- Never follow symlinks from untrusted sources — use `Path.resolve(strict=True)` and verify the resolved path is still within expected boundaries

### Qt / UI
- `QGraphicsTextItem` with `TextEditorInteraction` must not be enabled by default — use double-click-to-edit pattern to prevent unintended text selection issues in themed environments
- Plugin loading (`jeditor_plugins/`) uses auto-discovery — only load `.py` files, skip files starting with `_` or `.`
- `QWebEngineView.setUrl()` must only load trusted URLs (localhost or user-confirmed external URLs) — never load untrusted HTML or URLs without user consent
- Never call `QWebEngineView.setHtml()` with unsanitised content — this enables XSS within the embedded browser

### Secrets and credentials
- SSH passwords and private key passphrases are held in memory only during the session — never persist to disk or logs
- Password fields must use `QLineEdit.EchoMode.Password`
- API endpoint URLs may contain embedded tokens — treat URL strings with the same care as credentials (do not log full URLs)
- Environment variables (`PYBREEZE_LOG_MAX_BYTES`, etc.) must never contain secrets; use dedicated secure stores for credentials

### Dependency security
- Pin dependencies to exact versions in `requirements.txt` / `dev_requirements.txt`
- Do not add new dependencies without reviewing their security posture (maintained? known CVEs?)
- Avoid transitive dependency bloat — prefer stdlib solutions when the alternative is a single-function dependency

## Code quality (SonarQube / Codacy compliance)

All code must satisfy common static-analysis rules enforced by SonarQube and Codacy. Review each change against the checklist below.

### Complexity & size
- Cyclomatic complexity per function: ≤ 15 (hard cap 20). Break large branches into helpers
- Cognitive complexity per function: ≤ 15. Flatten nested `if`/`for`/`try` chains with early returns or guard clauses
- Function length: ≤ 75 lines of code (excluding docstring / blank lines). Extract helpers past that
- Parameter count: ≤ 7 per function/method. Use a dataclass or typed dict when more are needed
- Nesting depth: ≤ 4 levels of `if`/`for`/`while`/`try`. Refactor with early returns instead of pyramids
- File length: ≤ 1000 lines — split modules past that
- Class `__init__`: keep attribute count reasonable; if a class has > 15 instance attributes, split responsibilities

### Exception handling
- Never use bare `except:` — always specify exception types
- Avoid catching `Exception` or `BaseException` unless immediately re-raising or logging and re-raising with context
- Never `pass` silently inside `except` — log the error via `pybreeze_logger` (at minimum `.debug()`) with context
- Do not `return` / `break` / `continue` inside a `finally` block — it swallows exceptions
- Custom exceptions must inherit from `ITEException`; never `raise Exception(...)` directly
- Use `raise ... from err` (or `raise ... from None`) when re-raising to preserve / suppress the chain explicitly

### Pythonic correctness
- Compare with `None` using `is` / `is not`, never `==` / `!=`
- Type checks use `isinstance(obj, T)`, never `type(obj) == T`
- Never use mutable default arguments (`def f(x=[])`) — use `None` and initialise inside
- Prefer f-strings over `%` formatting or `str.format()`
- Use context managers (`with open(...) as f:`) for every file / socket / lock — never leave resources to GC
- Use `enumerate()` instead of `range(len(...))` when the index is needed alongside the item
- Use `dict.get(key, default)` instead of `key in dict and dict[key]` patterns
- Use set / dict comprehensions when clearer than manual loops; avoid comprehensions with side effects

### Naming & style (PEP 8)
- `snake_case` for functions, methods, variables, module names
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for module-level constants
- `_leading_underscore` for protected / internal members; never use `__dunder__` for custom attributes
- No single-letter names except loop indices (`i`, `j`) or conventional math (`x`, `y`)
- Do not shadow built-ins (`id`, `type`, `list`, `dict`, `input`, `file`, `open`, etc.) — rename the local variable

### Duplication & dead code
- String literal used 3+ times in the same module → extract a module-level constant
- Identical 6+ line blocks in 2+ places → extract a helper function
- Remove unused imports, unused parameters, unused local variables, unreachable code after `return` / `raise`
- No commented-out code blocks — delete them (git history is the archive)
- No `TODO` / `FIXME` / `XXX` without an accompanying issue reference (`# TODO(#123): ...`)

### Logging, printing, assertions
- Never use `print()` for diagnostics in library / runtime code — use `pybreeze_logger`
- Use lazy logging (`logger.debug("x=%s", x)`) — avoid eager f-string formatting inside log calls on hot paths
- Never use `assert` for runtime validation (Python strips assertions with `-O`). Use explicit `if … raise …` instead; `assert` is only for test code

### Hardcoded values & secrets
- No hardcoded passwords, tokens, API keys, or secrets — use env vars or a config file excluded from VCS
- No hardcoded IP addresses or hostnames outside of `localhost` / documented loopback — use config
- Magic numbers (except 0, 1, -1) should be named constants when repeated or non-obvious

### Boolean & return hygiene
- Replace `if cond: return True else: return False` with `return bool(cond)` or `return cond`
- Replace `if x == True` / `if x == False` with `if x` / `if not x`
- A function should have a consistent return type — never mix `return value` and bare `return` (returns `None`) on meaningful paths unless explicitly documented
- Do not return inside a generator function (`yield` + `return value` is a syntax pitfall)

### Imports
- One import per line for `import` statements; grouped `from x import a, b` is fine
- Order: stdlib → third-party → first-party (`pybreeze.*`) — separated by blank lines
- No wildcard imports (`from x import *`) outside of `__init__.py` re-exports
- No relative imports beyond one level (`from ..pkg import x` OK, `from ...pkg import x` avoid)

### Running the linters
- Before committing any non-trivial change, run `ruff check pybreeze/` locally to catch these rules — `ruff` covers the majority of SonarQube/Codacy Python rules
- When adding a new rule exception, justify it in a `# noqa: RULE` comment with a short reason — never blanket-disable

## Commit & PR rules

- Commit messages: short imperative sentence (e.g., "Update stable version", "Fix github actions")
- **No AI attribution (mandatory)**: Never mention any AI tool, assistant, agent, model name, or vendor in commit messages, commit trailers, branch names, PR titles, PR descriptions, issue text, code comments, or documentation
  - Do not add `Co-Authored-By` headers referencing any AI
  - No "Generated with ...", "Created by ...", or similar footers in commits or PR bodies
  - PR titles and bodies describe **what changed and why** — nothing about how the change was authored
- PR target: `dev` for development work, `main` for stable releases

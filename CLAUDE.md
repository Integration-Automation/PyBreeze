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
- Validate all user input at system boundaries (file dialogs, URL inputs, network data)

### Network requests (SSRF prevention)
- All outbound HTTP requests must go through `diagram_net_utils.safe_download_image()` or equivalent guards
- Only `http://` and `https://` schemes are allowed — block `file://`, `ftp://`, `data:`, `gopher://`
- Resolved IP addresses must be checked against private/loopback/link-local ranges (`ipaddress.is_private`, `is_loopback`, `is_link_local`, `is_reserved`)
- Enforce download size limits (default: 20 MB) and connection timeouts (default: 15s)
- Never pass user-supplied URLs directly to `urlopen()` without validation

### File I/O
- File read/write paths from user dialogs (`QFileDialog`) are trusted (user-initiated)
- File paths loaded from saved data (`.diagram.json`) must be validated before access:
  - Local paths: check `path.is_file()` and verify extension is in an allowlist
  - URLs: pass through the same SSRF validation as user-entered URLs
- Never construct file paths by string concatenation with user input — use `pathlib.Path` with validation

### Qt / UI
- `QGraphicsTextItem` with `TextEditorInteraction` must not be enabled by default — use double-click-to-edit pattern to prevent unintended text selection issues in themed environments
- Plugin loading (`jeditor_plugins/`) uses auto-discovery — only load `.py` files, skip files starting with `_` or `.`

## Commit & PR rules

- Commit messages: short imperative sentence (e.g., "Update stable version", "Fix github actions")
- Do not mention any AI tools, assistants, or co-authors in commit messages or PR descriptions
- Do not add `Co-Authored-By` headers referencing any AI
- PR target: `dev` for development work, `main` for stable releases

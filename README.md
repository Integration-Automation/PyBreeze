# PyBreeze: The Automation-First IDE

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)
[![Documentation](https://readthedocs.org/projects/pybreeze/badge/?version=latest)](https://pybreeze.readthedocs.io/en/latest/index.html)

[繁體中文](README/README_zh-TW.md) | [简体中文](README/README_zh-CN.md)

**PyBreeze** is a Python IDE purpose-built for automation engineers. Web, API, GUI and load testing live in one window, alongside the everyday HTTP tooling that automation work actually needs — no plugin hunting, no environment archaeology.

![PyBreeze main window](images/main_window.png)

*The main window: automation keywords highlighted in an APITestka action file, project tree on the left, run/format/debug/terminal panes below.*

---

## Table of Contents

- [A Tour in Screenshots](#a-tour-in-screenshots)
- [Four-Dimensional Automation](#four-dimensional-automation)
- [Built-in Tools](#built-in-tools)
- [AI-Assisted Development](#ai-assisted-development)
- [Plugin System](#plugin-system)
- [Multi-Language UI](#multi-language-ui)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Integrated Automation Modules](#integrated-automation-modules)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Testing & CI](#testing--ci)
- [Target Audience](#target-audience)
- [License](#license)

---

## A Tour in Screenshots

Three menus carry most of the IDE. **Automation** runs your scripts, **Tools** opens the utility tabs, **Install** fetches the modules.

| Automation | Tools | Install |
|---|---|---|
| ![Automation menu](images/menu_automation.png) | ![Tools menu](images/menu_tools.png) | ![Install menu](images/menu_install.png) |

Every automation run happens in its own subprocess. Output streams back into a run window while the editor stays responsive — stdout in the normal colour, stderr in red, and the process exit code at the end:

![Run output window](images/run_output_window.png)

*A real run: PyBreeze's own curl parser invoked through the IDE's file runner, generating a pytest test.*

---

## Four-Dimensional Automation

PyBreeze covers the full spectrum of automation testing out of the box:

| Dimension | Module | What it does |
|---|---|---|
| **API** | [APITestka](https://github.com/Intergration-Automation-Testing/APITestka) | RESTful testing with request builders, response analyzers, mock servers and assertions |
| **Web** | [WebRunner](https://github.com/Intergration-Automation-Testing/WebRunner) | Browser-driven interaction and testing with driver and locator integration |
| **GUI** | [AutoControl](https://github.com/Intergration-Automation-Testing/AutoControl) | Desktop automation via image recognition, coordinates, keyboard/mouse control and recording |
| **Load** | [LoadDensity](https://github.com/Intergration-Automation-Testing/LoadDensity) | High-concurrency performance testing for stability under pressure |

Plus:

- **File Automation** — file and directory operations via [automation-file](https://github.com/Intergration-Automation-Testing/AutomationFile)
- **Mail Automation** — report delivery via [MailThunder](https://github.com/Intergration-Automation-Testing/MailThunder)
- **Test Framework** — YAML-driven execution via [TestPioneer](https://github.com/Intergration-Automation-Testing/TestPioneer)

Each module gets the same menu shape: **Run** (single script, batch directory, with or without an emailed report), **Help** (docs and GitHub open as in-IDE browser tabs), **Project** (scaffold a template directory), and where available a native GUI tab.

### IDE core

- **Automation-aware syntax highlighting** — the `AT_*` / GUI / Web / Load keyword sets are registered for `.json`, and TestPioneer's schema for `.yml`, on top of JEditor's language support
- **Code editor** — built on [JEditor](https://github.com/Intergration-Automation-Testing/JEditor): tabs, project tree, format checker, debugger, terminal, variable inspector and a git client pane
- **Script execution** — single or batch; large action files are passed by path, never through the command line, so Windows' ~32 KB argv limit is never a factor
- **Report generation** — HTML / JSON / XML after a run, with optional email delivery
- **Integrated JupyterLab** — launches as a tab, installing JupyterLab into the project venv if it is missing
- **Virtual environment awareness** — `venv/` and `.venv/` are detected and used automatically

---

## Built-in Tools

### cURL Import — a copied request becomes a runnable script

Paste a `curl` command from your browser's dev tools and pick a target. The parser handles method, URL, headers, bodies, basic auth, `-G` query parameters, `-F` multipart fields (uploads become `files=open(...)`), the `--json` shortcut, `-d @file` bodies and multi-line continuations. Repeated `-H` values are combined the way HTTP combines them (`; ` for cookies, `, ` otherwise) instead of the last one silently winning. Nothing is ever executed — it is pure parsing.

| Target: pytest | Target: APITestka JSON action |
|---|---|
| ![cURL import to pytest](images/tool_curl_import.png) | ![cURL import to APITestka action](images/tool_curl_import_action.png) |

Targets: Python `requests`, a ready-to-run **pytest** test, **APITestka** (Python or a `[["AT_test_api_method", {...}]]` action list that `execute_files` runs directly), and a **LoadDensity** Locust load test. Copy the output, open it straight into an editor tab, or save it with the right extension. One click also hands the parsed URL to the URL parser/builder or the headers to the header analyzer.

### HAR Import — a whole session becomes a test suite

"Copy as cURL" captures one request; **Save all as HAR** captures the session. Open the export and every recorded call is listed with method, path, status and media type, with page furniture (CSS, images, fonts) filtered out by default.

![HAR import](images/tool_har_import.png)

Select what you want — or take everything listed — and generate one script using the same targets as the cURL importer. Repeated endpoints get numbered test names so no test silently replaces another; HTTP/2 pseudo-headers are dropped, and a `Cookie` header duplicating the recorded cookie list is removed so each value is sent once. A single selected request produces exactly what the cURL importer would. HAR is JSON, so this needs nothing beyond the standard library, and nothing is ever replayed for you.

### Response Inspector — paste a response, read everything in it

![Response Inspector](images/tool_response_inspector.png)

The status code is looked up in the HTTP reference, headers are parsed, a JSON body is pretty-printed, and any JWT anywhere in the text (an `Authorization: Bearer` header, for instance) is decoded with its timestamp claims rendered in UTC. Each finding opens in its dedicated tool tab, pre-filled.

### HTTP Header Analyzer — what a header block is actually saying

![Header Analyzer](images/tool_header_analyzer.png)

Reports names sent more than once, `Set-Cookie` entries missing `Secure` / `HttpOnly` / `SameSite`, wildcard CORS (and the wildcard-plus-credentials combination browsers reject outright), an HSTS `max-age` too short to survive a restart, CSP `unsafe-inline` / `unsafe-eval`, product banners, deprecated headers, and — for responses — the security headers that are absent. Headers carrying credentials are reported **by name only**; their values never enter the report.

### Text Diff

![Text Diff](images/tool_diff.png)

Compare two payloads — an expected vs. actual API response, say — and get a unified diff plus a one-line added/removed summary.

### The everyday utilities

Each is a tab or a dock, each has the same copy / open-in-editor / save-to-file row along the bottom.

![JWT decoder, regex tester, HTTP status reference, JSON format](images/tools_montage_a.png)

- **JWT Decoder** — header and payload as pretty JSON, with `exp` / `iat` / `nbf` / `auth_time` as readable UTC. Inspection only: the signature is never verified and the token is never trusted.
- **Regex Tester** — `IGNORECASE` / `MULTILINE` / `DOTALL` / `VERBOSE`, every match with offsets, numbered groups and named groups. An invalid pattern reports a friendly error instead of crashing.
- **HTTP Status Reference** — search the full status table (sourced from the standard library, so it stays current) by code prefix or keyword.
- **JSON Format** — pretty-print or minify, with a clear validation error when the input is not JSON.

![Timestamp converter, hash generator, query/JSON, URL builder](images/tools_montage_b.png)

- **Timestamp Converter** — a Unix epoch (seconds or milliseconds, auto-detected) or an ISO-8601 date-time in, every representation out in UTC. Deterministic and independent of the local time zone.
- **Hash Generator** — SHA-256, SHA-512, SHA-1 and MD5 at once (MD5/SHA-1 for interoperability with `usedforsecurity=False`, never for security decisions).
- **Query ⇄ JSON** — `application/x-www-form-urlencoded` to pretty JSON and back; repeated keys become arrays and vice versa.
- **URL Parser / Builder** — scheme, host, port, path, query, fragment and credentials as an editable JSON object, and back again. Brackets IPv6 literals and re-encodes query parameters for you.

### Diagram Editor — architecture diagrams without leaving the IDE

![Diagram editor with an imported Mermaid flowchart](images/diagram_editor.png)

*A Mermaid `flowchart` pasted into the importer and laid out automatically.*

A WYSIWYG `QGraphicsScene` editor: rectangle, rounded, ellipse and diamond nodes, bezier connections with edge labels, free text and images. Mermaid `flowchart` / `graph` import runs a Sugiyama-style layout (layering, crossing reduction, cross-axis alignment). Save and open as `.diagram.json`, export to PNG or SVG, with undo/redo, align, distribute, grid, snap and zoom. Images fetched from a URL are SSRF-validated and size-capped.

### SSH Client — terminal and remote file tree side by side

![SSH client](images/ssh_client.png)

Password or private-key authentication, an interactive shell with ANSI handling and keepalive, and a lazy-loading SFTP tree with create-folder / rename / delete / upload / download. Unknown host keys are **not** auto-accepted: the SHA256 fingerprint is shown for confirmation on first connection (trust on first use) and persisted to `~/.pybreeze/ssh_known_hosts`.

### And also

- **File Tree Context Menu** — right-click to create, rename, delete, copy absolute or relative paths, or reveal the item in your platform file manager. Renaming or deleting a file open in an editor tab keeps the tab in sync.
- **Package Manager** — install automation modules and build tools from the menu, output in the shell pane.
- **Integrated Documentation** — each module's docs and GitHub page open as in-IDE browser tabs.

---

## AI-Assisted Development

### AI Code Review

![AI code review client](images/ai_code_review.png)

*Shown in the pre-send state.* Send a selection to an LLM endpoint, then accept or reject the suggestion — the tally is kept in `~/.pybreeze/response_stats.txt`. The URL is SSRF-validated, redirects are not followed, and the response body is size-capped before it reaches the panel.

### Chain-of-Thought Code Review (prthinker)

Run the [prthinker](https://github.com/JE-Chen/Code-Review-Framework-Combining-Large-Language-Models-and-Chain-of-Thought-Reasoning) pipeline over the file being edited or over a Pull Request, with output streaming into a run window.

![prthinker settings](images/prthinker_setting.png)

One settings form holds the inference backend (`remote`, `local`, OpenAI-compatible, Anthropic, Gemini, Cohere, Mistral, `claude-cli`, `codex-cli`), the code host (GitHub / GitLab / Gitea) and the repository. **Keys and tokens are handed to the review as environment variables, never on a command line** where a process list would show them — and they are masked in logs.

### CoT Prompt Editor

![CoT prompt editor](images/cot_prompt_editor.png)

Create and manage the multi-step review chain: first summary → first code review → linter → code smell detector → total summary. Each step's result feeds the final summary. Files are watched, so an external edit shows up immediately.

### Skill Prompt Editor & Skill Send

| Skill prompt editor | Skill send |
|---|---|
| ![Skill prompt editor](images/skill_prompt_editor.png) | ![Skill send](images/skills_send.png) |

Define reusable skill prompts (code explanation, code review), then pick one, edit it if needed, and send it to an LLM endpoint from a dedicated tab or dock. *Both shown in the pre-send state — no endpoint was contacted for these screenshots.*

---

## Plugin System

PyBreeze inherits JEditor's plugin architecture, auto-discovered from a `jeditor_plugins/` directory in the working directory. A plugin can register:

- **Syntax highlighting** — keyword sets and rules for any language
- **UI translations** — new interface languages
- **Run configurations** — "Run with…" for interpreted (`go run main.go`) and compiled (`gcc main.c -o main` then run) languages, executed through PyBreeze's `FileRunnerProcess` with the compiled artifact cleaned up afterwards
- **Plugin Browser** — browse and install plugins from remote repositories inside the IDE

Loaded plugins appear under their own **Plugins** menu with an About entry and one run action per supported suffix. See [PLUGIN_GUIDE.md](PLUGIN_GUIDE.md) for the full API and worked examples (C, C++, Go, Java, Rust, and a French translation).

---

## Multi-Language UI

- **English** (default)
- **Traditional Chinese** (繁體中文)

Both dictionaries carry the same 571 keys, and a test enforces that parity so a new string can never land in one language only. Further languages can be added via translation plugins.

---

## Architecture

```mermaid
flowchart TB
    UI["PyBreeze UI · PySide6"]

    subgraph Editor["JEditor (Base Editor)"]
        direction LR
        E1["Code Editor + Tabs"]
        E2["File Tree"]
        E3["Syntax Highlighting"]
        E4["Plugin System"]
    end

    subgraph Automation["Automation Menu"]
        direction LR
        A1["APITestka"]
        A2["AutoControl"]
        A3["WebRunner"]
        A4["LoadDensity"]
        A5["FileAutomation"]
        A6["MailThunder"]
        A7["TestPioneer"]
    end

    subgraph Executors["Subprocess Executors · TaskProcessManager"]
        direction LR
        X1["je_api_testka"]
        X2["je_auto_control"]
        X3["je_web_runner"]
        X4["je_load_density"]
        X5["automation-file"]
        X6["je-mail-thunder"]
        X7["test_pioneer"]
    end

    subgraph Tools["Tools"]
        direction LR
        T1["SSH · paramiko"]
        T2["AI Code Review"]
        T3["Prompt Editors"]
        T4["Diagram Editor"]
        T5["HTTP Toolbelt"]
        T6["JupyterLab"]
    end

    subgraph Install["Install Menu"]
        direction LR
        I1["Module Installers"]
        I2["Build Tools"]
    end

    UI --> Editor
    UI --> Automation
    UI --> Tools
    UI --> Install

    A1 --> X1
    A2 --> X2
    A3 --> X3
    A4 --> X4
    A5 --> X5
    A6 --> X6
    A7 --> X7
```

**The editor process never runs your script.** Every automation module is launched as `python -m <package>` in the project's interpreter with `shell=False`. Two daemon threads read stdout and stderr into thread-safe queues; a 100 ms `QTimer` drains them onto the UI thread in bounded batches. A crash, a hang or an infinite print loop in a script cannot take the IDE with it.

For a module-by-module walkthrough of the codebase, see [architecture_explore.md](architecture_explore.md).

---

## Installation

### From PyPI

```bash
pip install pybreeze
```

### From source

```bash
git clone https://github.com/Intergration-Automation-Testing/AutomationEditor.git
cd AutomationEditor
pip install -r requirements.txt
```

### System requirements

- **Python**: 3.10 – 3.14
- **OS**: Windows, macOS, Linux
- **GUI**: PySide6 6.11.0 (installed automatically)

---

## Quick Start

```bash
python -m pybreeze                # command line
python exe/start_pybreeze.py      # from the exe directory
```

```python
from pybreeze import start_editor

start_editor()                              # default dark_amber theme
start_editor(theme="dark_teal.xml")         # any qt_material theme
```

Once launched:

1. **Write** an automation script in the editor — automation keywords highlight as you type
2. **Run** it from the `Automation` menu, picking the target module
3. **Watch** the output stream into the run window
4. **Generate** an HTML / JSON / XML report
5. **Send** it by email through the MailThunder integration

---

## Integrated Automation Modules

| Module | Capabilities |
|---|---|
| **APITestka** | HTTP methods, async via httpx, Flask mock servers, HTML/JSON/XML reports, scheduler triggers, socket server, JSON-schema and JSONPath assertions, SLA checks, record-replay cassettes |
| **AutoControl** | Mouse (click, drag, scroll, position), keyboard (type, hotkey, press/release), image recognition and locate-and-click, screenshots, record and playback, shell and process control |
| **WebRunner** | Browser driver integration, element location and interaction, web test scripting, reports |
| **LoadDensity** | Concurrent request simulation, performance metrics, stress scenario management, reports |
| **MailThunder** | SMTP sending, HTML report delivery, attachments, environment-variable configuration |
| **TestPioneer** | YAML test definitions, template generation, structured execution |
| **File Automation** | Automated file and directory operations, batch processing |
| **prthinker** | Chain-of-thought code review of a file or a Pull Request; settings in `~/.pybreeze/prthinker_setting.json`; installed from its own source folder via `Install ▸ Automation ▸ Install prthinker` (needs Python 3.12+) |

---

## Project Structure

```
PyBreeze/
├── pybreeze/
│   ├── __init__.py                    # Public API (start_editor, plugin re-exports)
│   ├── __main__.py                    # Entry point (python -m pybreeze)
│   ├── extend/
│   │   ├── process_executor/          # Subprocess isolation layer
│   │   │   ├── python_task_process_manager.py   # TaskProcessManager (core)
│   │   │   ├── process_executor_utils.py        # build_process / start_process
│   │   │   ├── file_runner_process.py           # Plugin run configs (any language)
│   │   │   ├── queue_pump.py                    # Shared QTimer drain
│   │   │   ├── api_testka/ auto_control/ web_runner/
│   │   │   ├── load_density/ file_automation/ mail_thunder/
│   │   │   ├── test_pioneer/ prthinker/
│   │   ├── mail_thunder_extend/       # Post-test email report hook
│   │   └── prthinker_extend/          # prthinker settings & argument assembly
│   ├── extend_multi_language/         # Built-in i18n (English, Traditional Chinese)
│   ├── pybreeze_ui/
│   │   ├── editor_main/               # Main window + file tree context menu
│   │   ├── menu/                      # Automation / install / tools / plugin menus
│   │   ├── tools_gui/                 # cURL, HAR, JWT, diff, regex, … tool tabs
│   │   ├── diagram_editor/            # WYSIWYG diagram editor
│   │   ├── extend_ai_gui/             # CoT review, prompt editors, skill send
│   │   ├── connect_gui/               # SSH terminal + SFTP tree, AI review client
│   │   ├── jupyter_lab_gui/           # JupyterLab tab
│   │   ├── show_code_window/          # CodeWindow (run output)
│   │   ├── dialog/                    # prthinker settings dialog
│   │   └── syntax/                    # Automation keyword definitions
│   └── utils/                         # curl/HAR parsing, headers, JWT, hashing,
│                                      # URL validation, logging, exceptions, …
├── exe/                               # Standalone launcher & build configs
├── docs/                              # Sphinx documentation source
├── test/                              # Unit tests (test_utils) + startup tests
├── images/                            # Screenshots
├── architecture_explore.md            # Module-by-module architecture notes
├── PLUGIN_GUIDE.md                    # Plugin development documentation
├── pyproject.toml                     # Package configuration (stable)
├── dev.toml                           # Package configuration (dev channel)
└── requirements.txt                   # Runtime dependencies
```

---

## Dependencies

### Runtime

| Package | Purpose |
|---|---|
| `PySide6` (6.11.0) | GUI framework (Qt for Python) |
| `je-editor` | Base code editor engine |
| `je_api_testka` | API testing automation |
| `je_auto_control` | GUI/desktop automation |
| `je_web_runner` | Web browser automation |
| `je_load_density` | Load and stress testing |
| `je-mail-thunder` | Email automation |
| `automation-file` | File operation automation |
| `test_pioneer` | YAML-based test framework |
| `paramiko` | SSH client support |
| `jupyterlab` | Integrated notebook environment |

### Development

`build`, `twine`, `sphinx`, `sphinx-rtd-theme`, `auto-py-to-exe`, `pytest`, `hypothesis`

---

## Testing & CI

```bash
python -m pip install -r dev_requirements.txt
python -m pytest test/test_utils/ -v --tb=short
```

- **Unit tests** — `test/test_utils/`, 60 modules covering the pure-logic layer (curl and HAR parsing, header analysis, SSRF validation, JWT, hashing, timestamps, diffing) plus headless Qt widget tests via `QT_QPA_PLATFORM=offscreen`, with Hypothesis property tests over the parsers
- **Startup tests** — `test/unit_test/start_automation/` launches the IDE in debug mode and verifies it comes up and exits cleanly
- **CI** — GitHub Actions on Windows across Python 3.10 – 3.14, on every push and PR plus a nightly run
- **Static analysis** — SonarCloud, Codacy and Bandit

---

## Target Audience

- **Python developers** — a lightweight, dedicated environment for automation scripts without the overhead of a general-purpose IDE
- **SDETs** — one tool for Web, API and performance tests maintained side by side
- **Automation beginners** — zero-config environment setup and a menu for every module
- **DevOps teams** — a place to build and debug integration suites destined for CI/CD

---

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2022 JE-Chen

---

<sub>Screenshots are rendered from the actual PyBreeze widgets on Windows 11 with the default `dark_amber` theme; the sample data in each tool is real input processed by the real code path.</sub>

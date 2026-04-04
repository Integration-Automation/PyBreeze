# PyBreeze: The Automation-First IDE

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)
[![Documentation](https://readthedocs.org/projects/pybreeze/badge/?version=latest)](https://pybreeze.readthedocs.io/en/latest/index.html)

[繁體中文](README/README_zh-TW.md) | [简体中文](README/README_zh-CN.md)

![Main GUI](images/main_gui.png)

**PyBreeze** is a Python IDE purpose-built for automation engineers. It integrates Web, API, GUI, and load testing automation into a single unified environment — no plugin hunting, no complex environment setup, just open and start automating.

---

## Table of Contents

- [Features](#features)
  - [Four-Dimensional Automation](#four-dimensional-automation)
  - [IDE Core Capabilities](#ide-core-capabilities)
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
- [Target Audience](#target-audience)
- [License](#license)

---

## Features

### Four-Dimensional Automation

PyBreeze covers the full spectrum of automation testing needs out of the box:

| Dimension | Module | Description |
|---|---|---|
| **Web Automation** | [WebRunner](https://github.com/Intergration-Automation-Testing/WebRunner) | Browser-based interaction simulation and testing with deep integration of browser drivers and element locators |
| **API Automation** | [APITestka](https://github.com/Intergration-Automation-Testing/APITestka) | RESTful API development and testing with built-in request builders, response analyzers, mock servers, and assertion verification |
| **GUI Automation** | [AutoControl](https://github.com/Intergration-Automation-Testing/AutoControl) | Desktop application automation via image recognition, coordinate-based positioning, keyboard/mouse control, and action recording |
| **Load & Stress Testing** | [LoadDensity](https://github.com/Intergration-Automation-Testing/LoadDensity) | High-concurrency performance testing engine for monitoring system stability under extreme pressure |

Additionally:

- **File Automation** — Automated file and directory operations via the [automation-file](https://github.com/Intergration-Automation-Testing/AutomationFile) module
- **Mail Automation** — Automated email sending (e.g., test report delivery) via [MailThunder](https://github.com/Intergration-Automation-Testing/MailThunder)
- **Test Framework** — Structured YAML-driven test execution via [TestPioneer](https://github.com/Intergration-Automation-Testing/TestPioneer)

### IDE Core Capabilities

PyBreeze is not just a code editor — it is a command center for the automation lifecycle:

- **Syntax Highlighting** — Built-in Python syntax highlighting with deep keyword awareness for automation libraries (APITestka, AutoControl, WebRunner, LoadDensity, etc.). Custom syntax rules can be added via plugins.
- **Code Editor** — Built on [JEditor](https://github.com/Intergration-Automation-Testing/JEditor), a full-featured editor with tab management, file tree navigation, and project workspace support.
- **Script Execution** — Run automation scripts directly from the IDE with real-time output. Supports single-script and multi-script batch execution.
- **Report Generation** — Automation modules can generate HTML, JSON, and XML reports after test execution, with optional email delivery.
- **Integrated JupyterLab** — Launch JupyterLab directly as a tab within PyBreeze for interactive notebook-based development. Auto-installs JupyterLab if not present.
- **Virtual Environment Awareness** — Automatically detects and uses the project's virtual environment (`.venv` or `venv`).

### Built-in Tools

- **SSH Client** — Full SSH terminal client with:
  - Password and private key authentication
  - Interactive command execution
  - Remote file tree viewer with CRUD operations (create folder, rename, delete, upload, download)
- **Package Manager** — Install automation modules and build tools directly from the IDE menu without leaving the editor.
- **Integrated Documentation** — Quick access to documentation and GitHub pages for each automation module directly from the menu bar.

### AI-Assisted Development

- **AI Code Review** — Send code to an LLM API endpoint for automated code review. Accept or reject suggestions directly in the IDE.
- **CoT (Chain-of-Thought) Prompt Editor** — Create and manage multi-step CoT prompts for structured code analysis, including:
  - Code review prompts
  - Code smell detection
  - Linting analysis
  - Step-by-step analysis
  - Summary generation
- **Skill Prompt Editor** — Define and manage reusable skill-based prompts (code explanation, code review templates) that can be sent to LLM APIs.

### Plugin System

PyBreeze supports an extensible plugin architecture for:

- **Syntax Highlighting** — Add syntax highlighting for any programming language via plugins
- **UI Translation** — Add new interface languages via translation plugins
- **Run Configurations** — Add "Run with..." support for compiled and interpreted languages (C, C++, Go, Java, Rust, etc.)
- **Plugin Browser** — Browse and install plugins from remote repositories directly within the IDE

Plugins are auto-discovered from the `jeditor_plugins/` directory. See [PLUGIN_GUIDE.md](PLUGIN_GUIDE.md) for full documentation.

**Bundled plugins:** C, C++, Go, Java, Rust syntax highlighting and run support; French translation.

### Multi-Language UI

The IDE interface supports multiple languages:

- **English** (default)
- **Traditional Chinese** (繁體中文)
- Additional languages can be added via plugins

---

## Architecture

![Architecture Diagram](architecture_diagram/AutomationEditorArchitectureDiagram.drawio.png)

PyBreeze follows a modular architecture:

```
PyBreeze UI (PySide6)
├── JEditor (Base Editor Engine)
│   ├── Code Editor with Tabs
│   ├── File Tree Navigation
│   ├── Syntax Highlighting Engine
│   └── Plugin System
├── Automation Menu
│   ├── APITestka ──→ APITestka Executor ──→ je_api_testka
│   ├── AutoControl ──→ AutoControl Executor ──→ je_auto_control
│   ├── WebRunner ──→ WebRunner Executor ──→ je_web_runner
│   ├── LoadDensity ──→ LoadDensity Executor ──→ je_load_density
│   ├── FileAutomation ──→ FileAutomation Executor ──→ automation-file
│   ├── MailThunder ──→ MailThunder Executor ──→ je-mail-thunder
│   └── TestPioneer ──→ TestPioneer Executor ──→ test_pioneer
├── Tools
│   ├── SSH Client (paramiko)
│   ├── AI Code Review Client
│   ├── CoT Prompt Editor
│   ├── Skill Prompt Editor
│   └── JupyterLab Integration
└── Install Menu
    ├── Automation Module Installers
    └── Build Tools Installer
```

Each automation module runs in its own subprocess via `PythonTaskProcessManager`, providing process isolation and preventing crashes from affecting the IDE.

---

## Installation

### From PyPI

```bash
pip install pybreeze
```

### From Source

```bash
git clone https://github.com/Intergration-Automation-Testing/AutomationEditor.git
cd AutomationEditor
pip install -r requirements.txt
```

### System Requirements

- **Python**: 3.10 or higher
- **OS**: Windows, macOS, Linux
- **GUI Framework**: PySide6 6.11.0 (installed automatically)

---

## Quick Start

### Run via command line

```bash
python -m pybreeze
```

### Run via Python script

```python
from pybreeze import start_editor

start_editor()
```

### Run from the exe directory

```bash
python exe/start_pybreeze.py
```

Once launched, you can:

1. **Write automation scripts** in the editor with syntax-aware auto-completion
2. **Execute scripts** via `Automation` menu — choose the target module (APITestka, WebRunner, etc.)
3. **View results** in the integrated output panel
4. **Generate reports** in HTML/JSON/XML formats
5. **Send reports** via email using MailThunder integration

---

## Integrated Automation Modules

### APITestka — API Testing

- HTTP method testing (GET, POST, PUT, DELETE, etc.)
- Async HTTP support via httpx
- Mock server creation with Flask
- Report generation (HTML, JSON, XML)
- Scheduler-based event triggering
- Socket server support

### AutoControl — GUI Automation

- Mouse control (click, drag, scroll, position tracking)
- Keyboard simulation (type, hotkey, key press/release)
- Image recognition and locate-and-click
- Screenshot capture
- Action recording and playback
- Shell command execution
- Process management

### WebRunner — Web Automation

- Browser driver integration
- Element location and interaction
- Web-based test scripting
- Report generation

### LoadDensity — Load Testing

- Concurrent request simulation
- Performance metrics collection
- Stress test scenario management
- Report generation

### MailThunder — Email Automation

- SMTP email sending
- HTML report delivery
- Attachment support
- Environment variable-based configuration

### TestPioneer — Test Framework

- YAML-based test definition
- Template generation
- Structured test execution

### File Automation

- Automated file and directory operations
- Batch file processing

---

## Project Structure

```
PyBreeze/
├── pybreeze/
│   ├── __init__.py                 # Public API (start_editor, plugin re-exports)
│   ├── __main__.py                 # Entry point (python -m pybreeze)
│   ├── extend/
│   │   ├── mail_thunder_extend/    # Email report sending after tests
│   │   ├── process_executor/       # Subprocess managers for each automation module
│   │   │   ├── api_testka/
│   │   │   ├── auto_control/
│   │   │   ├── file_automation/
│   │   │   ├── load_density/
│   │   │   ├── mail_thunder/
│   │   │   ├── test_pioneer/
│   │   │   └── web_runner/
│   │   └── process_executor/python_task_process_manager.py
│   ├── extend_multi_language/      # Built-in translations (English, Traditional Chinese)
│   ├── pybreeze_ui/
│   │   ├── editor_main/            # Main window (extends JEditor)
│   │   ├── connect_gui/ssh/        # SSH client widgets
│   │   ├── extend_ai_gui/          # AI code review & prompt editors
│   │   ├── jupyter_lab_gui/        # JupyterLab integration
│   │   ├── menu/                   # Menu bar construction
│   │   ├── syntax/                 # Automation keyword definitions
│   │   └── show_code_window/       # Code display widgets
│   └── utils/                      # Logging, exceptions, file processing, package management
├── exe/                            # Standalone launcher & build configs
├── docs/                           # Sphinx documentation source
├── test/                           # Unit tests
├── images/                         # Screenshots
├── architecture_diagram/           # Architecture diagrams
├── PLUGIN_GUIDE.md                 # Plugin development documentation
├── pyproject.toml                  # Package configuration
├── requirements.txt                # Runtime dependencies
└── dev_requirements.txt            # Development dependencies
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

`build`, `twine`, `sphinx`, `sphinx-rtd-theme`, `auto-py-to-exe`

---

## Target Audience

- **Python Developers** — A lightweight, dedicated environment for building automation scripts without the overhead of heavy general-purpose IDEs
- **SDET (Software Development Engineers in Test)** — Professionals maintaining Web, API, and Performance tests simultaneously in one tool
- **Automation Beginners** — A friendly IDE that lowers the barrier to entry for Python automation with zero-config environment setup
- **DevOps Teams** — A platform for rapidly building and debugging integration test suites within CI/CD pipelines

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

Copyright (c) 2022 JE-Chen

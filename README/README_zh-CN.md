# PyBreeze：自动化优先的 IDE

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)

[English](../README.md) | [繁體中文](README_zh-TW.md)

![主界面](../images/main_gui.png)

**PyBreeze** 是一款专为自动化工程师打造的 Python IDE。它将 Web、API、GUI 和负载测试自动化整合到单一统一环境中——无需寻找插件、无需复杂的环境配置，打开即可开始自动化。

---

## 目录

- [功能特色](#功能特色)
  - [四维自动化](#四维自动化)
  - [IDE 核心功能](#ide-核心功能)
  - [内置工具](#内置工具)
  - [AI 辅助开发](#ai-辅助开发)
  - [插件系统](#插件系统)
  - [多语言界面](#多语言界面)
- [架构设计](#架构设计)
- [安装方式](#安装方式)
- [快速开始](#快速开始)
- [集成自动化模块](#集成自动化模块)
- [项目结构](#项目结构)
- [依赖项](#依赖项)
- [目标用户](#目标用户)
- [许可证](#许可证)

---

## 功能特色

### 四维自动化

PyBreeze 开箱即用，涵盖自动化测试的完整范围：

| 维度 | 模块 | 说明 |
|---|---|---|
| **Web 自动化** | [WebRunner](https://github.com/Intergration-Automation-Testing/WebRunner) | 浏览器交互模拟与测试，深度集成浏览器驱动与元素定位器 |
| **API 自动化** | [APITestka](https://github.com/Intergration-Automation-Testing/APITestka) | RESTful API 开发与测试，内置请求构建器、响应分析器、Mock 服务器及断言验证 |
| **GUI 自动化** | [AutoControl](https://github.com/Intergration-Automation-Testing/AutoControl) | 桌面应用程序自动化，支持图像识别、坐标定位、键盘鼠标控制及动作录制 |
| **负载与压力测试** | [LoadDensity](https://github.com/Intergration-Automation-Testing/LoadDensity) | 高并发性能测试引擎，用于监控系统在极端压力下的稳定性 |

此外还包含：

- **文件自动化** — 通过 [automation-file](https://github.com/Intergration-Automation-Testing/AutomationFile) 模块实现自动化文件与目录操作
- **邮件自动化** — 通过 [MailThunder](https://github.com/Intergration-Automation-Testing/MailThunder) 实现自动化邮件发送（例如测试报告投递）
- **测试框架** — 通过 [TestPioneer](https://github.com/Intergration-Automation-Testing/TestPioneer) 实现结构化 YAML 驱动的测试执行

### IDE 核心功能

PyBreeze 不仅仅是一个代码编辑器——它是自动化生命周期的指挥中心：

- **语法高亮** — 内置 Python 语法高亮，针对自动化库（APITestka、AutoControl、WebRunner、LoadDensity 等）提供深度关键字识别。可通过插件添加自定义语法规则。
- **代码编辑器** — 基于 [JEditor](https://github.com/Intergration-Automation-Testing/JEditor) 构建，提供完整的编辑器功能，包含标签页管理、文件树导航与项目工作区支持。
- **脚本执行** — 直接在 IDE 中执行自动化脚本，并实时显示输出。支持单脚本与多脚本批量执行。
- **报告生成** — 自动化模块可在测试执行后生成 HTML、JSON 和 XML 报告，并支持可选的电子邮件投递。
- **集成 JupyterLab** — 在 PyBreeze 中直接以标签页方式启动 JupyterLab，进行交互式笔记本开发。若未安装 JupyterLab 将自动安装。
- **虚拟环境感知** — 自动检测并使用项目的虚拟环境（`.venv` 或 `venv`）。

### 内置工具

- **SSH 客户端** — 完整的 SSH 终端客户端，支持：
  - 密码与私钥认证
  - 交互式命令执行
  - 远程文件树查看器，支持 CRUD 操作（创建文件夹、重命名、删除、上传、下载）
- **包管理器** — 直接从 IDE 菜单安装自动化模块和构建工具，无需离开编辑器。
- **集成文档** — 从菜单栏快速访问每个自动化模块的文档和 GitHub 页面。

### AI 辅助开发

- **AI 代码审查** — 将代码发送到 LLM API 端点进行自动化代码审查。可直接在 IDE 中接受或拒绝建议。
- **CoT（思维链）提示词编辑器** — 创建和管理多步骤 CoT 提示词，用于结构化代码分析，包含：
  - 代码审查提示词
  - Code Smell 检测
  - 代码检查分析
  - 逐步分析
  - 摘要生成
- **Skill 提示词编辑器** — 定义和管理可重复使用的技能型提示词（代码解说、代码审查模板），可发送至 LLM API。

### 插件系统

PyBreeze 支持可扩展的插件架构，用于：

- **语法高亮** — 通过插件为任何编程语言添加语法高亮
- **UI 翻译** — 通过翻译插件添加新的界面语言
- **运行配置** — 为编译型和解释型语言添加"以...运行"支持（C、C++、Go、Java、Rust 等）
- **插件浏览器** — 直接在 IDE 中从远程仓库浏览并安装插件

插件会从 `jeditor_plugins/` 目录自动发现加载。完整文档请参阅 [PLUGIN_GUIDE.md](../PLUGIN_GUIDE.md)。

**内置插件：** C、C++、Go、Java、Rust 语法高亮与运行支持；法语翻译。

### 多语言界面

IDE 界面支持多种语言：

- **English**（英语，默认）
- **繁体中文**
- 可通过插件添加其他语言

---

## 架构设计

![架构图](../architecture_diagram/AutomationEditorArchitectureDiagram.drawio.png)

PyBreeze 采用模块化架构：

```
PyBreeze UI (PySide6)
├── JEditor（基础编辑器引擎）
│   ├── 代码编辑器与标签页
│   ├── 文件树导航
│   ├── 语法高亮引擎
│   └── 插件系统
├── 自动化菜单
│   ├── APITestka ──→ APITestka 执行器 ──→ je_api_testka
│   ├── AutoControl ──→ AutoControl 执行器 ──→ je_auto_control
│   ├── WebRunner ──→ WebRunner 执行器 ──→ je_web_runner
│   ├── LoadDensity ──→ LoadDensity 执行器 ──→ je_load_density
│   ├── FileAutomation ──→ FileAutomation 执行器 ──→ automation-file
│   ├── MailThunder ──→ MailThunder 执行器 ──→ je-mail-thunder
│   └── TestPioneer ──→ TestPioneer 执行器 ──→ test_pioneer
├── 工具
│   ├── SSH 客户端（paramiko）
│   ├── AI 代码审查客户端
│   ├── CoT 提示词编辑器
│   ├── Skill 提示词编辑器
│   └── JupyterLab 集成
└── 安装菜单
    ├── 自动化模块安装器
    └── 构建工具安装器
```

每个自动化模块都通过 `PythonTaskProcessManager` 在独立的子进程中执行，提供进程隔离，防止崩溃影响 IDE。

---

## 安装方式

### 从 PyPI 安装

```bash
pip install pybreeze
```

### 从源码安装

```bash
git clone https://github.com/Intergration-Automation-Testing/AutomationEditor.git
cd AutomationEditor
pip install -r requirements.txt
```

### 系统要求

- **Python**：3.10 或更高版本
- **操作系统**：Windows、macOS、Linux
- **GUI 框架**：PySide6 6.11.0（自动安装）

---

## 快速开始

### 通过命令行运行

```bash
python -m pybreeze
```

### 通过 Python 脚本运行

```python
from pybreeze import start_editor

start_editor()
```

### 从 exe 目录运行

```bash
python exe/start_pybreeze.py
```

启动后，您可以：

1. **编写自动化脚本** — 在编辑器中享有语法感知的自动补全
2. **执行脚本** — 通过 `自动化` 菜单，选择目标模块（APITestka、WebRunner 等）
3. **查看结果** — 在集成式输出面板中查看
4. **生成报告** — 支持 HTML/JSON/XML 格式
5. **发送报告** — 使用 MailThunder 集成功能通过电子邮件发送

---

## 集成自动化模块

### APITestka — API 测试

- HTTP 方法测试（GET、POST、PUT、DELETE 等）
- 通过 httpx 支持异步 HTTP
- 使用 Flask 创建 Mock 服务器
- 报告生成（HTML、JSON、XML）
- 基于调度器的事件触发
- Socket 服务器支持

### AutoControl — GUI 自动化

- 鼠标控制（点击、拖拽、滚动、位置追踪）
- 键盘模拟（输入、快捷键、按键按下/释放）
- 图像识别与定位点击
- 屏幕截图
- 动作录制与回放
- Shell 命令执行
- 进程管理

### WebRunner — Web 自动化

- 浏览器驱动集成
- 元素定位与交互
- 基于 Web 的测试脚本
- 报告生成

### LoadDensity — 负载测试

- 并发请求模拟
- 性能指标收集
- 压力测试场景管理
- 报告生成

### MailThunder — 邮件自动化

- SMTP 邮件发送
- HTML 报告投递
- 附件支持
- 基于环境变量的配置

### TestPioneer — 测试框架

- 基于 YAML 的测试定义
- 模板生成
- 结构化测试执行

### File Automation — 文件自动化

- 自动化文件与目录操作
- 批量文件处理

---

## 项目结构

```
PyBreeze/
├── pybreeze/
│   ├── __init__.py                 # 公开 API（start_editor、插件 re-export）
│   ├── __main__.py                 # 入口点（python -m pybreeze）
│   ├── extend/
│   │   ├── mail_thunder_extend/    # 测试后邮件报告发送
│   │   ├── process_executor/       # 各自动化模块的子进程管理器
│   │   │   ├── api_testka/
│   │   │   ├── auto_control/
│   │   │   ├── file_automation/
│   │   │   ├── load_density/
│   │   │   ├── mail_thunder/
│   │   │   ├── test_pioneer/
│   │   │   └── web_runner/
│   │   └── process_executor/python_task_process_manager.py
│   ├── extend_multi_language/      # 内置翻译（英语、繁体中文）
│   ├── pybreeze_ui/
│   │   ├── editor_main/            # 主窗口（扩展 JEditor）
│   │   ├── connect_gui/ssh/        # SSH 客户端组件
│   │   ├── extend_ai_gui/          # AI 代码审查与提示词编辑器
│   │   ├── jupyter_lab_gui/        # JupyterLab 集成
│   │   ├── menu/                   # 菜单栏构建
│   │   ├── syntax/                 # 自动化关键字定义
│   │   └── show_code_window/       # 代码显示组件
│   └── utils/                      # 日志、异常处理、文件处理、包管理
├── exe/                            # 独立启动器与构建配置
├── docs/                           # Sphinx 文档源码
├── test/                           # 单元测试
├── images/                         # 截图
├── architecture_diagram/           # 架构图
├── PLUGIN_GUIDE.md                 # 插件开发文档
├── pyproject.toml                  # 包配置
├── requirements.txt                # 运行时依赖项
└── dev_requirements.txt            # 开发依赖项
```

---

## 依赖项

### 运行时

| 包 | 用途 |
|---|---|
| `PySide6` (6.11.0) | GUI 框架（Qt for Python）|
| `je-editor` | 基础代码编辑器引擎 |
| `je_api_testka` | API 测试自动化 |
| `je_auto_control` | GUI/桌面自动化 |
| `je_web_runner` | Web 浏览器自动化 |
| `je_load_density` | 负载与压力测试 |
| `je-mail-thunder` | 邮件自动化 |
| `automation-file` | 文件操作自动化 |
| `test_pioneer` | 基于 YAML 的测试框架 |
| `paramiko` | SSH 客户端支持 |
| `jupyterlab` | 集成式笔记本环境 |

### 开发

`build`、`twine`、`sphinx`、`sphinx-rtd-theme`、`auto-py-to-exe`

---

## 目标用户

- **Python 开发者** — 一个轻量、专用的环境，用于构建自动化脚本，无需承受重量级通用 IDE 的负担
- **SDET（测试开发工程师）** — 需要在同一工具中同时维护 Web、API 和性能测试的专业人士
- **自动化初学者** — 一个友好的 IDE，通过零配置环境降低 Python 自动化的入门门槛
- **DevOps 团队** — 一个在 CI/CD 流水线中快速构建和调试集成测试套件的平台

---

## 许可证

本项目采用 MIT 许可证——详情请参阅 [LICENSE](../LICENSE) 文件。

Copyright (c) 2022 JE-Chen

# PyBreeze Architecture

> Short overview for people and agents. Per-module detail lives in [`architecture_explore.md`](architecture_explore.md).
> Last verified: 2026-09-23 against `dcd35c6` on `dev`.

## 1. Purpose

PyBreeze is an automation-first Python IDE built on JEditor. CI publishes it as `pybreeze`
(`pyproject.toml`) from `main` and as `pybreeze_dev` (`dev.toml`) from `dev`. It does not have its
own editor.
Instead it subclasses JEditor's main window and adds menus, tool tabs and docks around it:

- menus that drive the automation packages (AutoControl, WebRunner, APITestka, LoadDensity,
  FileAutomation, MailThunder, TestPioneer);
- prthinker and chain-of-thought LLM code review;
- SSH/SFTP, embedded JupyterLab and a diagram editor;
- a set of HTTP developer tools.

The central rule: the editor process never runs user scripts itself. They run in subprocesses, and
their output reaches the UI through Queue + QTimer.

## 2. Layers and directories

| Path | Responsibility |
| --- | --- |
| `pybreeze/__init__.py` | Facade: `start_editor`, `PyBreezeMainWindow`, `EDITOR_EXTEND_TAB`, re-exported JEditor plugin functions |
| `pybreeze/__main__.py`, `exe/start_pybreeze.py` | Launch scripts (module run, executable build) |
| `pybreeze/pybreeze_ui/editor_main/` | `PyBreezeMainWindow(EditorMain)`, `start_editor()`, file-tree context menu |
| `pybreeze/pybreeze_ui/menu/` | Menu builders; `build_menubar.py` is the single entry. Holds `automation_menu/` (factory, per-package menus, TestPioneer, prthinker), `install_menu/`, `tools/tools_menu.py`, `plugin_menu/`, `extend_jeditor_tab_menu/` |
| `pybreeze/pybreeze_ui/tools_gui/` | Thin tool tabs (cURL/HAR import, JWT, regex, diff, headers, …) backed by `pybreeze/utils/`; the JSON editor (`json_editor_gui.py`: a tree view, `json_tree_panel.py`, and a text view over one `JsonDocument`, with one undo history) |
| `pybreeze/pybreeze_ui/diagram_editor/` | Diagram editor (QGraphicsScene, Mermaid import, PNG/SVG export) |
| `pybreeze/pybreeze_ui/extend_ai_gui/`, `dialog/` | LLM code-review chain and prompt editors; prthinker settings dialog |
| `pybreeze/pybreeze_ui/connect_gui/` | `ssh/` terminal + SFTP tree; `url/` HTTP code-review client |
| `pybreeze/pybreeze_ui/jupyter_lab_gui/`, `show_code_window/`, `syntax/` | JupyterLab tab; `CodeWindow` subprocess output window; automation keyword highlighting |
| `pybreeze/pybreeze_ui/design/` | The design system PyBreeze's own panels are built from: `tokens.py` (gaps, text and icon sizes in ems, a state's theme colour), `flow_layout.py` (a row that wraps), `panels.py` (`Panel`, `StatusLine`, `wrapping_row`) |
| `pybreeze/pybreeze_ui/navigation/` | The navigation panel: `navigation_model.py` reads the menus and the tool table into five categories, `navigation_dock.py` shows them as a searchable tree in a dock at the left |
| `pybreeze/pybreeze_ui/mcp_gui/` | The MCP client tab: `mcp_client_gui.py` (connecting, asking before a call, cancelling, the session's log), `mcp_server_panel.py` (the user's servers and the project's), `mcp_profile_dialog.py`, `mcp_panels.py` (tools, resources, prompts, calls), `mcp_worker.py` (one blocking call on a `KeptThread`) |
| `pybreeze/pybreeze_ui/report_gui/` | The report viewer tab (`report_viewer_gui.py`): several runs as one tree, a filter bar, the selected result's details, output, attachments and own record, and export |
| `pybreeze/pybreeze_ui/thread_keeper.py` | `let_run_out()`: a worker `QThread` whose widget closed is kept until it ends instead of being waited for |
| `pybreeze/pybreeze_ui/gui_thread_gc.py` | `GuiThreadGarbageCollector`: automatic garbage collection off, collected on a GUI-thread timer instead (installed by `start_editor()`) |
| `pybreeze/extend/process_executor/` | Subprocess isolation layer: `TaskProcessManager`, `process_executor_utils.py`, `FileRunnerProcess`, `queue_pump.py`, `run_notice.py`, and `test_pioneer/` and `prthinker/` (the other automation packages run through `build_process()` from their menus) |
| `pybreeze/extend/mail_thunder_extend/`, `prthinker_extend/` | Post-test email hook; prthinker settings and argument assembly (pure logic) |
| `pybreeze/extend/language_server/` | The action language server as a process: its entry (`python -m pybreeze.extend.language_server`), the frameworks it asks for their keywords, and the command JEditor's editors start it with (`launch.py`). No Qt |
| `pybreeze/extend_multi_language/` | PyBreeze's English and Traditional Chinese strings, merged into JEditor's dictionaries; `supported_languages.py` lists the languages PyBreeze maintains, the ones it only passes on from JEditor, and the few JEditor keys it words its own way |
| `pybreeze/utils/` | Pure logic, no Qt or JEditor (`test_utils_has_no_qt.py` guards it): request parsing and codegen, the registry of what a captured request can be generated as (`import_targets/`, with the request as it is sent, `NormalizedRequest`), the schema a run of any framework is reported in and what reads and writes it (`execution_report/`: the packages' record files, JUnit XML, an HTML page, a filter, an XML reader that refuses document types), the JSON document a text editor and a visual editor both edit (`json_format/json_document.py`) and the edits of its tree by path (`json_format/json_tree_edit.py`), the one way an editor asks a framework for completion and diagnostics and what answers it for the three frameworks' action scripts (`language_service/`: profiles, the keywords read from the installed package in a child process, the adapter, and a Language Server Protocol server), an MCP client over the standard transport with its server profiles, redaction and call log (`mcp/`), HTTP tools, `network/` SSRF validation, pinned connections and capped reads, exceptions, logging, `app_dirs.py`, `subprocess_util.py`, `terminal_text.py` (terminal escapes stripped for the SSH terminal and the run window), `terminal_style.py` (SGR colours read for the SSH terminal) |
| `test/test_utils/` | Unit tests (pure logic and headless widgets). `test/unit_test/start_automation/` holds the launch tests |
| `pyproject.toml`, `dev.toml` | Stable packaging (CI bumps and publishes it) and the dev-channel packaging: the same package under the name `pybreeze_dev` (`test_requirement_pins.py` and `test_dev_toml_parity.py` keep the two in step) |
| `.github/workflows/`, `scripts/` | `dev.yml`, `stable.yml` (unit tests on a Windows matrix, the platform smoke tests on Linux and macOS, then SonarCloud and the upload to PyPI); `scripts/dev_release.py` numbers and gates the dev-channel release |
| `.github/requirements/` | `publish.in` and the lock made from it, `publish.txt`: `build`, `twine`, the build backend `setuptools` and what they need, each a version and a hash. The only thing the two publish jobs install (`test_workflow_actions.py`) |
| `docs/`, `linux_package_source/`, `architecture_diagram/` | Sphinx docs (`docs/source/`), the decision records of the shared contracts (`docs/adr/`) and the update log (`docs/updates/`); Debian package source; architecture image |

The layers are presentation (`pybreeze_ui/`), then execution (`extend/`), then foundation (`utils/`,
`extend_multi_language/`), then external subprocesses.

## 3. Entry points and public interfaces

- **CLI**: `python -m pybreeze` (`pybreeze/__main__.py`). No console script is declared. It and
  `exe/start_pybreeze.py` start the IDE only under `if __name__ == "__main__":` with
  `multiprocessing.freeze_support()`: in the packaged executable the regex tester runs patterns in
  a spawned process, which re-runs the executable. From source it runs them in a plain worker script
  (`python -I -S -c`), so a launch script without the guard is safe.
- **The action language server**: `python -m pybreeze.extend.language_server [--interpreter <python>]
  [--language <JEditor's name for it>]` speaks the Language Server Protocol on standard input and output
  for WebRunner, AutoControl and LoadDensity scripts (`.json`): `initialize`, `textDocument/didOpen`,
  `didChange`, `didSave`, `didClose` (answered with `publishDiagnostics`), `completion`, `hover`,
  `definition`, `shutdown`, `exit`, and `pybreeze/frameworks` (each framework's state, version, keyword
  count and capabilities). The IDE starts it by the path of its `__main__.py`, never with `-m`.
- **Header findings as SARIF, without the IDE**: `python -m pybreeze.utils.header_tools.header_sarif
  <file | -> [-o report.sarif] [--fail-on-warning]`. It analyses a block of HTTP headers and writes
  the findings as SARIF 2.1.0 to standard output or to `-o`; exit 0, 1 with `--fail-on-warning` and a
  warning found, 2 when the input cannot be read or the report written. It imports no Qt, and CI jobs
  of other repositories may call it: the arguments, the exit codes and the rule ids are a contract.
- **Programmatic**: `pybreeze.start_editor(debug_mode=False, theme=None, **kwargs)`. A `theme` replaces
  the one picked from UI Style (JEditor's saved `ui_style`) and is saved as it; `None` keeps the saved one.
  `debug_mode=True` adds an auto-close timer, which CI uses.
- **Main window**: `PyBreezeMainWindow` exposes `tab_widget`, `current_run_code_window` and
  `python_compiler`.
- **Custom tabs**: `EDITOR_EXTEND_TAB: dict[str, type[QWidget]]` in
  `pybreeze/pybreeze_ui/editor_main/main_ui.py`. This is PyBreeze's own registry, separate from
  JEditor's dict of the same name.
- **Plugin API (re-exported)**: `load_external_plugins`, `register_programming_language`,
  `register_natural_language`.
- **Persisted state**: `~/.pybreeze/` via `utils/app_dirs.pybreeze_data_dir()` (SSH known hosts,
  prthinker settings, edited prompts, review history, whether the navigation panel is shown (`ui_state.json`,
  `utils/ui_state.py`), and `logs/PyBreeze.log`, which
  `$PYBREEZE_LOG_FILE` can move). The editor settings inherited from JEditor
  stay in `.jeditor/` under the working directory.
- **PyPI packages**: `pybreeze` (stable) and `pybreeze_dev` (dev channel), the same import package
  `pybreeze`. Stable: a push to `main` runs the `publish` job of `stable.yml`, which bumps
  `pyproject.toml`, uploads, commits the bump and tags it. Dev: the `publish-dev` job of `dev.yml`
  runs after `unit-tests` on a push to `dev`, builds from `dev.toml` and uploads when the commit is
  still the tip of `dev` and the wheel differs from the newest published one;
  `scripts/dev_release.py` takes the version from PyPI (the newest release plus one patch), so
  nothing is committed back and the version in `dev.toml` is only a floor.
  Both jobs install only what `.github/requirements/publish.txt` locks and build with
  `python -m build --no-isolation`, so the build backend is the locked `setuptools` too.

## 4. Main flows

**Startup**

```
python -m pybreeze → start_editor() → QApplication → open_main_window() → PyBreezeMainWindow()
  → update_language_dict()             [before JEditor picks the startup language]
  → EditorMain.__init__(extend=True)   [JEditor builds the editor, loads jeditor_plugins/]
  → drop JEditor Help menu → add_menu_to_menubar()
  → syntax_extend_package() → navigation dock (build_navigation reads the menus just built)
  → EDITOR_EXTEND_TAB tabs → setup_file_tree_context_menu()
     [EditorMain.__init__ has applied the saved settings and UI Style theme: startup_setting()]
  → a theme given to start_editor(): saved as ui_style, startup_setting() again
     (none given: only the window's own style sheet is set again)
  → showMaximized() → exec() → os._exit()
```

Before PySide6 is imported, `main_ui.py` sets `LOCUST_SKIP_MONKEY_PATCH` (to `IDE_ONLY`, unless the user
set it) to keep locust's gevent patching away from Qt. The processes the IDE starts get
`subprocess_util.child_environment()`, which leaves it out: a load test needs the patching.

**Run an automation script**

```
Automation menu (automation_menu_factory.build_automation_menu; the Run entries from
package_run_actions) → build_process() / run_dir_files_with_package() (process_executor_utils.py)
  → CodeWindow + TaskProcessManager → python -m <package> --execute_str | --execute_file
  → stdout/stderr reader threads → Queue → QTimer → pump_message_queue() → CodeWindow.append_output()
  → optional report_mail_hook() → send_after_test() (mail_thunder_extend; mails this run's report on a
    thread of its own, never an earlier run's, and the run window says whether it went)
```

**Run a non-Python file through a plugin**

```
Run with… / Plugins menu (menu/plugin_menu/) → get_all_plugin_run_configs()
  → run_current_file_with() → save_current_file_for_run() [tab's own encoding and line ending]
  → FileRunnerProcess.run_file() → interpret, or compile then run → CodeWindow
```

**Complete and check an action script**

```
PyBreezeMainWindow._offer_language_server() → launch.offer_to_jeditor(): JEditor's DEFAULT_SERVERS[".json"]
editor tab holding a .json file → JEditor's LspClient → QProcess: <python> .../language_server/__main__.py
  → server_main.main(): ActionLanguageServer + lsp_server.serve() on stdin/stdout
  → one thread per framework: metadata_probe.read_metadata() → child process of the scripts'
    interpreter imports <package>.utils.executor.action_executor, writes event_dict as JSON
  → server.offer(metadata): ActionLanguageAdapter registered, open documents diagnosed again
didOpen / didChange → framework_of(text) → adapter.diagnose() → publishDiagnostics → editor marks
completion / hover / definition → json_scan (context_at, locate) → adapter → reply → editor popup
```

The Automation Keywords tab (`tools_gui/keyword_reference_gui.py`) calls the same `read_metadata()` on a
`QThread`, for the interpreter chosen in the IDE at that moment.

**Call an MCP tool**

```
MCP Client tab → Connect → McpWorker (KeptThread): McpClient.connect()
  → StdioTransport: Popen(the profile's argument list, child env + the profile's variables)
  → initialize / notifications/initialized → tools/list, resources/list, prompts/list → the pages
Call → arguments typed as a JSON object → asked about (unless that tool is trusted)
  → McpWorker: client.call_tool(name, arguments, cancel) → reply | time limit | cancel | server gone
  → McpCallLog: one ExecutionResult per call, secrets taken out → Calls page → Export Session (JSON)
```

A project's `.mcp.json` is read by `discovered_profiles()` and listed; nothing in it is started until the
user connects to it and says yes to its command.

**Open a run in the report viewer**

```
Report Viewer tab → Open… → report_files.read_report(path)
  → "<…" → safe_xml.parse_xml → JUnit (junit_xml) | <xml_data> records (record_reports)
  → "{…" → records (with the run's other file, _success ↔ _failure) | ExecutionReport.from_dict
  → .html → the report carried in the page's data block (html_report)
  → ExecutionReport → ReportFilter.of(results) → the tree (items made as they are opened) → details
Export… → EXPORT_FORMATS: JSON | JUnit XML | HTML → replace_text
MCP Client → Calls → Open in Report Viewer → ReportViewerGUI.show_report(McpCallLog.report())
```

## 5. Extension points

- **Custom tabs**: add entries to `EDITOR_EXTEND_TAB` (`pybreeze_ui/editor_main/main_ui.py`) before
  `start_editor()`, or in a file plugin's `register()`, which runs before the tabs are added. A widget
  with a `may_close()` is asked before its tab, its dock or the IDE closes (`pybreeze_ui/closing.py`);
  one whose constructor raises costs only its own tab.
- **File plugins**: `jeditor_plugins/` in the working directory, loaded by JEditor
  (`je_editor/plugins/plugin_loader.py`). `PLUGIN_RUN_CONFIG` entries appear in the Run with… and
  Plugins menus and execute via `FileRunnerProcess`. The plugin browser tab reuses JEditor's
  `PluginBrowserWidget`. See `PLUGIN_GUIDE.md`.
- **New automation package**:
  - add a menu: one `AutomationMenu(...)` passed to `build_automation_menu()`
    (`pybreeze_ui/menu/automation_menu/automation_menu_factory.py`), wired in
    `menu/build_menubar.py`; its Run entries are `package_run_actions(ui, "<label prefix>", "<package>")`,
    which start the package through `build_process()` and `run_dir_files_with_package()`, and need the four
    `<label prefix>` + `RUN_ENTRY_LABEL_SUFFIXES` keys in both language dictionaries;
  - add an installer in `menu/install_menu/automation_menu/`;
  - add keywords in `pybreeze_ui/syntax/syntax_keyword.py`.
- **New tool tab or dock**: a widget in `pybreeze_ui/tools_gui/`, its logic in `pybreeze/utils/`, and
  one `_tool(...)` line in `TOOLS` (`pybreeze_ui/menu/tools/tools_menu.py`): the Tools menu, the Dock
  menu and the navigation panel are built from that table, and its `category` says where the panel
  lists it (`tools`, `mcp` or `reports`). Its sizes come from `design/tokens.py` and a row that may be
  long is a `wrapping_row()`: `test_tools_fit_small_screens.py` holds it to 60 ems of width. Like the other tools, a box that holds code calls
  `fixed_pitch.use_fixed_pitch_font()`, and the main button gets Ctrl+Enter through
  `run_shortcut.press_on_ctrl_enter()` (`act_on_ctrl_enter()` when the input decides the action).
- **New import target** (something a cURL command or a HAR export can be generated as): one
  `TargetDescriptor` registered in `utils/import_targets/builtin_targets.py`, naming its key, its
  label's language key, the extension of its output, a generator for one request and one for
  several, and the request parts its output sends (`carries`). The cURL and HAR tabs list whatever
  `IMPORT_TARGETS` holds and know no target by name, and show under the output what the chosen
  target leaves out (`tools_gui/import_gaps.py`). A new generator reads the request through
  `normalized_request.normalize()`. `test_import_targets.py` checks `carries` against what the
  generators write, for every target and every part, and `test_import_round_trip.py` reads each
  target's output back against the fixtures in `test/test_utils/fixtures/import/`.
- **A further report format**: a function from a file's text to an `ExecutionReport`, a branch in
  `execution_report/report_files.read_report()`, and, to write it, one `ExportFormat` line in `EXPORT_FORMATS`.
  A tool that has a run of its own hands it over with `ReportViewerGUI.show_report(report)` (`docs/adr/0012`).
- **A further MCP transport**: a class with `start()`, `send(message)`, `close()` and `log_tail()` that calls
  back with each message and once when the server is gone, given to `McpClient(profile, version, transport)`
  (`utils/mcp/mcp_transport.py`, `docs/adr/0011`).
- **A further framework for the language service**: one `FrameworkProfile` in
  `utils/language_service/framework_profiles.py` (its package, its key in an object-shaped script, its
  executor module, its keywords' prefix). The adapter, the server and the Automation Keywords tab read
  `PROFILES`; the keywords themselves come from the installed package (`docs/adr/0010`).
- **A further edit in the JSON editor**: a pure function in `utils/json_format/json_tree_edit.py` (a new tree
  from the old one and a path) and a control in `tools_gui/json_tree_panel.py` that emits `edit_asked`.
  The tab makes the edit, records it for Undo and shows both views again (`docs/adr/0009`).
- **A further interface language**: its dictionary with every key, one `MaintainedLanguage` line in
  `extend_multi_language/supported_languages.py`, and its name in the three READMEs
  (`test_supported_languages.py`, `docs/adr/0008`). A language JEditor adds is placed in that file
  too, as maintained or as passed on.
- **UI strings**: add keys to both `extend_multi_language/extend_english.py` and
  `extend_traditional_chinese.py`. `test/test_utils/test_language_parity.py` enforces parity, and the
  key count in the READMEs and `architecture_explore.md` must follow (`test_the_readmes_count_the_keys_there_are`).

## 6. Cross-project boundaries

- **JEditor (upstream)**: `PyBreezeMainWindow` subclasses `je_editor.EditorMain` in extend mode
  and calls `super().__init__(debug_mode, show_system_tray_ray, extend=True)`. `pybreeze/__init__.py`
  re-exports JEditor's plugin API. Everything else PyBreeze takes from the top level is in
  je_editor's `__all__`, except for these names, which it imports from module paths JEditor has not
  promised to keep. `test/test_utils/test_jeditor_contract.py` pins each path and the shape
  PyBreeze calls it with, and fails if the code imports an internal name that is not on this list:

  | Name | JEditor module | Used in |
  | --- | --- | --- |
  | `PluginBrowserWidget` | `pyside_ui.main_ui.plugin_browser.plugin_browser_widget` | `menu/plugin_menu/build_plugin_menu.py` |
  | `DestroyDock` | `pyside_ui.main_ui.dock.destroy_dock` | `closing.py` (`AskingDock`, which the Dock menu builds), `editor_main/main_ui.py` |
  | `init_new_auto_save_thread`, `auto_save_manager_dict`, `file_is_open_manager_dict` | `pyside_ui.code.auto_save.auto_save_manager` | `editor_main/file_tree_context_menu.py` (a rename restarts the tab's auto-save on the new path) |
  | `FullEditorWidget` | `pyside_ui.main_ui.editor.editor_widget_dock` | `editor_main/file_tree_context_menu.py` (a rename re-points a docked editor's `current_file`) |
  | `check_and_choose_venv` | `utils.venv_check.check_venv` | `extend/process_executor/python_task_process_manager.py` |
  | `choose_file_get_save_file_path` | `pyside_ui.dialog.file_dialog.save_file_dialog` | `menu/plugin_menu/build_run_with_menu.py` |
  | `write_file_with_encoding` | `utils.file.save.save_file` | `menu/plugin_menu/build_run_with_menu.py` |
  | `DEFAULT_ENCODING`, `LINE_ENDING_LF` | `utils.encodings.text_codec` | `menu/plugin_menu/build_run_with_menu.py` |
  | `actually_color_dict` | `pyside_ui.main_ui.save_settings.user_color_setting_file` | `show_code_window/code_window.py`, `automation_menu/auto_control_menu/build_autocontrol_menu.py`, `design/tokens.py` (a state's colour), `tools_gui/diff_gui.py` (the diff's line colours: `diff_added_marker_color`, `diff_removed_marker_color`, `syntax_keyword_color`, `blame_annotation_color`) |
  | `RedirectStdErr` | `utils.redirect_manager.redirect_manager_class` | `code_result_logs.py` (the handler `EditorMain` hooks onto every logger to show records in Code Result; PyBreeze raises its level to `WARNING`) |
  | `user_setting_dict` | `pyside_ui.main_ui.save_settings.user_setting_file` | `editor_main/main_ui.py` (`open_main_window()` makes a `theme` given to `start_editor()` the saved `ui_style`, which `EditorMain.startup_setting()` applies over any theme applied before it) |
  | `DEFAULT_SERVERS` | `utils.lsp.language_servers` | `extend/language_server/launch.py` (PyBreeze's action language server is put there for `.json`; JEditor's `LspClient.start_for()` reads the table through `server_command()`, which also wants the command to exist, and `CodeEditor.start_language_server()` starts what it names) |

  PyBreeze also relies on `EditorWidget`'s `current_file`, `code_edit`, `file_encoding`,
  `line_ending`, `mark_ignore_next_file_change()` and `mark_saved()`, on its private `_file_watcher`,
  `_ignore_next_change`, `_is_modified` and `_on_text_changed()` (a rename puts the unsaved mark
  back after `rename_self_tab()` clears it), on `EditorMain.close_tab(index)` (overridden to ask a
  tab's `may_close()` first, and to delete a closed tool tab, which its `removeTab` keeps) and on `CodeEditor`'s `reset_highlighter()`, `load_git_baseline()` and
  `start_language_server()` (a rename moves the tab the way `open_an_file` does), on `EditorMain`'s
  `run_menu.stop_all_program_action` (Stop All Program also stops every run window's run), on
  `EditorMain.__init__` calling `startup_setting()` (the window is built with the saved settings and
  theme; `open_main_window()` applies them again only for a theme given to `start_editor()`), its
  `dock_menu` and its AI submenu `dock_ai_menu` (PyBreeze's AI docks join it; without one they get an
  AI submenu of their own, `menu/tools/tools_menu.py`), on its `language_menu` and `venv_menu` and on the
  `style_menu_label` word that titles its UI Style menu (the navigation panel lists the three under
  Settings and leaves out one it does not find), on the syntax highlighter
  taking a theme colour key (`warning_output_color`, `diff_modified_marker_color`, in both JEditor's dark and light
  sets) for a registered keyword's colour (`syntax/syntax_extend.py`), and on `language_wrapper`'s
  `choose_language_dict` serving English and Traditional Chinese from the exported dict objects
  themselves. Having je_editor export the names in the table is workspace X-17. It
  merges its strings by mutating JEditor's `english_word_dict` and `traditional_chinese_word_dict`
  in place, and writes its `application_name` into every dict in
  `language_wrapper.choose_language_dict` (`extend_multi_language/update_language_dict.py`). That has
  to happen before `EditorMain.__init__`: JEditor serves every language but English from a merged
  copy built when it picks the startup language, so strings added later are missing and a `None`
  menu title crashes Qt (`test_startup_language.py`). JEditor translation changes must keep
  `test_language_parity.py` green.
- **Automation packages**: `je_auto_control`, `je_web_runner`, `je_api_testka`, `je_load_density`,
  `automation_file` and `je_mail_thunder` run as `python -m <pkg> --execute_str/--execute_file`
  (`extend/process_executor/python_task_process_manager.py`). TestPioneer runs as
  `python -m test_pioneer -e <yaml>` through the same manager's `start_module_process`
  (`extend/process_executor/test_pioneer/`).
- **The automation packages' keywords**: the language service asks `je_web_runner`, `je_auto_control` and
  `je_load_density` for their keywords in a child process (`utils/language_service/metadata_probe.py`), and
  relies on each having `<package>.utils.executor.action_executor` with a module-level `executor` whose
  `event_dict` maps every keyword to a callable, on `execute_action()` reading an object-shaped script's
  actions from the key `webdriver_wrapper`, `auto_control` or `load_density`, and on their own keywords
  starting `WR_`, `AC_` or `LD_` (`framework_profiles.py`). `test_metadata_probe.py` asks the installed
  packages and reads their executors' source for the key.
- **The automation packages' reports**: the report viewer reads what `je_api_testka`, `je_auto_control`,
  `je_web_runner` and `je_load_density` write (`execution_report/record_reports.py`) and relies on the pair of
  files `<name>_success.json` / `<name>_failure.json` (or `.xml`, under an `<xml_data>` root), on their
  `Success_Test…` / `Failure_Test…` keys, and on the fields of a record: `request_method`, `request_url`,
  `request_time_sec`, `start_time`, `text`, `http_method`, `test_url`, `error` (APITestka); `function_name`,
  `param`, `time`, `exception` (AutoControl and WebRunner, the latter told by its function names starting
  `webdriver wrapper`, `web element`, `web runner manager` or `webdriver with options`); `Method`,
  `test_url`, `name`, `text`, `error` (LoadDensity). Exported, a run is an `ExecutionReport` as JSON, JUnit
  XML (`testsuites` / `testsuite` / `testcase`), or an HTML page whose data block
  `<script type="application/json" id="pybreeze-execution-report">` carries the report.
- **MCP servers**: the client (`utils/mcp/mcp_client.py`) speaks protocol revisions `2025-06-18`, `2025-03-26`
  and `2024-11-05` over the standard-input-and-output transport, and uses `initialize`,
  `notifications/initialized`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list`,
  `prompts/get`, `ping` and `notifications/cancelled`. It reads the servers file other clients write
  (`mcpServers`: `command`, `args`, `env`) from `~/.pybreeze/mcp_servers.json` and, as servers found but not
  trusted, from a project's `.mcp.json`; PyBreeze's own fields there are `cwd`, `timeout` and `trustedTools`.
  A session exported from the tab is an `ExecutionReport` with `framework` `mcp`.
- **MailThunder, in process**: the report mail (`extend/mail_thunder_extend/mail_thunder_setting.py`) imports
  `SMTPWrapper`, `read_output_content` and `get_mail_thunder_os_environ` from `je_mail_thunder`, and relies on
  `SMTPWrapper()` being an `smtplib.SMTP_SSL`: `_with_timeout()` overrides its `_get_socket(host, port,
  timeout)` to give every step 30 s, a timeout `SMTPWrapper` does not pass on.
- **prthinker**: runs as `python -m prthinker review-file <path>` or
  `review-pr --pr-number <n>` via `TaskProcessManager.start_module_process`
  (`extend/process_executor/prthinker/`), with the interpreter chosen in the IDE, which needs Python
  3.12+ (PyBreeze's own may be older). Settings travel as environment variables, never argv
  (`prthinker_setting.environment_for`): `PRTHINKER_BACKEND`, the chosen backend's model variable
  (`MODEL_ENVIRONMENT`: `PRTHINKER_MODEL_NAME` for `remote`/`local`, otherwise
  `PRTHINKER_<BACKEND>_MODEL`), `PRTHINKER_REMOTE_URL`, `PRTHINKER_REMOTE_API_KEY`,
  `PRTHINKER_OPENAI_API_KEY`, `PRTHINKER_OPENAI_BASE_URL`, `PRTHINKER_ANTHROPIC_API_KEY`,
  `PRTHINKER_PLATFORM`, `PRTHINKER_PLATFORM_BASE_URL`, `GITHUB_REPOSITORY`, `GITHUB_TOKEN`, and
  always both `PRTHINKER_RAG_ENABLED` and `PRTHINKER_REMOTE_RAG` (the child inherits the IDE's
  environment, so one left out would be decided by whatever is exported there). `BACKENDS` must stay a
  subset of `prthinker.config.BackendKind`. It is not on PyPI: the Install menu asks for a local
  source folder and installs `<path>[runner]`; that package excludes prthinker's `codes/` (the local
  RAG index), which is why local retrieval is never left on. `test_prthinker_contract.py` runs the
  real prthinker (CI's 3.12 leg) against the arguments and variables PyBreeze builds, and builds
  prthinker's config (`prthinker.cli._build_parser`, `_build_config`, both in its `__all__`) to check
  each backend gets the model.
- **IDE_Plugins**: the plugin browser's default repo (set in JEditor). Its run configs execute here via
  `FileRunnerProcess`. PyBreeze reads one key JEditor's plugin guide does not define: `"encoding"`, the
  encoding the program's output is in (`"locale"` for the machine's own), documented in `PLUGIN_GUIDE.md`.
- **PySide6 pin**: it must match JEditor and FrontEngine. PyBreeze pins it in `pyproject.toml`,
  `dev.toml` and `requirements.txt`. All three pin 6.11.2, the exact pin of the published je_editor
  1.0.26 and frontengine 1.0.78 (both `==`, so PyBreeze cannot move ahead of them without becoming
  uninstallable). PyBreeze moves when the published je_editor does (workspace X-1).

## 7. Design constraints

- Keep `architecture_explore.md` and the CLAUDE.md tree current in the same change
  (CLAUDE.md § Architecture).
- Never update UI from a worker thread: use Queue + QTimer or Signal/Slot. Keep every menu `QAction`
  alive: store it on the main window or parent it to its menu. Custom exceptions derive from `ITEException`. Log via `pybreeze_logger`
  (§ Conventions).
- An executor is held by the run window it writes to (`CodeWindow.runner`): its QTimer connection does
  not keep it alive, and a collected executor stops pumping output before the exit line. Closing the
  IDE stops every run still going (`CodeWindow.stop_runner()`): a child is a separate, console-less
  process that would otherwise outlive it unseen.
- Every outbound request to a user URL passes SSRF validation (`utils/network/url_validation.py`)
  with timeouts and size caps, and connects through `utils/network/public_http.py`, which connects
  only to the addresses it checks as it connects, trying each in turn (§ Security › Network).
- SSH uses the interactive host-key policy, never auto-add (§ Security › SSH).
- Work that waits on a network — an AI review request, a diagram's image downloads, an SSH
  connect, an SFTP listing or transfer — runs on a
  `QThread` and reaches the UI only through signals. A request panel that closes mid-request hands
  its thread to `thread_keeper.let_run_out()` (cut off from the panel, kept until it ends) rather
  than waiting for it on the UI thread; a running `QThread` must never be destroyed.
- Cyclic garbage is collected on the GUI thread only (`gui_thread_gc.py`, installed by
  `start_editor()`): an automatic collection runs in whichever thread allocates, and one on a worker
  destroyed Qt objects there and crashed the IDE. Never call `gc.enable()` in the IDE.
- Subprocesses use argument lists, `shell=False` and a `timeout`, and pass secrets through `env`
  (§ Security › Subprocess).
- The JupyterLab server stays localhost-only (§ Security › JupyterLab).
- A framework is asked for its keywords in a child process and never imported in the IDE or in the
  language server; the server writes only protocol messages to its standard output; neither is
  started with the folder the IDE is in on its import path (§ Security › Language server).
- An MCP tool call is asked about before it is sent unless the user trusted that tool; a server a project
  names is never started without a yes; nothing secret reaches a log or a report (§ Security › MCP).
- Persist data only under `~/.pybreeze/` (§ Security › File I/O).
- Complexity, length and nesting caps; no silent `except`; no `assert` in runtime code
  (§ Code quality gates).
- `main` is stable and `dev` is development. CI owns the version: never edit it by hand.
  SonarCloud automatic analysis stays off (§ Branching & CI).
- Commit and PR text must follow the attribution rules (§ Commit & PR rules).

## 8. When to update this file

Update it in the same change when any of these changes:

- a top-level package or directory in §2;
- an entry point or an export in `pybreeze/__init__.py`;
- the startup, execution or plugin-run flow in §4;
- an extension point in §5;
- a cross-repo contract in §6 (JEditor base class or imports, the subprocess command-line protocol,
  the prthinker install path, the PySide6 pin);
- a CLAUDE.md section that §7 points to is renamed.

Per-module changes go to `architecture_explore.md`. Refresh the "Last verified" line when you
re-check this file.

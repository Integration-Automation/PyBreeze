# PyBreeze Architecture

> Short overview for people and agents. Per-module detail lives in [`architecture_explore.md`](architecture_explore.md).
> Last verified: 2026-09-23 against `dcd35c6` on `dev`.

## 1. Purpose

PyBreeze is an automation-first Python IDE built on JEditor. CI publishes it as `pybreeze`
(`pyproject.toml`) from `main`; `dev.toml` describes a `pybreeze_dev` package that nothing
publishes any more (workspace X-13). It does not have its own editor.
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
| `pybreeze/pybreeze_ui/tools_gui/` | Thin tool tabs (cURL/HAR import, JWT, regex, diff, headers, …) backed by `pybreeze/utils/` |
| `pybreeze/pybreeze_ui/diagram_editor/` | Diagram editor (QGraphicsScene, Mermaid import, PNG/SVG export) |
| `pybreeze/pybreeze_ui/extend_ai_gui/`, `dialog/` | LLM code-review chain and prompt editors; prthinker settings dialog |
| `pybreeze/pybreeze_ui/connect_gui/` | `ssh/` terminal + SFTP tree; `url/` HTTP code-review client |
| `pybreeze/pybreeze_ui/jupyter_lab_gui/`, `show_code_window/`, `syntax/` | JupyterLab tab; `CodeWindow` subprocess output window; automation keyword highlighting |
| `pybreeze/pybreeze_ui/thread_keeper.py` | `let_run_out()`: a worker `QThread` whose widget closed is kept until it ends instead of being waited for |
| `pybreeze/pybreeze_ui/gui_thread_gc.py` | `GuiThreadGarbageCollector`: automatic garbage collection off, collected on a GUI-thread timer instead (installed by `start_editor()`) |
| `pybreeze/extend/process_executor/` | Subprocess isolation layer: `TaskProcessManager`, `process_executor_utils.py`, `FileRunnerProcess`, `queue_pump.py`, one sub-package per automation package, plus `test_pioneer/` and `prthinker/` |
| `pybreeze/extend/mail_thunder_extend/`, `prthinker_extend/` | Post-test email hook; prthinker settings and argument assembly (pure logic) |
| `pybreeze/extend_multi_language/` | PyBreeze's English and Traditional Chinese strings, merged into JEditor's dictionaries |
| `pybreeze/utils/` | Pure logic, no Qt or JEditor (`test_utils_has_no_qt.py` guards it): request parsing and codegen, HTTP tools, `network/` SSRF validation, pinned connections and capped reads, exceptions, logging, `app_dirs.py`, `subprocess_util.py`, `terminal_text.py` (terminal escapes stripped for the SSH terminal and the run window), `terminal_style.py` (SGR colours read for the SSH terminal) |
| `test/test_utils/` | Unit tests (pure logic and headless widgets). `test/unit_test/start_automation/` holds the launch tests |
| `pyproject.toml`, `dev.toml` | Stable packaging (CI bumps and publishes it) and the unpublished dev packaging (keep its dependencies identical) |
| `.github/workflows/` | `dev.yml`, `stable.yml` (unit tests on a Windows matrix, then SonarCloud) |
| `docs/`, `linux_package_source/`, `architecture_diagram/` | Sphinx docs, Debian package source, architecture image |

The layers are presentation (`pybreeze_ui/`), then execution (`extend/`), then foundation (`utils/`,
`extend_multi_language/`), then external subprocesses.

## 3. Entry points and public interfaces

- **CLI**: `python -m pybreeze` (`pybreeze/__main__.py`). No console script is declared. It and
  `exe/start_pybreeze.py` start the IDE only under `if __name__ == "__main__":` with
  `multiprocessing.freeze_support()`: in the packaged executable the regex tester runs patterns in
  a spawned process, which re-runs the executable. From source it runs them in a plain worker script
  (`python -I -S -c`), so a launch script without the guard is safe.
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
  prthinker settings, edited prompts, review history, and `logs/PyBreeze.log`, which
  `$PYBREEZE_LOG_FILE` can move). The editor settings inherited from JEditor
  stay in `.jeditor/` under the working directory.

## 4. Main flows

**Startup**

```
python -m pybreeze → start_editor() → QApplication → open_main_window() → PyBreezeMainWindow()
  → update_language_dict()             [before JEditor picks the startup language]
  → EditorMain.__init__(extend=True)   [JEditor builds the editor, loads jeditor_plugins/]
  → drop JEditor Help menu → add_menu_to_menubar()
  → syntax_extend_package() → EDITOR_EXTEND_TAB tabs → setup_file_tree_context_menu()
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
Automation menu (automation_menu_factory.build_automation_menu) → call_<pkg>() in
extend/process_executor/<pkg>/ → build_process() (process_executor_utils.py)
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
  - add a sub-package under `extend/process_executor/` with a `_PACKAGE` constant that calls
    `build_process()`;
  - add a menu: one `AutomationMenu(...)` passed to `build_automation_menu()`
    (`pybreeze_ui/menu/automation_menu/automation_menu_factory.py`), wired in
    `menu/build_menubar.py`;
  - add an installer in `menu/install_menu/automation_menu/`;
  - add keywords in `pybreeze_ui/syntax/syntax_keyword.py`.
- **New tool tab or dock**: a widget in `pybreeze_ui/tools_gui/`, its logic in `pybreeze/utils/`, and
  rows in `_WIDGET_FACTORIES` / `_TAB_ACTIONS` / `_DOCK_ACTIONS` / `_DOCK_TITLES`
  (`pybreeze_ui/menu/tools/tools_menu.py`). Like the other tools, a box that holds code calls
  `fixed_pitch.use_fixed_pitch_font()`, and the main button gets Ctrl+Enter through
  `run_shortcut.press_on_ctrl_enter()` (`act_on_ctrl_enter()` when the input decides the action).
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
  | `actually_color_dict` | `pyside_ui.main_ui.save_settings.user_color_setting_file` | `show_code_window/code_window.py`, `automation_menu/auto_control_menu/build_autocontrol_menu.py`, `tools_gui/diff_gui.py` (the diff's line colours: `diff_added_marker_color`, `diff_removed_marker_color`, `syntax_keyword_color`, `blame_annotation_color`) |
  | `RedirectStdErr` | `utils.redirect_manager.redirect_manager_class` | `code_result_logs.py` (the handler `EditorMain` hooks onto every logger to show records in Code Result; PyBreeze raises its level to `WARNING`) |
  | `user_setting_dict` | `pyside_ui.main_ui.save_settings.user_setting_file` | `editor_main/main_ui.py` (`open_main_window()` makes a `theme` given to `start_editor()` the saved `ui_style`, which `EditorMain.startup_setting()` applies over any theme applied before it) |

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
  AI submenu of their own, `menu/tools/tools_menu.py`), on the syntax highlighter
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

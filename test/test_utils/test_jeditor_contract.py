"""What PyBreeze takes from JEditor that je_editor does not export.

je_editor's ``__all__`` is its promise; the names below sit outside it, in module
paths JEditor is free to move. PyBreeze still needs them, so this file pins each
one down: its import path, and the shape PyBreeze calls it with. When JEditor
moves or reshapes one, this fails here instead of in the IDE at the moment
someone opens that menu. ``architecture.md`` §6 lists the same set; keep the two
in step, and move a name to ``EXPORTED`` once je_editor exports it
(workspace X-17).
"""
from __future__ import annotations

import importlib
import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

# (module, name, where PyBreeze uses it)
INTERNAL = [
    ("je_editor.pyside_ui.main_ui.plugin_browser.plugin_browser_widget", "PluginBrowserWidget",
     "menu/plugin_menu/build_plugin_menu.py"),
    ("je_editor.pyside_ui.main_ui.dock.destroy_dock", "DestroyDock",
     "menu/tools/tools_menu.py, editor_main/main_ui.py"),
    ("je_editor.pyside_ui.code.auto_save.auto_save_manager", "init_new_auto_save_thread",
     "editor_main/file_tree_context_menu.py"),
    ("je_editor.pyside_ui.code.auto_save.auto_save_manager", "auto_save_manager_dict",
     "editor_main/file_tree_context_menu.py"),
    ("je_editor.pyside_ui.code.auto_save.auto_save_manager", "file_is_open_manager_dict",
     "editor_main/file_tree_context_menu.py"),
    ("je_editor.pyside_ui.main_ui.editor.editor_widget_dock", "FullEditorWidget",
     "editor_main/file_tree_context_menu.py"),
    ("je_editor.utils.venv_check.check_venv", "check_and_choose_venv",
     "extend/process_executor/python_task_process_manager.py"),
    ("je_editor.pyside_ui.dialog.file_dialog.save_file_dialog", "choose_file_get_save_file_path",
     "menu/plugin_menu/build_run_with_menu.py"),
    ("je_editor.utils.file.save.save_file", "write_file_with_encoding",
     "menu/plugin_menu/build_run_with_menu.py"),
    ("je_editor.utils.encodings.text_codec", "DEFAULT_ENCODING",
     "menu/plugin_menu/build_run_with_menu.py"),
    ("je_editor.utils.encodings.text_codec", "LINE_ENDING_LF",
     "menu/plugin_menu/build_run_with_menu.py"),
    ("je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file", "actually_color_dict",
     "show_code_window/code_window.py, auto_control_menu/build_autocontrol_menu.py"),
]

# Names PyBreeze imports from je_editor's top level, i.e. from its __all__.
EXPORTED = [
    "EditorMain", "EditorWidget", "MainBrowserWidget", "ShellManager", "JEditorExecException",
    "language_wrapper", "english_word_dict", "traditional_chinese_word_dict", "jeditor_logger",
    "load_external_plugins", "register_programming_language", "register_natural_language",
    "get_all_plugin_run_configs", "get_all_plugin_metadata",
]


def _internal(module: str, name: str):
    return getattr(importlib.import_module(module), name)


def _parameters(function) -> list[str]:
    return [name for name in inspect.signature(function).parameters if name != "self"]


@pytest.mark.parametrize(("module", "name", "_used_in"), INTERNAL)
def test_each_internal_name_is_where_pybreeze_imports_it(module, name, _used_in):
    assert hasattr(importlib.import_module(module), name), f"{module}.{name} moved"


@pytest.mark.parametrize("name", EXPORTED)
def test_each_top_level_name_is_still_exported(name):
    import je_editor

    assert name in je_editor.__all__, f"je_editor stopped exporting {name}"


class TestTheShapesPyBreezeCalls:
    def test_the_main_window_takes_the_arguments_pybreeze_passes(self):
        from je_editor import EditorMain

        # PyBreezeMainWindow calls super().__init__(debug_mode, show_system_tray_ray, extend=True).
        assert _parameters(EditorMain.__init__)[:3] == ["debug_mode", "show_system_tray_ray", "extend"]
        assert callable(EditorMain.clear_code_result)
        assert callable(EditorMain.startup_setting)

    def test_an_editor_tab_can_be_saved_the_way_a_run_saves_it(self):
        from je_editor import EditorWidget

        # save_current_file_for_run() reads these and calls these.
        source = inspect.getsource(EditorWidget)
        for attribute in ("current_file", "code_edit", "file_encoding", "line_ending"):
            assert f"self.{attribute}" in source, f"EditorWidget has no {attribute}"
        assert callable(EditorWidget.mark_ignore_next_file_change)
        assert callable(EditorWidget.mark_saved)

    def test_the_save_helpers_take_the_arguments_pybreeze_passes(self):
        write = _internal("je_editor.utils.file.save.save_file", "write_file_with_encoding")
        save_as = _internal(
            "je_editor.pyside_ui.dialog.file_dialog.save_file_dialog",
            "choose_file_get_save_file_path")

        assert _parameters(write)[:4] == ["file_path", "content", "encoding", "line_ending"]
        assert len(_parameters(save_as)) == 1
        assert _internal("je_editor.utils.encodings.text_codec", "LINE_ENDING_LF") == "\n"

    def test_the_interpreter_search_takes_one_directory(self):
        search = _internal("je_editor.utils.venv_check.check_venv", "check_and_choose_venv")
        assert len(_parameters(search)) == 1

    def test_the_output_colours_are_there(self):
        colours = _internal(
            "je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file",
            "actually_color_dict")
        assert {"normal_output_color", "error_output_color"} <= set(colours)

    def test_the_widgets_build_without_arguments(self):
        from PySide6.QtWidgets import QDockWidget, QWidget

        dock = _internal("je_editor.pyside_ui.main_ui.dock.destroy_dock", "DestroyDock")
        browser = _internal(
            "je_editor.pyside_ui.main_ui.plugin_browser.plugin_browser_widget",
            "PluginBrowserWidget")
        assert issubclass(dock, QDockWidget) and not _parameters(dock.__init__)
        assert issubclass(browser, QWidget)
        assert all(
            parameter.default is not inspect.Parameter.empty
            for name, parameter in inspect.signature(browser.__init__).parameters.items()
            if name != "self")

    def test_auto_save_can_be_stopped_and_started_again_on_another_path(self):
        # A rename in the file tree stops a tab's save thread and starts another.
        module = "je_editor.pyside_ui.code.auto_save.auto_save_manager"
        start = _internal(module, "init_new_auto_save_thread")
        assert _parameters(start)[:2] == ["file_path", "widget"]
        assert isinstance(_internal(module, "auto_save_manager_dict"), dict)
        assert isinstance(_internal(module, "file_is_open_manager_dict"), dict)
        thread = _internal("je_editor.pyside_ui.code.auto_save.auto_save_thread", "CodeEditSaveThread")
        source = inspect.getsource(thread)
        assert "self.still_run" in source and "self.file" in source

    def test_a_rename_can_move_what_an_editor_tab_follows_its_file_with(self):
        # The file tree moves the tab's watcher, as open_an_file does, and
        # reloads what goes by the path
        from je_editor import EditorWidget

        source = inspect.getsource(EditorWidget)
        assert "self._file_watcher = QFileSystemWatcher" in source
        assert "self._ignore_next_change" in source
        # A rename puts the unsaved mark back after rename_self_tab clears it
        assert "self._is_modified" in inspect.getsource(EditorWidget.rename_self_tab)
        assert "self._is_modified = True" in inspect.getsource(EditorWidget._on_text_changed)
        code_editor = _internal("je_editor.pyside_ui.code.plaintext_code_edit.code_edit_plaintext", "CodeEditor")
        for method in ("reset_highlighter", "load_git_baseline", "start_language_server"):
            assert callable(getattr(code_editor, method, None)), method

    def test_a_tab_closes_through_close_tab(self):
        # PyBreeze overrides it to ask a tab's may_close() first
        from je_editor import EditorMain

        assert _parameters(EditorMain.close_tab) == ["index"]
        assert "widget.close()" in inspect.getsource(EditorMain.close_tab)

    def test_a_docked_editor_writes_to_the_file_it_names_when_it_closes(self):
        # A rename re-points current_file; the dock saves nothing else
        docked = _internal("je_editor.pyside_ui.main_ui.editor.editor_widget_dock", "FullEditorWidget")
        assert _parameters(docked.__init__) == ["current_file"]
        assert "self.current_file" in inspect.getsource(docked.closeEvent)

    def test_the_language_wrapper_has_what_pybreeze_reads(self):
        from je_editor import language_wrapper

        for member in ("language", "language_word_dict", "choose_language_dict"):
            assert hasattr(language_wrapper, member), member
        assert callable(language_wrapper.reset_language)
        assert callable(language_wrapper.available_languages)
        # PyBreeze adds its strings to these two dicts in place, so they must be
        # the very objects the wrapper serves English and Traditional Chinese from.
        from je_editor import english_word_dict, traditional_chinese_word_dict
        assert language_wrapper.choose_language_dict["English"] is english_word_dict
        assert language_wrapper.choose_language_dict["Traditional_Chinese"] is traditional_chinese_word_dict


def test_the_list_matches_the_code():
    """Every internal je_editor import in pybreeze/ is listed above, and nothing else is."""
    import pathlib
    import re

    import pybreeze

    # Both "import a, b" and "import (\n    a, b,\n)": a parenthesised import that
    # the check could not read would slip past it unlisted.
    pattern = re.compile(
        r"^\s*from (je_editor\.[\w.]+) import (?:\(([^)]*)\)|([\w, ]+)$)", re.MULTILINE)
    found = set()
    for path in pathlib.Path(pybreeze.__file__).parent.rglob("*.py"):
        for module, wrapped, plain in pattern.findall(path.read_text(encoding="utf-8")):
            names = (wrapped or plain).replace("\n", " ").split(",")
            found.update((module, name.strip()) for name in names if name.strip())
    assert found == {(module, name) for module, name, _ in INTERNAL}

"""The plugin menus: what they build from a plugin registry, and what "Run with" refuses.

Both menus read je_editor's plugin registry, so each test supplies its own
registry contents rather than depending on whichever plugins happen to be
installed.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMenuBar, QPlainTextEdit, QTabWidget, QWidget
)

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.plugin_menu import build_plugin_menu as plugin_menu
from pybreeze.pybreeze_ui.menu.plugin_menu import build_run_with_menu as run_with
from pybreeze.pybreeze_ui.menu.plugin_menu.build_plugin_menu import set_plugin_menu
from pybreeze.pybreeze_ui.menu.plugin_menu.build_run_with_menu import (
    run_config_suffixes, run_current_file_with, save_current_file_for_run, set_run_with_menu
)

GO_CONFIG = {"name": "Go", "compiler": "go", "args": ("run",), "suffixes": (".go",)}
RUST_CONFIG = {"name": "Rust", "compiler": "rustc", "suffixes": (".rs",),
               "compile_then_run": True, "output_flag": "-o"}
MULTI_CONFIG = {"name": "C++", "compiler": "g++", "suffixes": (".cpp", ".hpp")}


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class FakeWindow(QMainWindow):
    """A main window with the handful of members the menu builders touch."""

    def __init__(self) -> None:
        super().__init__()
        self.menu = QMenuBar(self)
        self.run_menu = self.menu.addMenu("Run")
        self.tab_widget = QTabWidget()
        self.current_run_code_window: list[QWidget] = []
        self.encoding = "utf-8"


@pytest.fixture
def window(app):
    made = FakeWindow()
    yield made
    made.deleteLater()


def labels(menu) -> list[str]:
    return [action.text() for action in menu.actions()]


def submenu_action_texts(menu) -> list[list[str]]:
    """Return the action texts of each submenu of *menu*, submenu by submenu.

    The texts are read while the owning ``QAction`` is still referenced rather
    than handed back as ``QMenu`` objects: a submenu built by ``addMenu(title)``
    is owned through its action, and under pytest the wrapper is collected
    eagerly enough that a returned ``QMenu`` can be dead before the caller
    touches it.
    """
    collected: list[list[str]] = []
    for action in menu.actions():
        sub = action.menu()
        if sub is not None:
            collected.append([entry.text() for entry in sub.actions()])
        del sub
    return collected


class TestTheRunWithMenu:
    def test_no_plugins_means_no_menu(self, window, monkeypatch):
        monkeypatch.setattr(run_with, "get_all_plugin_run_configs", lambda: [])
        set_run_with_menu(window)
        assert not hasattr(window, "run_with_menu")

    def test_one_entry_per_run_config(self, window, monkeypatch):
        monkeypatch.setattr(
            run_with, "get_all_plugin_run_configs", lambda: [GO_CONFIG, RUST_CONFIG])
        set_run_with_menu(window)
        assert len(window.run_with_menu.actions()) == 2

    def test_entries_are_sorted_by_name(self, window, monkeypatch):
        monkeypatch.setattr(
            run_with, "get_all_plugin_run_configs",
            lambda: [RUST_CONFIG, GO_CONFIG, MULTI_CONFIG])
        set_run_with_menu(window)
        names = [text.split(" ")[0] for text in labels(window.run_with_menu)]
        assert names == ["C++", "Go", "Rust"]

    def test_the_label_lists_the_suffixes(self, window, monkeypatch):
        monkeypatch.setattr(
            run_with, "get_all_plugin_run_configs", lambda: [MULTI_CONFIG])
        set_run_with_menu(window)
        assert ".cpp, .hpp" in labels(window.run_with_menu)[0]

    def test_a_config_without_suffixes_is_labelled_by_name_alone(
            self, window, monkeypatch):
        monkeypatch.setattr(
            run_with, "get_all_plugin_run_configs", lambda: [{"name": "Bare"}])
        set_run_with_menu(window)
        assert labels(window.run_with_menu) == ["Bare"]


class TestTheSuffixesAPluginRegistered:
    @pytest.mark.parametrize(("registered", "expected"), [
        ((".go",), (".go",)),
        ((".R",), (".r",)),
        (("r",), (".r",)),
        ((" .Py ", "py"), (".py",)),
        (".rs", (".rs",)),
        (("", ".", None, 3), ()),
    ])
    def test_they_read_as_a_file_suffix_does(self, registered, expected):
        assert run_config_suffixes({"suffixes": registered}) == expected

    def test_a_file_matching_a_suffix_registered_in_capitals_runs(self, window, tmp_path, monkeypatch):
        script = tmp_path / "analysis.r"
        script.touch()
        monkeypatch.setattr(run_with, "save_current_file_for_run", lambda _w: str(script))
        refused: list = []
        monkeypatch.setattr(run_with.QMessageBox, "exec", lambda self: refused.append(self.text()))
        started: list = []
        monkeypatch.setattr(
            run_with, "FileRunnerProcess",
            lambda **kwargs: type("R", (), {"run_file": lambda *a: started.append(a)})())

        run_current_file_with(window, {"name": "R", "compiler": "Rscript", "suffixes": (".R",)})

        assert refused == []
        assert started


class TestFindingTheFileToRun:
    def test_a_non_editor_tab_offers_no_file(self, window):
        window.tab_widget.addTab(QWidget(), "not an editor")
        window.tab_widget.setCurrentIndex(0)
        assert save_current_file_for_run(window) is None

    def test_no_tabs_at_all_offers_no_file(self, window):
        assert save_current_file_for_run(window) is None


class TestRefusingToRunTheWrongFile:
    def test_a_suffix_mismatch_warns_and_runs_nothing(
            self, window, tmp_path, monkeypatch):
        script = tmp_path / "script.py"
        script.touch()
        monkeypatch.setattr(run_with, "save_current_file_for_run", lambda _w: str(script))
        shown: list[str] = []
        monkeypatch.setattr(
            run_with.QMessageBox, "exec", lambda self: shown.append(self.text()))
        started: list[object] = []
        monkeypatch.setattr(
            run_with, "FileRunnerProcess",
            lambda **kwargs: started.append(kwargs))

        run_current_file_with(window, GO_CONFIG)

        assert shown
        assert ".py" in shown[0]
        assert not started

    def test_no_file_means_nothing_runs(self, window, monkeypatch):
        monkeypatch.setattr(run_with, "save_current_file_for_run", lambda _w: None)
        started: list[object] = []
        monkeypatch.setattr(
            run_with, "FileRunnerProcess", lambda **kwargs: started.append(kwargs))
        run_current_file_with(window, GO_CONFIG)
        assert not started

    def test_a_matching_suffix_opens_a_run_window_and_starts(
            self, window, tmp_path, monkeypatch):
        script = tmp_path / "main.go"
        script.touch()
        monkeypatch.setattr(run_with, "save_current_file_for_run", lambda _w: str(script))

        class Runner:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs
                started.append(self)

            def run_file(self, config, path) -> None:
                self.ran = (config, path)

        started: list[Runner] = []
        monkeypatch.setattr(run_with, "FileRunnerProcess", Runner)

        run_current_file_with(window, GO_CONFIG)

        assert len(started) == 1
        assert started[0].ran == (GO_CONFIG, str(script))
        assert len(window.current_run_code_window) == 1

    def test_a_config_without_suffixes_accepts_any_file(
            self, window, tmp_path, monkeypatch):
        script = tmp_path / "anything.xyz"
        script.touch()
        monkeypatch.setattr(run_with, "save_current_file_for_run", lambda _w: str(script))
        started: list[object] = []
        monkeypatch.setattr(
            run_with, "FileRunnerProcess",
            lambda **kwargs: type("R", (), {"run_file": lambda *a: started.append(a)})())
        run_current_file_with(window, {"name": "Anything", "compiler": "cat"})
        assert started


class TestThePluginMenu:
    def test_with_no_plugins_the_menu_still_offers_the_plugin_browser(self, window, monkeypatch):
        # The browser is how a first plugin gets installed: the menu was left
        # out while none was loaded, so it could not be reached until one was
        # copied into jeditor_plugins/ by hand. JEditor's own menu always has it.
        monkeypatch.setattr(plugin_menu, "get_all_plugin_metadata", lambda: [])
        set_plugin_menu(window)
        assert labels(window.plugin_menu) == ["Plugin Browser"]

    def test_the_plugin_browser_opens_as_a_tab(self, window, monkeypatch):
        monkeypatch.setattr(plugin_menu, "get_all_plugin_metadata", lambda: [])
        monkeypatch.setattr(plugin_menu, "PluginBrowserWidget", QWidget)
        set_plugin_menu(window)

        window.plugin_menu.actions()[0].trigger()

        assert window.tab_widget.count() == 1
        assert window.tab_widget.tabText(0).startswith("Plugin Browser")

    def test_a_plugin_without_a_run_config_gets_a_bare_entry(
            self, window, monkeypatch):
        monkeypatch.setattr(
            plugin_menu, "get_all_plugin_metadata",
            lambda: [{"name": "French", "version": "1.0", "author": "someone"}])
        set_plugin_menu(window)
        assert "French" in labels(window.plugin_menu)

    def test_a_plugin_with_a_run_config_gets_a_submenu(self, window, monkeypatch):
        monkeypatch.setattr(
            plugin_menu, "get_all_plugin_metadata",
            lambda: [{"name": "Go", "version": "1.0", "author": "someone",
                      "run_config": GO_CONFIG}])
        set_plugin_menu(window)
        submenus = submenu_action_texts(window.plugin_menu)
        assert len(submenus) == 1
        # About, a separator (empty text), then one run action for the suffix
        assert [text for text in submenus[0] if text] == ["About", "Run with Go"]

    def test_multiple_suffixes_share_one_run_action_that_lists_them(self, window, monkeypatch):
        # There was one entry per suffix, and every one ran the same config:
        # the file's own suffix decides what runs, not the entry picked.
        monkeypatch.setattr(
            plugin_menu, "get_all_plugin_metadata",
            lambda: [{"name": "C++", "version": "1.0", "author": "someone",
                      "run_config": MULTI_CONFIG}])
        set_plugin_menu(window)
        submenu = submenu_action_texts(window.plugin_menu)[0]
        runs = [text for text in submenu if "(" in text]
        assert len(runs) == 1
        assert ".cpp, .hpp" in runs[0]

    def test_the_browser_entry_comes_first(self, window, monkeypatch):
        monkeypatch.setattr(
            plugin_menu, "get_all_plugin_metadata",
            lambda: [{"name": "French", "version": "1.0", "author": "someone"}])
        set_plugin_menu(window)
        assert "Plugin Browser" in window.plugin_menu.actions()[0].text()

    def test_the_about_dialog_names_version_and_author(self, app, monkeypatch):
        shown: list[str] = []
        monkeypatch.setattr(
            plugin_menu.QMessageBox, "exec", lambda self: shown.append(self.text()))
        plugin_menu._make_about_callback(None, "Go", "2.1", "someone")()
        assert "2.1" in shown[0]
        assert "someone" in shown[0]

    def test_the_about_dialog_speaks_the_ide_language(self, app, monkeypatch):
        # "Version:" and "Author:" were English whatever the IDE spoke
        from pybreeze.extend_multi_language.extend_traditional_chinese import (
            pybreeze_traditional_chinese_word_dict,
        )
        monkeypatch.setattr(plugin_menu.language_wrapper, "language_word_dict",
                            pybreeze_traditional_chinese_word_dict)
        shown: list[str] = []
        monkeypatch.setattr(
            plugin_menu.QMessageBox, "exec", lambda self: shown.append(self.text()))
        plugin_menu._make_about_callback(None, "Go", "2.1", "someone")()

        assert "版本" in shown[0]
        assert "作者" in shown[0]
        assert "Version" not in shown[0]
        assert "Author" not in shown[0]

    def test_the_about_dialog_shows_markup_as_text(self, app, monkeypatch):
        # A plugin's name or author went to the box as markup, <img> and all
        from PySide6.QtGui import QTextDocument

        shown: list[str] = []
        monkeypatch.setattr(
            plugin_menu.QMessageBox, "exec", lambda self: shown.append(self.text()))
        plugin_menu._make_about_callback(None, "<b>Go</b>", "1", "<img src=x>")()

        document = QTextDocument()
        document.setHtml(shown[0])
        assert "<b>Go</b>" in document.toPlainText()
        assert "<img src=x>" in document.toPlainText()

    def test_a_run_callback_ignores_a_non_editor_tab(self, window, monkeypatch):
        window.tab_widget.addTab(QWidget(), "not an editor")
        window.tab_widget.setCurrentIndex(0)
        started: list[object] = []
        monkeypatch.setattr(
            run_with, "FileRunnerProcess",
            lambda **kwargs: started.append(kwargs))
        plugin_menu._make_run_callback(window, GO_CONFIG)()
        assert not started

    def test_a_run_callback_runs_the_way_run_with_does(self, window, monkeypatch):
        calls: list[tuple] = []
        monkeypatch.setattr(
            plugin_menu, "run_current_file_with",
            lambda main_window, config: calls.append((main_window, config)))
        plugin_menu._make_run_callback(window, GO_CONFIG)()
        assert calls == [(window, GO_CONFIG)]


class EditorTab(QWidget):
    """Stands in for a JEditor editor tab: its file, its text and how it saves."""

    def __init__(self, current_file=None, text="", file_encoding="utf-8",
                 line_ending="\n") -> None:
        super().__init__()
        self.current_file = current_file
        self.code_edit = QPlainTextEdit(text)
        self.file_encoding = file_encoding
        self.line_ending = line_ending
        self.events: list[str] = []

    def mark_ignore_next_file_change(self) -> None:
        self.events.append("expect write")

    def mark_saved(self) -> None:
        self.events.append("saved")


@pytest.fixture
def editor_tab(window, monkeypatch):
    """Put an editor tab in the window; the helper recognises it by type."""
    monkeypatch.setattr(run_with, "EditorWidget", EditorTab)

    def make(**kwargs) -> EditorTab:
        tab = EditorTab(**kwargs)
        window.tab_widget.addTab(tab, "tab")
        window.tab_widget.setCurrentWidget(tab)
        return tab
    return make


class TestSavingBeforeARun:
    def test_a_saved_file_keeps_its_encoding_and_line_endings(self, window, editor_tab, tmp_path):
        target = tmp_path / "legacy.txt"
        target.write_bytes("舊\r\n".encode("big5"))
        editor_tab(current_file=str(target), text="中文\n第二行\n",
                   file_encoding="big5", line_ending="\r\n")

        assert save_current_file_for_run(window) == str(target)
        assert target.read_bytes() == "中文\r\n第二行\r\n".encode("big5")

    def test_the_tab_expects_the_write_and_is_marked_saved(self, window, editor_tab, tmp_path):
        target = tmp_path / "main.go"
        tab = editor_tab(current_file=str(target), text="package main\n")

        save_current_file_for_run(window)

        assert tab.events == ["expect write", "saved"]
        assert target.read_bytes() == b"package main\n"

    def test_an_unnamed_tab_goes_through_save_as(self, window, editor_tab, tmp_path, monkeypatch):
        tab = editor_tab(text="print(1)\n")
        chosen = str(tmp_path / "chosen.py")

        def save_as(_main_window):
            tab.current_file = chosen
            return True

        monkeypatch.setattr(run_with, "choose_file_get_save_file_path", save_as)
        assert save_current_file_for_run(window) == chosen

    def test_a_cancelled_save_as_runs_nothing(self, window, editor_tab, monkeypatch):
        editor_tab(text="print(1)\n")
        monkeypatch.setattr(run_with, "choose_file_get_save_file_path", lambda _w: False)
        assert save_current_file_for_run(window) is None


class TestASaveThatFailsBeforeARun:
    """A read-only or locked file, or a character the tab's encoding cannot hold."""

    def test_it_is_reported_and_runs_nothing(self, window, editor_tab, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        warned: list = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a)))
        target = tmp_path / "legacy.txt"
        target.write_bytes("舊".encode("big5"))
        tab = editor_tab(current_file=str(target), text="€ is not in Big5\n", file_encoding="big5")

        # It used to raise out of the menu slot, so nothing said why nothing ran.
        assert save_current_file_for_run(window) is None
        assert warned
        assert "legacy.txt" in warned[0][2]
        # ... and the tab still expects no write of its own, so the next real
        # change made outside the editor is not swallowed.
        assert tab.events == []


class TestRunConfigsJEditorDoesNotCheck:
    def test_a_config_without_a_name_still_runs(self, window, tmp_path, monkeypatch):
        script = tmp_path / "main.go"
        script.touch()
        monkeypatch.setattr(run_with, "save_current_file_for_run", lambda _w: str(script))
        started: list[object] = []
        monkeypatch.setattr(
            run_with, "FileRunnerProcess",
            lambda **kwargs: type("R", (), {"run_file": lambda *a: started.append(a)})())

        run_current_file_with(window, {"compiler": "go", "suffixes": (".go",)})

        assert started
        assert window.current_run_code_window[-1].windowTitle() == "Run - main.go"

    def test_a_config_without_a_compiler_is_reported_in_the_run_window(self, app):
        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        run_window = CodeWindow()
        FileRunnerProcess(run_window).run_file({"name": "Broken"}, "main.go")

        assert "names no compiler" in run_window.code_result.toPlainText()


class TestAPluginThatDoesNotFollowTheRules:
    """A plugin is third-party code: one bad plugin stopped the IDE from starting."""

    def test_a_run_config_that_is_not_a_dict_is_skipped(self, window, monkeypatch):
        # run_config_suffixes raised AttributeError while the main window was built
        monkeypatch.setattr(
            plugin_menu, "get_all_plugin_metadata",
            lambda: [{"name": "Odd", "run_config": ["not", "a", "dict"]},
                     {"name": "Go", "run_config": GO_CONFIG}])
        set_plugin_menu(window)

        assert "Odd" in labels(window.plugin_menu)
        assert [text for text in submenu_action_texts(window.plugin_menu)[0] if text] == ["About", "Run with Go"]

    def test_a_name_that_is_none_gets_a_label(self, window, monkeypatch):
        # addMenu(None) is an access violation, not a Python error
        monkeypatch.setattr(
            plugin_menu, "get_all_plugin_metadata",
            lambda: [{"name": None, "run_config": {"name": None, "suffixes": [".x"]}}, "not metadata"])
        set_plugin_menu(window)

        assert submenu_action_texts(window.plugin_menu)

    def test_run_configs_with_none_and_text_names_sort(self, window, monkeypatch):
        # sorted() raised comparing None with a string
        monkeypatch.setattr(
            run_with, "get_all_plugin_run_configs",
            lambda: [{"name": "Go", "suffixes": [".go"]}, {"name": None}, "not a config"])
        set_run_with_menu(window)

        assert labels(window.run_with_menu) == ["Go  (.go)", "Unknown"]


class TestTheEncodingAProgramWrites:
    """Java and localized compilers write the console code page, not UTF-8."""

    def test_the_ides_encoding_by_default(self):
        from pybreeze.pybreeze_ui.menu.plugin_menu.build_run_with_menu import output_encoding

        assert output_encoding({"name": "Go"}, "utf-8") == "utf-8"

    def test_a_config_can_name_its_own(self):
        from pybreeze.pybreeze_ui.menu.plugin_menu.build_run_with_menu import output_encoding

        assert output_encoding({"name": "Java", "encoding": "MS950"}, "utf-8") == "cp950"

    def test_locale_means_this_machines(self):
        import locale

        from pybreeze.pybreeze_ui.menu.plugin_menu.build_run_with_menu import output_encoding

        assert output_encoding({"encoding": "locale"}, "utf-8") == locale.getpreferredencoding(False)

    @pytest.mark.parametrize("named", ["no-such-codec", 5, "  "])
    def test_anything_else_keeps_the_default(self, named):
        from pybreeze.pybreeze_ui.menu.plugin_menu.build_run_with_menu import output_encoding

        assert output_encoding({"name": "Odd", "encoding": named}, "utf-8") == "utf-8"

    def test_the_run_decodes_with_it(self, window, monkeypatch, tmp_path):
        script = tmp_path / "anything.xyz"
        script.touch()
        monkeypatch.setattr(run_with, "save_current_file_for_run", lambda _w: str(script))
        made: list = []
        monkeypatch.setattr(
            run_with, "FileRunnerProcess",
            lambda **kwargs: made.append(kwargs) or type("R", (), {"run_file": lambda *a: None})())

        run_current_file_with(window, {"name": "Java", "compiler": "java", "encoding": "cp950"})

        assert made[0]["program_encoding"] == "cp950"

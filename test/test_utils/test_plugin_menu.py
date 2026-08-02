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
    QApplication, QMainWindow, QMenuBar, QTabWidget, QWidget
)

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.plugin_menu import build_plugin_menu as plugin_menu
from pybreeze.pybreeze_ui.menu.plugin_menu import build_run_with_menu as run_with
from pybreeze.pybreeze_ui.menu.plugin_menu.build_plugin_menu import set_plugin_menu
from pybreeze.pybreeze_ui.menu.plugin_menu.build_run_with_menu import (
    _get_current_file, _run_with, set_run_with_menu
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


@pytest.fixture()
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


class TestFindingTheFileToRun:
    def test_a_non_editor_tab_offers_no_file(self, window):
        window.tab_widget.addTab(QWidget(), "not an editor")
        window.tab_widget.setCurrentIndex(0)
        assert _get_current_file(window) is None

    def test_no_tabs_at_all_offers_no_file(self, window):
        assert _get_current_file(window) is None


class TestRefusingToRunTheWrongFile:
    def test_a_suffix_mismatch_warns_and_runs_nothing(
            self, window, tmp_path, monkeypatch):
        script = tmp_path / "script.py"
        script.touch()
        monkeypatch.setattr(run_with, "_get_current_file", lambda _w: str(script))
        shown: list[str] = []
        monkeypatch.setattr(
            run_with.QMessageBox, "exec", lambda self: shown.append(self.text()))
        started: list[object] = []
        monkeypatch.setattr(
            run_with, "FileRunnerProcess",
            lambda **kwargs: started.append(kwargs))

        _run_with(window, GO_CONFIG)

        assert shown and ".py" in shown[0]
        assert not started

    def test_no_file_means_nothing_runs(self, window, monkeypatch):
        monkeypatch.setattr(run_with, "_get_current_file", lambda _w: None)
        started: list[object] = []
        monkeypatch.setattr(
            run_with, "FileRunnerProcess", lambda **kwargs: started.append(kwargs))
        _run_with(window, GO_CONFIG)
        assert not started

    def test_a_matching_suffix_opens_a_run_window_and_starts(
            self, window, tmp_path, monkeypatch):
        script = tmp_path / "main.go"
        script.touch()
        monkeypatch.setattr(run_with, "_get_current_file", lambda _w: str(script))

        class Runner:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs
                started.append(self)

            def run_file(self, config, path) -> None:
                self.ran = (config, path)

        started: list[Runner] = []
        monkeypatch.setattr(run_with, "FileRunnerProcess", Runner)

        _run_with(window, GO_CONFIG)

        assert len(started) == 1
        assert started[0].ran == (GO_CONFIG, str(script))
        assert len(window.current_run_code_window) == 1

    def test_a_config_without_suffixes_accepts_any_file(
            self, window, tmp_path, monkeypatch):
        script = tmp_path / "anything.xyz"
        script.touch()
        monkeypatch.setattr(run_with, "_get_current_file", lambda _w: str(script))
        started: list[object] = []
        monkeypatch.setattr(
            run_with, "FileRunnerProcess",
            lambda **kwargs: type("R", (), {"run_file": lambda *a: started.append(a)})())
        _run_with(window, {"name": "Anything", "compiler": "cat"})
        assert started


class TestThePluginMenu:
    def test_no_plugins_means_no_menu(self, window, monkeypatch):
        monkeypatch.setattr(plugin_menu, "get_all_plugin_metadata", lambda: [])
        set_plugin_menu(window)
        assert not hasattr(window, "plugin_menu")

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

    def test_multiple_suffixes_get_one_run_action_each(self, window, monkeypatch):
        monkeypatch.setattr(
            plugin_menu, "get_all_plugin_metadata",
            lambda: [{"name": "C++", "version": "1.0", "author": "someone",
                      "run_config": MULTI_CONFIG}])
        set_plugin_menu(window)
        submenu = submenu_action_texts(window.plugin_menu)[0]
        runs = [text for text in submenu if "(" in text]
        assert len(runs) == 2
        assert ".cpp" in runs[0] and ".hpp" in runs[1]

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
        plugin_menu._make_about_callback("Go", "2.1", "someone")()
        assert "2.1" in shown[0]
        assert "someone" in shown[0]

    def test_a_run_callback_ignores_a_non_editor_tab(self, window, monkeypatch):
        window.tab_widget.addTab(QWidget(), "not an editor")
        window.tab_widget.setCurrentIndex(0)
        started: list[object] = []
        monkeypatch.setattr(
            plugin_menu, "FileRunnerProcess",
            lambda **kwargs: started.append(kwargs))
        plugin_menu._make_run_callback(window, GO_CONFIG)()
        assert not started

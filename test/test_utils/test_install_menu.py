"""Installing packages from the Install menu: one pip, no shell, in a run window."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.install_menu import install_utils
from pybreeze.pybreeze_ui.menu.install_menu.install_utils import install_package


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class Process:
    """Records the module run instead of starting it."""

    def __init__(self) -> None:
        self.runs: list = []

    def start_module_process(self, package, arguments, environment=None) -> None:
        self.runs.append((package, list(arguments)))


@pytest.fixture
def processes(monkeypatch) -> list:
    started: list = []

    def build(_window) -> Process:
        process = Process()
        started.append(process)
        return process

    monkeypatch.setattr(install_utils, "build_task_process", build)
    return started


def _runs(processes) -> list:
    return [run for process in processes for run in process.runs]


class TestInstallingAPackage:
    def test_it_runs_pip_as_a_module(self, app, processes):
        install_package("je_web_runner", object())

        assert _runs(processes) == [("pip", ["install", "-U", "je_web_runner"])]

    def test_a_source_folder_target_is_one_argument(self, app, processes):
        install_package(r"D:\R&D\prthinker[runner]", object())

        assert _runs(processes) == [("pip", ["install", "-U", r"D:\R&D\prthinker[runner]"])]


class TestNoShellIsInvolved:
    def test_a_folder_name_with_shell_characters_reaches_the_module_unchanged(
            self, app, tmp_path):
        # Through cmd.exe, "&" ended the command. The executor pip now runs in
        # passes argv to the child as it is: run it for real, with a module
        # standing in for pip that prints what it was given.
        import time

        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        (tmp_path / "echo_argv.py").write_text(
            "import sys\nprint(repr(sys.argv[1:]))\n", encoding="utf-8")
        target = r"D:\R&D|x^y%PATH%\prthinker[runner]"

        class MainWindow:
            python_compiler = sys.executable
            encoding = "utf-8"

            def __init__(self) -> None:
                self.current_run_code_window: list = []

            def clear_code_result(self) -> None:
                """Nothing to clear in a stand-in."""

        window = MainWindow()
        build_task_process(window).start_module_process(
            "echo_argv", ["install", "-U", target], environment={"PYTHONPATH": str(tmp_path)})
        run_window = window.current_run_code_window[0]
        deadline = time.monotonic() + 30
        while "Task exit with code" not in run_window.code_result.toPlainText():
            assert time.monotonic() < deadline, "the child did not finish"
            app.processEvents()
            time.sleep(0.01)

        assert repr(["install", "-U", target]) in run_window.code_result.toPlainText()


class TestInstallingTheBuildTools:
    def test_one_pip_installs_all_three(self, app, processes):
        from pybreeze.pybreeze_ui.menu.install_menu.tools_menu.build_tool_install_menu import (
            install_build_tools,
        )

        install_build_tools(object())

        assert _runs(processes) == [("pip", ["install", "-U", "setuptools", "build", "wheel"])]


class TestTheAutomationInstallMenu:
    """Each entry installs its own package."""

    @staticmethod
    def _menu(app):
        from types import SimpleNamespace

        from PySide6.QtWidgets import QMenu

        from pybreeze.pybreeze_ui.menu.install_menu.automation_menu.build_automation_install_menu import (
            build_automation_install_menu,
        )

        window = SimpleNamespace(install_menu=QMenu())
        build_automation_install_menu(window)
        return window, window.install_automation_menu

    def test_the_entries_and_their_packages(self, app, processes):
        from je_editor import language_wrapper

        window, menu = self._menu(app)
        words = language_wrapper.language_word_dict
        pip_entries = [action for action in menu.actions()
                       if action.text() != words.get("install_menu_prthinker")]
        installed = []
        for action in pip_entries:
            action.trigger()
            installed.append((action.text(), _runs(processes)[-1][1][-1]))

        assert installed == [
            (words.get("install_menu_autocontrol"), "je_auto_control"),
            (words.get("install_menu_apitestka"), "je_api_testka"),
            (words.get("install_menu_loaddensity"), "je_load_density"),
            (words.get("install_menu_webrunner"), "je_web_runner"),
            (words.get("install_menu_automation_file"), "automation_file"),
            (words.get("install_menu_mail_thunder"), "je_mail_thunder"),
            (words.get("install_menu_test_pioneer"), "test_pioneer"),
        ]
        assert menu.actions()[-1].text() == words.get("install_menu_prthinker")


class TestInstallingPrthinker:
    def test_a_remembered_source_folder_is_installed(self, app, processes, monkeypatch, tmp_path):
        from pybreeze.pybreeze_ui.menu.install_menu.automation_menu import (
            build_automation_install_menu as install_menu,
        )

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "prthinker"\n', encoding="utf-8")
        monkeypatch.setattr(install_menu, "load_setting", lambda: {"source_path": str(tmp_path)})

        install_menu.install_prthinker(object())

        (run,) = _runs(processes)
        assert run[0] == "pip"
        assert run[1][2].startswith(str(tmp_path))

    def test_a_folder_that_is_not_its_source_is_not_saved(self, app, processes, monkeypatch, tmp_path):
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from pybreeze.pybreeze_ui.menu.install_menu.automation_menu import (
            build_automation_install_menu as install_menu,
        )

        saved: list = []
        monkeypatch.setattr(install_menu, "load_setting", lambda: {"source_path": ""})
        monkeypatch.setattr(install_menu, "save_setting", saved.append)
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

        install_menu.install_prthinker(None)

        # A wrong pick used to be remembered, so every later click ran a pip that failed.
        assert saved == []
        assert _runs(processes) == []

    def test_a_source_folder_picked_is_remembered_and_installed(self, app, processes, monkeypatch, tmp_path):
        from PySide6.QtWidgets import QFileDialog

        from pybreeze.pybreeze_ui.menu.install_menu.automation_menu import (
            build_automation_install_menu as install_menu,
        )

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "prthinker"\n', encoding="utf-8")
        saved: list = []
        monkeypatch.setattr(install_menu, "load_setting", lambda: {"source_path": "", "backend": "kept"})
        monkeypatch.setattr(install_menu, "save_setting", saved.append)
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))

        install_menu.install_prthinker(None)

        # Asked once: the next install takes it from the settings
        assert saved == [{"source_path": str(tmp_path), "backend": "kept"}]
        (run,) = _runs(processes)
        assert run[1][2].startswith(str(tmp_path))

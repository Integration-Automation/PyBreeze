"""Installing an automation package: which interpreter pip runs with, and where it runs."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.install_menu import install_utils
from pybreeze.pybreeze_ui.menu.install_menu.install_utils import install_package


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class EditorTab(QWidget):
    """Stands in for JEditor's editor tab, which is where the install's output goes."""

    def __init__(self) -> None:
        super().__init__()
        self.python_compiler = None


class Window(QMainWindow):
    def __init__(self, tab: QWidget, python_compiler=None) -> None:
        super().__init__()
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(tab, "tab")
        self.python_compiler = python_compiler


class Shell:
    """Records the command instead of starting a shell."""

    last: "Shell | None" = None

    def __init__(self, main_window) -> None:
        self.main_window = main_window
        self.compiler_path = "shell/python"
        self.commands: list = []
        Shell.last = self

    def later_init(self) -> None:
        self.initialised = True

    def exec_shell(self, command) -> None:
        self.commands.append(command)


@pytest.fixture()
def shell(monkeypatch):
    Shell.last = None
    monkeypatch.setattr(install_utils, "EditorWidget", EditorTab)
    monkeypatch.setattr(install_utils, "ShellManager", Shell)
    return Shell


@pytest.fixture()
def told(monkeypatch) -> list:
    """Collect what the user was told instead of opening a message box."""
    said: list = []

    class Message:
        def __init__(self, _parent=None) -> None:
            pass

        def setWindowTitle(self, title) -> None:
            self.title = title

        def setText(self, text) -> None:
            said.append(text)

        def exec(self) -> None:
            pass

    monkeypatch.setattr(install_utils, "QMessageBox", Message, raising=False)
    return said


class TestInstallingAPackage:
    def test_it_pips_with_the_interpreter_chosen_in_the_ide(self, app, shell, told):
        window = Window(EditorTab(), python_compiler="C:/envs/py313/python.exe")

        assert install_package("je_web_runner", window) is True

        assert shell.last.commands == [
            ["C:/envs/py313/python.exe", "-m", "pip", "install", "je_web_runner", "-U"]]
        assert told == []

    def test_without_a_choice_the_shells_own_interpreter_is_used(self, app, shell, told):
        window = Window(EditorTab())

        assert install_package("je_web_runner", window) is True

        assert shell.last.commands == [
            ["shell/python", "-m", "pip", "install", "je_web_runner", "-U"]]

    def test_a_source_folder_target_is_passed_through(self, app, shell, told):
        window = Window(EditorTab(), python_compiler="python")

        install_package(r"D:\src\prthinker[runner]", window)

        assert shell.last.commands[0][4] == r"D:\src\prthinker[runner]"

    def test_a_tab_that_is_not_an_editor_is_reported_not_ignored(self, app, shell, told):
        window = Window(QWidget())

        assert install_package("je_web_runner", window) is False

        assert shell.last is None
        assert told, "the user was told nothing"

"""Each automation menu's Run entries start the menu's own package, and send the report only when they say so.

The four entries of a package's Run submenu (the script, the script with the
report sent, a folder of scripts, a folder with the report sent) go through a
module of their own per package under ``extend/process_executor/``; nothing
followed an entry to the run it starts.
"""
from __future__ import annotations

import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from pybreeze.extend_multi_language.update_language_dict import update_language_dict

_MENUS = "pybreeze.pybreeze_ui.menu.automation_menu"
_EXECUTORS = "pybreeze.extend.process_executor"

# (the menu's builder, the module its entries call, the package they run)
_PACKAGES = [
    (f"{_MENUS}.api_testka_menu.build_api_testka_menu.set_apitestka_menu",
     f"{_EXECUTORS}.api_testka.api_testka_process", "je_api_testka"),
    (f"{_MENUS}.auto_control_menu.build_autocontrol_menu.set_autocontrol_menu",
     f"{_EXECUTORS}.auto_control.auto_control_process", "je_auto_control"),
    (f"{_MENUS}.automation_file_menu.build_automation_file_menu.set_automation_file_menu",
     f"{_EXECUTORS}.file_automation.file_automation_process", "automation_file"),
    (f"{_MENUS}.load_density_menu.build_load_density_menu.set_load_density_menu",
     f"{_EXECUTORS}.load_density.load_density_process", "je_load_density"),
    (f"{_MENUS}.web_runner_menu.build_webrunner_menu.set_web_runner_menu",
     f"{_EXECUTORS}.web_runner.web_runner_process", "je_web_runner"),
]


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class FakeWindow(QMainWindow):
    """A main window with the members the menu builders touch."""

    def __init__(self):
        super().__init__()
        self.automation_menu = self.menuBar().addMenu("Automation")
        self.tab_widget = QTabWidget()


@pytest.fixture
def window(app):
    fake = FakeWindow()
    yield fake
    fake.deleteLater()


def _record_runs(monkeypatch, executor: str) -> list[tuple]:
    """Stand in for the two ways *executor* starts a run; what each was asked."""
    runs: list[tuple] = []
    module = importlib.import_module(executor)
    monkeypatch.setattr(module, "build_process",
                        lambda window, package, exec_str, send, buffer: runs.append(
                            ("script", window, package, send)))
    if hasattr(module, "run_dir_files_with_package"):
        monkeypatch.setattr(module, "run_dir_files_with_package",
                            lambda window, package, send, buffer: runs.append(("folder", window, package, send)))
    return runs


def _trigger_every_run_entry(window, builder: str) -> None:
    module_name, function_name = builder.rsplit(".", 1)
    getattr(importlib.import_module(module_name), function_name)(window)
    package_menu = window.automation_menu.actions()[-1].menu()
    run_menu_action = package_menu.actions()[0]  # Run comes first
    for action in run_menu_action.menu().actions():
        action.trigger()


@pytest.mark.parametrize(("builder", "executor", "package"), _PACKAGES,
                         ids=[package for _builder, _executor, package in _PACKAGES])
def test_the_four_run_entries(window, monkeypatch, builder, executor, package):
    runs = _record_runs(monkeypatch, executor)

    _trigger_every_run_entry(window, builder)

    assert runs == [
        ("script", window, package, False),
        ("script", window, package, True),
        ("folder", window, package, False),
        ("folder", window, package, True),
    ]


def test_mail_thunder_runs_the_script_without_sending_a_report(window, monkeypatch):
    runs = _record_runs(monkeypatch, f"{_EXECUTORS}.mail_thunder.mail_thunder_process")

    _trigger_every_run_entry(window, f"{_MENUS}.mail_thunder_menu.build_mail_thunder_menu.set_mail_thunder_menu")

    assert runs == [("script", window, "je_mail_thunder", False)]

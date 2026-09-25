"""Each automation menu's Run entries start the menu's own package, and send the report only when they say so.

The four entries of a package's Run submenu (the script, the script with the
report sent, a folder of scripts, a folder with the report sent) are made by
``package_run_actions`` for each package; nothing followed an entry to the run
it starts.
"""
from __future__ import annotations

import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from pybreeze.extend_multi_language.update_language_dict import update_language_dict

_MENUS = "pybreeze.pybreeze_ui.menu.automation_menu"
_FACTORY = f"{_MENUS}.automation_menu_factory"

# (the menu's builder, the package its entries run)
_PACKAGES = [
    (f"{_MENUS}.api_testka_menu.build_api_testka_menu.set_apitestka_menu", "je_api_testka"),
    (f"{_MENUS}.auto_control_menu.build_autocontrol_menu.set_autocontrol_menu", "je_auto_control"),
    (f"{_MENUS}.automation_file_menu.build_automation_file_menu.set_automation_file_menu", "automation_file"),
    (f"{_MENUS}.load_density_menu.build_load_density_menu.set_load_density_menu", "je_load_density"),
    (f"{_MENUS}.web_runner_menu.build_webrunner_menu.set_web_runner_menu", "je_web_runner"),
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


def _record_runs(monkeypatch, *modules: str) -> list[tuple]:
    """Stand in for the two ways a run starts, where *modules* look them up; what each was asked.

    The stand-ins take what ``build_process`` and ``run_dir_files_with_package``
    take, so a call the real ones would refuse fails here too.
    """
    runs: list[tuple] = []

    def script(main_window, package, exec_str=None, send_mail=False, program_buffer=1024000):
        runs.append(("script", main_window, package, send_mail))

    def folder(main_window, package, send_mail=False, program_buffer=1024000):
        runs.append(("folder", main_window, package, send_mail))

    for name in modules:
        module = importlib.import_module(name)
        monkeypatch.setattr(module, "build_process", script)
        if hasattr(module, "run_dir_files_with_package"):
            monkeypatch.setattr(module, "run_dir_files_with_package", folder)
    return runs


def _trigger_every_run_entry(window, builder: str) -> list[str]:
    """Build the menu with *builder* and choose each Run entry in turn; their labels."""
    module_name, function_name = builder.rsplit(".", 1)
    getattr(importlib.import_module(module_name), function_name)(window)
    package_menu = window.automation_menu.actions()[-1].menu()
    run_menu_action = package_menu.actions()[0]  # Run comes first
    labels = []
    for action in run_menu_action.menu().actions():
        labels.append(action.text())
        action.trigger()
    return labels


@pytest.mark.parametrize(("builder", "package"), _PACKAGES,
                         ids=[package for _builder, package in _PACKAGES])
def test_the_four_run_entries(window, monkeypatch, builder, package):
    runs = _record_runs(monkeypatch, _FACTORY)

    labels = _trigger_every_run_entry(window, builder)

    # Each labelled from the language dictionary, none the same as another
    assert len(set(labels)) == 4 and all(labels)
    assert runs == [
        ("script", window, package, False),
        ("script", window, package, True),
        ("folder", window, package, False),
        ("folder", window, package, True),
    ]


def test_mail_thunder_runs_the_script_without_sending_a_report(window, monkeypatch):
    menu = f"{_MENUS}.mail_thunder_menu.build_mail_thunder_menu"
    runs = _record_runs(monkeypatch, _FACTORY, menu)

    _trigger_every_run_entry(window, f"{menu}.set_mail_thunder_menu")

    assert runs == [("script", window, "je_mail_thunder", False)]

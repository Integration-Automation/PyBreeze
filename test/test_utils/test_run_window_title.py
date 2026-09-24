"""A run window says what it runs: the package, and the file when there is one.

Running a folder opens one window per file, and every one was titled with the
package alone (``je_api_testka``), so nothing told them apart; the plugin run
windows already read ``Run - main.go``.
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

# A module that runs, ignores its arguments and ends at once
_PACKAGE = "this"


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def manager(app):
    from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager
    from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

    window = CodeWindow()
    runner = TaskProcessManager(window)
    runner.renew_path = lambda: True
    runner.compiler_path = sys.executable
    yield runner
    deadline = time.monotonic() + 30
    while runner.still_run_program and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    window.close()


def test_a_file_run_names_the_file(manager, tmp_path):
    manager.start_test_process_file(_PACKAGE, str(tmp_path / "login_flow.json"))
    assert manager.main_window.windowTitle() == f"{_PACKAGE} - login_flow.json"


def test_a_script_run_names_the_tab_it_came_from(manager):
    manager.start_test_process(_PACKAGE, "[]", subject="checkout.json")
    assert manager.main_window.windowTitle() == f"{_PACKAGE} - checkout.json"


def test_a_script_from_nowhere_names_the_package(manager):
    manager.start_test_process(_PACKAGE, "[]")
    assert manager.main_window.windowTitle() == _PACKAGE


def test_a_module_run_names_what_it_was_given(manager):
    manager.start_module_process(_PACKAGE, ["-e", "suite.yml"], subject="suite.yml")
    assert manager.main_window.windowTitle() == f"{_PACKAGE} - suite.yml"

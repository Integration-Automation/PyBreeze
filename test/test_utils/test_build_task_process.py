"""The run window an automation run opens: which interpreter it runs with, and where it is kept."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        try:
            app = QApplication([])
        except Exception as exc:  # pragma: no cover - no usable Qt platform
            pytest.skip(f"Cannot start QApplication: {exc}")
    return app


class MainWindow:
    """The little of the IDE's main window that opening a run window touches."""

    def __init__(self, python_compiler=None) -> None:
        self.python_compiler = python_compiler
        self.current_run_code_window: list = []
        self.encoding = "utf-8"
        self.cleared = False

    def clear_code_result(self) -> None:
        self.cleared = True


class TestBuildTaskProcess:
    def test_the_interpreter_chosen_in_the_ide_is_used(self, qt_app):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        process = build_task_process(MainWindow("C:/envs/py312/python.exe"))

        assert process.renew_path() is True
        assert process.compiler_path == "C:/envs/py312/python.exe"

    def test_without_a_choice_the_working_directory_is_searched(self, qt_app, monkeypatch):
        from pybreeze.extend.process_executor import python_task_process_manager as manager_module
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        searched: list = []
        monkeypatch.setattr(manager_module, "find_venv_path", lambda: "venv-dir")
        monkeypatch.setattr(
            manager_module, "check_and_choose_venv",
            lambda path: searched.append(path) or "found/python")

        process = build_task_process(MainWindow())

        assert process.renew_path() is True
        assert searched == ["venv-dir"]
        assert process.compiler_path == "found/python"

    def test_the_run_window_is_kept_and_the_old_result_cleared(self, qt_app):
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        main_window = MainWindow()
        process = build_task_process(main_window)

        assert main_window.current_run_code_window == [process.main_window]
        assert main_window.cleared

    def test_the_report_mail_is_sent_only_when_asked(self, qt_app):
        from pybreeze.extend.mail_thunder_extend.mail_thunder_setting import send_after_test
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        assert build_task_process(MainWindow()).task_done_trigger_function is None
        assert build_task_process(
            MainWindow(), send_mail=True).task_done_trigger_function is send_after_test

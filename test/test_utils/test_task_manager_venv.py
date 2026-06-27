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


def _raise_no_python(_path):
    from je_editor.utils.exception.exceptions import JEditorExecException
    raise JEditorExecException("no python interpreter found")


class TestRenewPathNoInterpreter:
    def test_returns_false_without_crashing(self, qt_app, monkeypatch):
        from pybreeze.extend.process_executor import python_task_process_manager as mod
        from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.python_compiler = None

        manager = TaskProcessManager.__new__(TaskProcessManager)
        manager.main_window = window

        monkeypatch.setattr(mod, "find_venv_path", lambda: "ignored")
        monkeypatch.setattr(mod, "check_and_choose_venv", _raise_no_python)

        # Must report (not raise) so the run menu callback does not crash.
        assert manager.renew_path() is False
        assert "No Python interpreter" in window.code_result.toPlainText()

    def test_returns_true_with_explicit_compiler(self, qt_app):
        from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.python_compiler = "C:/python/python.exe"

        manager = TaskProcessManager.__new__(TaskProcessManager)
        manager.main_window = window

        assert manager.renew_path() is True
        assert manager.compiler_path == "C:/python/python.exe"

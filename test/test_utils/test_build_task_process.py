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
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        assert build_task_process(MainWindow()).task_done_trigger_function is None
        assert callable(build_task_process(MainWindow(), send_mail=True).task_done_trigger_function)


class TestTheReportMailSaysHowItWent:
    """The run window tells the user whether the report went out; it was only logged."""

    @staticmethod
    def _run_the_hook(qt_app, monkeypatch, answer):
        import time

        from pybreeze.extend.mail_thunder_extend import mail_thunder_setting as mail
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        asked: list = []

        def send_report(path, *, not_before=None):
            asked.append((path, not_before))
            return answer

        monkeypatch.setattr(mail, "send_report", send_report)
        before = time.time()
        runner = build_task_process(MainWindow(), send_mail=True)
        runner.task_done_trigger_function()
        window = runner.main_window
        deadline = time.monotonic() + 10
        while "[Mail]" not in window.code_result.toPlainText() and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        return window.code_result.toPlainText(), asked, before

    def test_a_sent_report_is_reported(self, qt_app, monkeypatch):
        text, asked, before = self._run_the_hook(qt_app, monkeypatch, None)

        assert "[Mail] The test report was sent" in text
        ((path, not_before),) = asked
        # The report the child writes in the directory it starts in, from this run on
        assert os.path.isabs(path) and path.endswith("default_name.html")
        assert not_before >= before

    def test_a_report_not_sent_says_why(self, qt_app, monkeypatch):
        text, _asked, _before = self._run_the_hook(qt_app, monkeypatch, "no mail user is set")

        assert "[Mail] The test report was not sent: no mail user is set" in text

    def test_an_answer_after_the_window_is_gone_is_dropped(self, qt_app, monkeypatch):
        import threading

        from pybreeze.extend.mail_thunder_extend import mail_thunder_setting as mail
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process
        from shiboken6 import delete

        release = threading.Event()
        raised: list = []
        monkeypatch.setattr(threading, "excepthook", raised.append)
        monkeypatch.setattr(mail, "send_report", lambda _path, *, not_before=None: release.wait(5) and None)
        runner = build_task_process(MainWindow(), send_mail=True)
        runner.task_done_trigger_function()
        (mail_thread,) = [one for one in threading.enumerate() if one.name == "pybreeze-report-mail"]
        delete(runner.main_window)
        release.set()

        mail_thread.join(5)
        qt_app.processEvents()
        assert not mail_thread.is_alive()
        assert raised == []


class TestRunningWithoutAScriptTab:
    """A run takes the code from the editor tab in front; with another tab there it says so."""

    def test_a_non_editor_tab_is_reported_in_a_run_window(self, qt_app, monkeypatch):
        from PySide6.QtWidgets import QTabWidget, QWidget

        from pybreeze.extend.process_executor import process_executor_utils

        started: list = []
        monkeypatch.setattr(
            process_executor_utils, "start_process",
            lambda *args, **kwargs: started.append(args))
        main_window = MainWindow()
        main_window.tab_widget = QTabWidget()
        main_window.tab_widget.addTab(QWidget(), "tools")

        process_executor_utils.build_process(main_window, "je_api_testka")

        assert started == []
        run_window = main_window.current_run_code_window[0]
        assert "je_api_testka" in run_window.code_result.toPlainText()
        assert "editor tab in front" in run_window.code_result.toPlainText()

    def test_a_script_given_outright_runs_without_any_tab(self, qt_app, monkeypatch):
        from PySide6.QtWidgets import QTabWidget

        from pybreeze.extend.process_executor import process_executor_utils

        started: list = []
        monkeypatch.setattr(
            process_executor_utils, "start_process",
            lambda *args, **kwargs: started.append(args))
        main_window = MainWindow()
        main_window.tab_widget = QTabWidget()

        process_executor_utils.build_process(main_window, "je_api_testka", exec_str="{}")

        assert started and started[0][2] == "{}"
        assert main_window.current_run_code_window == []


class TestLettingGoOfARunWindow:
    """The main window holds every run window; a closed one whose run is over goes."""

    def test_a_closed_window_with_nothing_running_is_let_go_of(self, qt_app):
        from pybreeze.extend.process_executor.process_executor_utils import open_run_window

        main_window = MainWindow()
        run_window = open_run_window(main_window)

        run_window.close()

        assert main_window.current_run_code_window == []

    def test_a_window_whose_run_is_still_going_is_kept(self, qt_app):
        from pybreeze.extend.process_executor.process_executor_utils import open_run_window

        class StillRunning:
            class process:
                @staticmethod
                def poll():
                    return None

        main_window = MainWindow()
        run_window = open_run_window(main_window)
        run_window.runner = StillRunning()

        run_window.close()

        assert main_window.current_run_code_window == [run_window]

    def test_closing_one_window_does_not_skip_the_others(self, qt_app):
        from pybreeze.extend.process_executor.process_executor_utils import open_run_window

        main_window = MainWindow()
        windows = [open_run_window(main_window) for _ in range(3)]

        for window in tuple(main_window.current_run_code_window):
            window.close()

        assert main_window.current_run_code_window == []
        assert all(not window.isVisible() for window in windows)

    def test_a_window_let_go_of_is_freed(self, qt_app):
        # The slot that let go of it held the window, and the connection
        # belongs to the window: every closed run window, its output and its
        # executor stayed alive for as long as the IDE ran
        import gc
        import weakref

        from pybreeze.extend.process_executor.process_executor_utils import open_run_window

        main_window = MainWindow()
        run_window = open_run_window(main_window)
        watch = weakref.ref(run_window)

        run_window.close()
        del run_window
        gc.collect()

        assert main_window.current_run_code_window == []
        assert watch() is None


def test_the_mail_notice_is_freed_on_the_gui_thread(qt_app, monkeypatch):
    # Its last reference was the mail thread's: with the run window gone, the
    # QObject was destroyed on that thread, the crash class GC had caused
    import threading
    import time
    import weakref

    from pybreeze.extend.process_executor import process_executor_utils
    from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

    freed_on: list = []
    sent = threading.Event()

    def send_after_test(_path, not_before, on_done):
        def send() -> None:
            time.sleep(0.2)
            on_done(None)
            sent.set()

        threading.Thread(target=send, name="mail").start()

    monkeypatch.setattr(process_executor_utils, "send_after_test", send_after_test)
    window = CodeWindow()
    hook = process_executor_utils.report_mail_hook(window)
    notices = [cell.cell_contents for cell in hook.__closure__
               if isinstance(cell.cell_contents, process_executor_utils._MailNotice)]
    notices[0].destroyed.connect(lambda *_: freed_on.append(threading.current_thread().name))
    watch = weakref.ref(notices[0])
    del notices

    hook()
    del hook
    window.close()
    window.deleteLater()
    del window
    assert sent.wait(5)
    deadline = time.monotonic() + 5
    while not freed_on and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    assert freed_on == [threading.main_thread().name]
    assert watch() is None or not __import__("shiboken6").isValid(watch())

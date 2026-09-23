from __future__ import annotations

import os
import time
import weakref
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox
from je_editor import EditorWidget, language_wrapper

from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.extend.mail_thunder_extend.mail_thunder_setting import DEFAULT_REPORT_PATH, send_after_test
from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager
from pybreeze.utils.file_process.get_dir_file_list import get_dir_files_as_list
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.pybreeze_ui.plain_text import as_text

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def build_process(
        main_window: PyBreezeMainWindow,
        package: str,
        exec_str: str | None = None,
        send_mail: bool = False,
        program_buffer: int = 1024000,
):
    """Run *package* against a script: *exec_str*, or the code in the tab in front.

    The script is handed to the package as written; the package parses it and
    reports its own errors in the run window.
    """
    test_format_code = exec_str
    if test_format_code is None:
        widget = main_window.tab_widget.currentWidget()
        if not isinstance(widget, EditorWidget):
            report_no_script_tab(main_window, package, program_buffer)
            return
        test_format_code = widget.code_edit.toPlainText()
    start_process(main_window, package, test_format_code, send_mail, program_buffer)


def report_no_script_tab(
        main_window: PyBreezeMainWindow, package: str, program_buffer: int = 1024000) -> None:
    """Open a run window saying the run needs the script's tab in front.

    A run takes the code from the editor tab in front. With another kind of tab
    there -- a tool tab, the diagram editor, a run window -- the package used to
    be handed nothing and answered with a parse error of its own.
    """
    pybreeze_logger.error("%s run needs an editor tab in front", package)
    process = build_task_process(main_window, program_buffer=program_buffer)
    process.main_window.append_output(
        f"[Error] {package} runs the script in the editor tab in front; open it and try again\n",
        is_error=True, own_line=True)
    process.main_window.show()


def start_process(
        main_window: PyBreezeMainWindow,
        package: str,
        test_format_code: str,
        send_mail: bool = False,
        program_buffer: int = 1024000
):
    process = build_task_process(main_window, send_mail, program_buffer)
    process.start_test_process(
        package,
        exec_str=test_format_code,
    )


def build_process_from_file(
        main_window: PyBreezeMainWindow,
        package: str,
        file_path: str,
        send_mail: bool = False,
        program_buffer: int = 1024000,
        then: Callable[[], None] | None = None,
) -> TaskProcessManager:
    """Run ``package`` against an action JSON file path; return the run's manager.

    Bypasses the ``--execute_str`` cmdline path so large scripts cannot trip
    the Windows ~32K argv limit. Useful for batch / multi-file flows where
    the file is already on disk. *then* is called when the run has ended.
    """
    process = build_task_process(main_window, send_mail, program_buffer, then=then)
    process.start_test_process_file(package, file_path)
    return process


def run_dir_files_with_package(
        main_window: PyBreezeMainWindow,
        package: str,
        send_mail: bool = False,
        program_buffer: int = 1024000,
) -> None:
    """Prompt for a directory and run every matching file through *package*, one after another.

    Each file is executed via its on-disk path (``--execute_file``) so large
    action JSON never trips the Windows ~32K command-line limit, and one run
    window is opened per file, which reports that file's run, a run that cannot
    start included. The broad guard here only keeps a single bad directory pick
    from crashing the menu callback.

    They used to start all at once: every run writes its report to the same
    ``default_name.html``, so the reports overwrote one another and a run's
    mail could carry another run's report, and N browsers opened together.
    """
    try:
        execute_list = _ask_for_action_files(main_window)
        if not execute_list:
            return
        run_one_after_another(main_window, package, list(execute_list), send_mail, program_buffer)
    except Exception as error:  # noqa: BLE001 — batch UI action must not abort on one bad entry
        pybreeze_logger.error("%s multi file error: %r", package, error)


def run_one_after_another(
        main_window: PyBreezeMainWindow, package: str, files: list[str],
        send_mail: bool = False, program_buffer: int = 1024000) -> None:
    """Run *files* through *package*, each in its own window once the one before has ended.

    A run that was stopped (its Stop, or the IDE closing) ends the batch; a
    file whose run could not start is passed over.
    """
    if not files:
        return
    first, rest = files[0], files[1:]
    process: TaskProcessManager | None = None

    def next_file() -> None:
        if process is not None and process.was_stopped:
            return
        run_one_after_another(main_window, package, rest, send_mail, program_buffer)

    process = build_process_from_file(main_window, package, first, send_mail, program_buffer, then=next_file)
    if process.process is None:
        # It never started, so it never ends: go on from the event loop
        QTimer.singleShot(0, next_file)


def _ask_for_action_files(main_window: PyBreezeMainWindow) -> list[str]:
    """Ask for a folder and return the action JSON files under it, none when cancelled.

    The dialog is parented to the main window (it was not, and could open
    behind it). A folder with no JSON in it says so; it used to do nothing.
    """
    folder = QFileDialog.getExistingDirectory(main_window)
    if not folder:
        return []
    files = get_dir_files_as_list(folder, ".json")
    if not files:
        lang = language_wrapper.language_word_dict
        QMessageBox.information(
            main_window, lang.get("run_folder_title"),
            as_text(lang.get("run_folder_no_action_files").format(folder=folder)))
    return files


def open_run_window(main_window: PyBreezeMainWindow, title: str = "") -> CodeWindow:
    """Open a run window and keep it on the main window until it is closed.

    The main window holds every run window (that is what stops the runs when
    it closes) and lets go of one that the user closes once its run is over.

    :param main_window: the main window
    :param title: the window's title, when it has one of its own
    :return: the run window
    """
    code_window = CodeWindow()
    if title:
        code_window.setWindowTitle(title)
    main_window.current_run_code_window.append(code_window)
    # Weakly: the connection belongs to the window, so a slot holding the
    # window itself kept every closed run window, with its output and its
    # executor, alive for as long as the IDE ran
    window_ref = weakref.ref(code_window)
    code_window.finished_and_closed.connect(lambda: _forget_if_alive(main_window, window_ref))
    return code_window


def _forget_if_alive(main_window: PyBreezeMainWindow, window_ref: weakref.ref) -> None:
    """``forget_run_window`` for the window *window_ref* points at, if it still exists."""
    code_window = window_ref()
    if code_window is not None:
        forget_run_window(main_window, code_window)


def forget_run_window(main_window: PyBreezeMainWindow, code_window: CodeWindow) -> None:
    """Drop *code_window* from the main window's list, if it is still there."""
    if code_window in main_window.current_run_code_window:
        main_window.current_run_code_window.remove(code_window)


class _MailNotice(QObject):
    """Carries the mail thread's answer to the run window, on the UI thread."""

    told = Signal(str, bool)

    def tell(self, reason: str | None) -> None:
        """Called on the mail thread with ``send_report``'s answer."""
        if reason is None:
            self.told.emit("[Mail] The test report was sent\n", False)
        else:
            self.told.emit(f"[Mail] The test report was not sent: {reason}\n", True)


def report_mail_hook(code_window: CodeWindow) -> Callable[[], None]:
    """The done-hook that mails this run's report and says in *code_window* how that went.

    Made as the run starts, so it knows where the child writes its report (the
    working directory it starts in) and when it started: a report older than
    the run is an earlier run's, and is not sent. The mail used to go out, or
    fail, with nothing but a log line to say so.
    """
    report_path = os.path.abspath(DEFAULT_REPORT_PATH)
    started = time.time()
    # Owned by the application, not the window: the mail thread may answer
    # after the window is gone (its queued connection to the window goes with
    # the window). Without a C++ owner, the mail thread's closure held the last
    # reference, and the QObject was destroyed on that thread when it ended.
    # It is deleted on the GUI thread once its answer has been delivered there.
    notice = _MailNotice(QCoreApplication.instance())
    notice.told.connect(code_window.append_output)
    notice.told.connect(notice.deleteLater)

    def mail_the_report() -> None:
        send_after_test(report_path, not_before=started, on_done=notice.tell)

    return mail_the_report


def build_task_process(
        main_window: PyBreezeMainWindow,
        send_mail: bool = False,
        program_buffer: int = 1024000,
        then: Callable[[], None] | None = None,
) -> TaskProcessManager:
    """Open a fresh run window and the task process manager that writes to it.

    *then* is called when the run has ended, after the report mail is started.

    The run window carries the interpreter chosen in the IDE (the Python
    environment menu, or the saved setting), so the child runs with that
    interpreter; only when none was chosen does the manager fall back to a
    ``venv`` / ``.venv`` in the working directory, then to ``PATH``. The run
    window holds the manager (``CodeWindow.runner``), so a caller may drop it.
    """
    code_window = open_run_window(main_window)
    code_window.python_compiler = main_window.python_compiler
    main_window.clear_code_result()
    hooks = [hook for hook in (report_mail_hook(code_window) if send_mail else None, then) if hook]
    code_window.runner = TaskProcessManager(
        code_window,
        task_done_trigger_function=_one_after_another(hooks) if hooks else None,
        program_buffer_size=program_buffer,
        program_encoding=main_window.encoding,
    )
    return code_window.runner


def _one_after_another(hooks: list[Callable[[], None]]) -> Callable[[], None]:
    """One done-hook that calls each of *hooks* in turn."""
    def call_each() -> None:
        for hook in hooks:
            hook()
    return call_each

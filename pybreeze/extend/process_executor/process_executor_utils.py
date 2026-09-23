from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox
from je_editor import EditorWidget, language_wrapper

from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.extend.mail_thunder_extend.mail_thunder_setting import DEFAULT_REPORT_PATH, send_after_test
from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager
from pybreeze.utils.exception.exception_tags import wrong_test_data_format_exception_tag
from pybreeze.utils.exception.exceptions import ITETestExecutorException
from pybreeze.utils.file_process.get_dir_file_list import get_dir_files_as_list
from pybreeze.utils.logging.logger import pybreeze_logger

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def build_process(
        main_window: PyBreezeMainWindow,
        package: str,
        exec_str: str | None = None,
        send_mail: bool = False,
        program_buffer: int = 1024000,
):
    """Run *package* against a script: *exec_str*, or the code in the tab in front."""
    try:
        test_format_code = exec_str
        if test_format_code is None:
            widget = main_window.tab_widget.currentWidget()
            if not isinstance(widget, EditorWidget):
                report_no_script_tab(main_window, package, program_buffer)
                return
            test_format_code = widget.code_edit.toPlainText()
        start_process(main_window, package, test_format_code, send_mail, program_buffer)
    except json.decoder.JSONDecodeError as error:
        pybreeze_logger.error(f"{error!r}\n{wrong_test_data_format_exception_tag}")
    except ITETestExecutorException as error:
        pybreeze_logger.error(repr(error))


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
):
    """Run ``package`` against an action JSON file path.

    Bypasses the ``--execute_str`` cmdline path so large scripts cannot trip
    the Windows ~32K argv limit. Useful for batch / multi-file flows where
    the file is already on disk.
    """
    try:
        process = build_task_process(main_window, send_mail, program_buffer)
        process.start_test_process_file(package, file_path)
    except ITETestExecutorException as error:
        pybreeze_logger.error(repr(error))


def run_dir_files_with_package(
        main_window: PyBreezeMainWindow,
        package: str,
        send_mail: bool = False,
        program_buffer: int = 1024000,
) -> None:
    """Prompt for a directory and run every matching file through *package*.

    Each file is executed via its on-disk path (``--execute_file``) so large
    action JSON never trips the Windows ~32K command-line limit, and one run
    window is opened per file. ``build_process_from_file`` already logs and
    contains per-file executor errors; the broad guard here only keeps a single
    bad directory pick from crashing the menu callback.
    """
    try:
        execute_list = _ask_for_action_files(main_window)
        if not execute_list:
            return
        for execute_file in execute_list:
            build_process_from_file(main_window, package, execute_file, send_mail, program_buffer)
    except Exception as error:  # noqa: BLE001 — batch UI action must not abort on one bad entry
        pybreeze_logger.error("%s multi file error: %r", package, error)


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
            lang.get("run_folder_no_action_files").format(folder=folder))
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
    code_window.finished_and_closed.connect(
        lambda: forget_run_window(main_window, code_window))
    return code_window


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
    # No parent: the mail thread may answer after the window is gone. Its
    # queued connection to the window is dropped with the window.
    notice = _MailNotice()
    notice.told.connect(code_window.append_output)

    def mail_the_report() -> None:
        send_after_test(report_path, not_before=started, on_done=notice.tell)

    return mail_the_report


def build_task_process(
        main_window: PyBreezeMainWindow,
        send_mail: bool = False,
        program_buffer: int = 1024000,
) -> TaskProcessManager:
    """Open a fresh run window and the task process manager that writes to it.

    The run window carries the interpreter chosen in the IDE (the Python
    environment menu, or the saved setting), so the child runs with that
    interpreter; only when none was chosen does the manager fall back to a
    ``venv`` / ``.venv`` in the working directory, then to ``PATH``. The run
    window holds the manager (``CodeWindow.runner``), so a caller may drop it.
    """
    code_window = open_run_window(main_window)
    code_window.python_compiler = main_window.python_compiler
    main_window.clear_code_result()
    code_window.runner = TaskProcessManager(
        code_window,
        task_done_trigger_function=report_mail_hook(code_window) if send_mail else None,
        program_buffer_size=program_buffer,
        program_encoding=main_window.encoding,
    )
    return code_window.runner

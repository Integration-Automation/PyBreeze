from __future__ import annotations

import json
from typing import TYPE_CHECKING

from je_editor import EditorWidget

from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.extend.mail_thunder_extend.mail_thunder_setting import send_after_test
from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager
from pybreeze.utils.exception.exception_tags import wrong_test_data_format_exception_tag
from pybreeze.utils.exception.exceptions import ITETestExecutorException
from pybreeze.utils.file_process.get_dir_file_list import ask_and_get_dir_files_as_list
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
    try:
        widget = main_window.tab_widget.currentWidget()
        if isinstance(widget, EditorWidget) and exec_str is None:
            test_format_code = widget.code_edit.toPlainText()
        else:
            test_format_code = exec_str
        start_process(main_window, package, test_format_code, send_mail, program_buffer)
    except json.decoder.JSONDecodeError as error:
        pybreeze_logger.error(f"{error!r}\n{wrong_test_data_format_exception_tag}")
    except ITETestExecutorException as error:
        pybreeze_logger.error(repr(error))


def start_process(
        main_window: PyBreezeMainWindow,
        package: str,
        test_format_code: str,
        send_mail: bool = False,
        program_buffer: int = 1024000
):
    process = _build_task_process(main_window, send_mail, program_buffer)
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
        process = _build_task_process(main_window, send_mail, program_buffer)
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
        execute_list = ask_and_get_dir_files_as_list(main_window)
        if not execute_list:
            return
        for execute_file in execute_list:
            build_process_from_file(main_window, package, execute_file, send_mail, program_buffer)
    except Exception as error:  # noqa: BLE001 — batch UI action must not abort on one bad entry
        pybreeze_logger.error("%s multi file error: %r", package, error)


def _build_task_process(
        main_window: PyBreezeMainWindow,
        send_mail: bool,
        program_buffer: int,
) -> TaskProcessManager:
    code_window = CodeWindow()
    main_window.current_run_code_window.append(code_window)
    main_window.clear_code_result()
    if send_mail:
        return TaskProcessManager(
            main_window=code_window,
            task_done_trigger_function=send_after_test,
            program_buffer_size=program_buffer,
            program_encoding=main_window.encoding,
        )
    return TaskProcessManager(
        code_window,
        program_buffer_size=program_buffer,
        program_encoding=main_window.encoding,
    )

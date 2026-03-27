from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Union

from je_editor import EditorWidget

from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.extend.mail_thunder_extend.mail_thunder_setting import send_after_test
from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager
from pybreeze.utils.exception.exception_tags import wrong_test_data_format_exception_tag
from pybreeze.utils.exception.exceptions import ITETestExecutorException

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def build_process(
        main_window: PyBreezeMainWindow,
        package: str,
        exec_str: Union[str, None] = None,
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
        print(
            repr(error) +
            "\n"
            + wrong_test_data_format_exception_tag,
            file=sys.stderr
        )
    except ITETestExecutorException as error:
        print(repr(error), file=sys.stderr)


def start_process(
        main_window: PyBreezeMainWindow,
        package: str,
        test_format_code: str,
        send_mail: bool = False,
        program_buffer: int = 1024000
):
    # Code window init
    code_window = CodeWindow()
    main_window.current_run_code_window.append(code_window)
    main_window.clear_code_result()
    # Process init
    if send_mail:
        process = TaskProcessManager(
            main_window=code_window,
            program_buffer_size=program_buffer,
            program_encoding=main_window.encoding
        )
    else:
        process = TaskProcessManager(
            code_window,
            task_done_trigger_function=send_after_test,
            program_buffer_size=program_buffer,
            program_encoding=main_window.encoding
        )
    process.start_test_process(
        package,
        exec_str=test_format_code,
    )

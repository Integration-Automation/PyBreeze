from __future__ import annotations

from typing import TYPE_CHECKING, Union

from pybreeze.extend.process_executor.process_executor_utils import build_process

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow
import sys

from pybreeze.utils.file_process.get_dir_file_list import ask_and_get_dir_files_as_list


def call_load_density(
        main_window: PyBreezeMainWindow,
        exec_str: Union[str, None] = None,
        program_buffer: int = 1024000
):
    build_process(main_window, "je_load_density", exec_str, False, program_buffer)


def call_load_density_with_send(
        main_window: PyBreezeMainWindow,
        exec_str: Union[str, None] = None,
        program_buffer: int = 1024000
):
    build_process(main_window, "je_load_density", exec_str, True, program_buffer)


def call_load_density_multi_file(
        main_window: PyBreezeMainWindow,
        program_buffer: int = 1024000
):
    try:
        need_to_execute_list: list = ask_and_get_dir_files_as_list(main_window)
        if need_to_execute_list is not None and isinstance(need_to_execute_list, list) and len(
                need_to_execute_list) > 0:
            for execute_file in need_to_execute_list:
                with open(execute_file, "r") as test_script_json:
                    call_load_density(
                        main_window,
                        test_script_json.read(),
                        program_buffer
                    )
    except Exception as error:
        print(repr(error), file=sys.stderr)


def call_load_density_multi_file_and_send(
        main_window: PyBreezeMainWindow,
        program_buffer: int = 1024000
):
    try:

        need_to_execute_list: list = ask_and_get_dir_files_as_list(main_window)
        if need_to_execute_list is not None and isinstance(need_to_execute_list, list) and len(
                need_to_execute_list) > 0:
            for execute_file in need_to_execute_list:
                with open(execute_file, "r") as test_script_json:
                    call_load_density_with_send(
                        main_window,
                        test_script_json.read(),
                        program_buffer
                    )
    except Exception as error:
        print(repr(error), file=sys.stderr)

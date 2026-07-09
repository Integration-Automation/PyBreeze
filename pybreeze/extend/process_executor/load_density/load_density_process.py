from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.extend.process_executor.process_executor_utils import (
    build_process, run_dir_files_with_package,
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

_PACKAGE = "je_load_density"


def call_load_density(
        main_window: PyBreezeMainWindow,
        exec_str: str | None = None,
        program_buffer: int = 1024000
):
    build_process(main_window, _PACKAGE, exec_str, False, program_buffer)


def call_load_density_with_send(
        main_window: PyBreezeMainWindow,
        exec_str: str | None = None,
        program_buffer: int = 1024000
):
    build_process(main_window, _PACKAGE, exec_str, True, program_buffer)


def call_load_density_multi_file(
        main_window: PyBreezeMainWindow,
        program_buffer: int = 1024000
):
    run_dir_files_with_package(main_window, _PACKAGE, False, program_buffer)


def call_load_density_multi_file_and_send(
        main_window: PyBreezeMainWindow,
        program_buffer: int = 1024000
):
    run_dir_files_with_package(main_window, _PACKAGE, True, program_buffer)

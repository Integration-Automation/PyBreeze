from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.extend.process_executor.process_executor_utils import build_task_process

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

_PACKAGE = "test_pioneer"


def init_and_start_test_pioneer_process(
        ui_we_want_to_set: PyBreezeMainWindow, file_path: str, program_buffer: int = 1024000) -> None:
    """Run ``python -m test_pioneer -e <yaml>`` in a new run window.

    It goes through the same task process manager as the other automation
    packages, so a missing interpreter is reported in the run window rather
    than raised out of the menu callback.
    """
    process = build_task_process(ui_we_want_to_set, program_buffer=program_buffer)
    process.start_module_process(_PACKAGE, ["-e", file_path])

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from pybreeze.extend.process_executor.process_executor_utils import build_process

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import AutomationEditor


def call_mail_thunder(
        main_window: AutomationEditor,
        exec_str: Union[str, None] = None,
        program_buffer: int = 1024000
):
    build_process(main_window, "je_mail_thunder", exec_str, False, program_buffer)

"""
把程式碼審查交給 prthinker 跑
Hand a code review to prthinker and run it.

審查在子行程裡進行，輸出即時流進一個執行視窗——和其他自動化工具一樣，不會卡住編輯器。
The review runs in a child process and its output streams into a run window, the
same as the other automation tools, so the editor never waits on it.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from je_editor import EditorWidget

from pybreeze.extend.prthinker_extend.prthinker_setting import (
    PRTHINKER_PACKAGE, environment_for, load_setting, review_file_arguments,
    review_pr_arguments
)
from pybreeze.extend.process_executor.process_executor_utils import DEFAULT_PROGRAM_BUFFER, build_task_process
from pybreeze.utils.logging.logger import pybreeze_logger

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def review_current_file(
        main_window: PyBreezeMainWindow, program_buffer: int = DEFAULT_PROGRAM_BUFFER) -> bool:
    """
    審查目前分頁的檔案
    Review the file in the current tab.

    檔案得先存起來：審查看的是磁碟上的內容，未存檔的編輯不會被讀到。
    The file has to have been saved: the review reads what is on disk, so an
    unsaved edit would not be part of it.

    :param main_window: 主視窗 / the main window
    :param program_buffer: 輸出緩衝大小 / the output buffer's size
    :return: 是否真的開始審查 / whether a review actually started
    """
    widget = main_window.tab_widget.currentWidget()
    file_path = getattr(widget, "current_file", None) if isinstance(
        widget, EditorWidget) else None
    if not file_path or not Path(file_path).is_file():
        pybreeze_logger.error("prthinker review needs a saved file in the current tab")
        return False
    setting = load_setting()
    return _run(
        main_window, review_file_arguments(file_path, setting), setting, program_buffer)


def review_pull_request(
        main_window: PyBreezeMainWindow, pull_request_number: int,
        program_buffer: int = DEFAULT_PROGRAM_BUFFER) -> bool:
    """
    審查一個 Pull Request
    Review one pull request.

    :param main_window: 主視窗 / the main window
    :param pull_request_number: PR 或 MR 的編號 / the pull request's number
    :param program_buffer: 輸出緩衝大小 / the output buffer's size
    :return: 是否真的開始審查 / whether a review actually started
    """
    setting = load_setting()
    if not setting.get("repository", "").strip():
        pybreeze_logger.error("prthinker review-pr needs a repository in the settings")
        return False
    return _run(
        main_window, review_pr_arguments(pull_request_number, setting),
        setting, program_buffer)


def _run(main_window: PyBreezeMainWindow, arguments: list[str],
         setting: dict, program_buffer: int) -> bool:
    """開一個執行視窗把 prthinker 跑起來 / Open a run window and start prthinker in it."""
    process = build_task_process(main_window, program_buffer=program_buffer)
    process.start_module_process(
        PRTHINKER_PACKAGE, arguments, environment_for(setting))
    return True

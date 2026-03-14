from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path
from queue import Queue
from typing import TYPE_CHECKING, Union

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCharFormat
from PySide6.QtWidgets import QWidget
from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict
from je_editor.utils.venv_check.check_venv import check_and_choose_venv

from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import AutomationEditor


class TestPioneerProcess(object):

    def __init__(
            self,
            main_window: AutomationEditor,
            executable_path: str,
            program_buffer: int = 1024000,
            encoding: str = "utf-8",
    ):
        self._main_window: AutomationEditor = main_window
        self._widget: QWidget = main_window.tab_widget.currentWidget()
        # Code window init
        self._code_window = CodeWindow()
        self._main_window.current_run_code_window.append(self._code_window)
        self._main_window.clear_code_result()
        self._still_run_program: bool = False
        self._program_buffer_size = program_buffer
        self._run_output_queue: Queue = Queue()
        self._run_error_queue: Queue = Queue()
        self._read_program_error_output_from_thread: Union[threading.Thread, None] = None
        self._read_program_output_from_thread: Union[threading.Thread, None] = None
        self._timer: QTimer = QTimer(self._code_window)
        if self._main_window.python_compiler is None:
            # Renew compiler path
            if sys.platform in ["win32", "cygwin", "msys"]:
                venv_path = Path(str(Path.cwd()) + "/venv/Scripts")
            else:
                venv_path = Path(str(Path.cwd()) + "/venv/bin")
            self._compiler_path = check_and_choose_venv(venv_path)
        else:
            self._compiler_path = main_window.python_compiler
        if sys.platform in ["win32", "cygwin", "msys"]:
            args = [
                self._compiler_path,
                "-m",
                "test_pioneer",
                "-e",
                executable_path
            ]
        else:
            args = " ".join([
                f"{self._compiler_path}", "-m test_pioneer", "-e", f"{executable_path}"
            ])
        self._process: subprocess.Popen = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            encoding=encoding
        )

    # Pyside UI update method
    def pull_text(self):
        try:
            if not self._run_output_queue.empty():
                output_message = self._run_output_queue.get_nowait()
                output_message = str(output_message).strip()
                if output_message:
                    text_cursor = self._code_window.code_result.textCursor()
                    text_format = QTextCharFormat()
                    text_format.setForeground(actually_color_dict.get("normal_output_color"))
                    text_cursor.insertText(output_message, text_format)
                    text_cursor.insertBlock()
            if not self._run_error_queue.empty():
                error_message = self._run_error_queue.get_nowait()
                error_message = str(error_message).strip()
                if error_message:
                    text_cursor = self._code_window.code_result.textCursor()
                    text_format = QTextCharFormat()
                    text_format.setForeground(actually_color_dict.get("error_output_color"))
                    text_cursor.insertText(error_message, text_format)
                    text_cursor.insertBlock()
        except queue.Empty:
            pass
        if self._process is not None:
            if self._process.returncode == 0:
                if self._timer.isActive():
                    self._timer.stop()
                self.exit_program()
            elif self._process.returncode is not None:
                if self._timer.isActive():
                    self._timer.stop()
                self.exit_program()
            if self._still_run_program:
                # poll return code
                self._process.poll()
        else:
            if self._timer.isActive():
                self._timer.stop()

    # exit program change run flag to false and clean read thread and queue and process
    def exit_program(self):
        self._still_run_program = False
        if self._read_program_output_from_thread is not None:
            self._read_program_output_from_thread = None
        if self._read_program_error_output_from_thread is not None:
            self._read_program_error_output_from_thread = None
        self.print_and_clear_queue()
        if self._process is not None:
            self._process.terminate()
            text_cursor = self._code_window.code_result.textCursor()
            text_format = QTextCharFormat()
            text_format.setForeground(actually_color_dict.get("normal_output_color"))
            text_cursor.insertText(f"Task exit with code {self._process.returncode}", text_format)
            text_cursor.insertBlock()
            self._process = None

    def print_and_clear_queue(self):
        self._run_output_queue = queue.Queue()
        self._run_error_queue = queue.Queue()

    def read_program_output_from_process(self):
        while self._still_run_program:
            self.process: subprocess.Popen
            program_output_data = self._process.stdout.readline(self._program_buffer_size) \
                .decode("utf-8", "replace")
            if self._process:
                self._process.stdout.flush()
            if program_output_data.strip() != "":
                self._run_output_queue.put(program_output_data)

    def read_program_error_output_from_process(self):
        while self._still_run_program:
            program_error_output_data = self._process.stderr.readline(self._program_buffer_size) \
                .decode("utf-8", "replace")
            if self._process:
                self._process.stderr.flush()
            if program_error_output_data.strip() != "":
                self._run_error_queue.put(program_error_output_data)

    def start_test_pioneer_process(self):
        self._still_run_program = True
        # program output message queue thread
        self._read_program_output_from_thread = threading.Thread(
            target=self.read_program_output_from_process,
            daemon=True
        )
        self._read_program_output_from_thread.start()
        # program error message queue thread
        self._read_program_error_output_from_thread = threading.Thread(
            target=self.read_program_error_output_from_process,
            daemon=True
        )
        self._read_program_error_output_from_thread.start()
        # start Pyside update
        # start timer
        self._code_window.setWindowTitle("Test Pioneer")
        self._code_window.show()
        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.pull_text)
        self._timer.start()


def init_and_start_test_pioneer_process(ui_we_want_to_set: AutomationEditor, file_path: str):
    test_pioneer_process_manager = TestPioneerProcess(
        main_window=ui_we_want_to_set, executable_path=file_path)
    test_pioneer_process_manager.start_test_pioneer_process()

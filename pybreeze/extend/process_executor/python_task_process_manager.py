from __future__ import annotations

import queue
import subprocess
import sys
import threading
import typing
from pathlib import Path
from queue import Queue
from threading import Thread


from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCharFormat
from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict
from je_editor.utils.venv_check.check_venv import check_and_choose_venv

from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow


class TaskProcessManager:
    def __init__(
            self,
            main_window: CodeWindow,
            task_done_trigger_function: typing.Callable | None = None,
            error_trigger_function: typing.Callable | None = None,
            program_buffer_size: int = 1024,
            program_encoding: str = "utf-8"
    ):
        super().__init__()
        self.compiler_path = None
        # ite_instance param
        self.read_program_error_output_from_thread: threading.Thread | None = None
        self.read_program_output_from_thread: threading.Thread | None = None
        self.main_window: CodeWindow = main_window
        self.timer: QTimer = QTimer(self.main_window)
        self.still_run_program: bool = True
        self.program_encoding: str = program_encoding
        self.run_output_queue: Queue = Queue()
        self.run_error_queue: Queue = Queue()
        self.process: subprocess.Popen | None = None

        self.task_done_trigger_function: typing.Callable = task_done_trigger_function
        self.error_trigger_function: typing.Callable = error_trigger_function
        self.program_buffer_size = program_buffer_size

    def renew_path(self) -> None:
        if self.main_window.python_compiler is None:
            # Renew compiler path
            if sys.platform in ["win32", "cygwin", "msys"]:
                venv_path = Path(str(Path.cwd()) + "/venv/Scripts")
            else:
                venv_path = Path(str(Path.cwd()) + "/venv/bin")
            self.compiler_path = check_and_choose_venv(venv_path)
        else:
            self.compiler_path = self.main_window.python_compiler

    def start_test_process(self, package: str, exec_str: str):
        self.renew_path()
        if sys.platform in ["win32", "cygwin", "msys"]:
            exec_str = __import__("json").dumps(exec_str)
        args = [
            str(self.compiler_path),
            "-m",
            package,
            "--execute_str",
            exec_str
        ]
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.still_run_program = True
        # program output message queue thread
        self.read_program_output_from_thread = Thread(
            target=self.read_program_output_from_process,
            daemon=True
        )
        self.read_program_output_from_thread.start()
        # program error message queue thread
        self.read_program_error_output_from_thread = Thread(
            target=self.read_program_error_output_from_process,
            daemon=True
        )
        self.read_program_error_output_from_thread.start()
        # start Pyside update
        # start timer
        self.main_window.setWindowTitle(package)
        self.main_window.show()
        self.timer = QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.pull_text)
        self.timer.start()

    # Pyside UI update method
    def pull_text(self):
        try:
            if not self.run_output_queue.empty():
                output_message = self.run_output_queue.get_nowait()
                output_message = str(output_message).strip()
                if output_message:
                    text_cursor = self.main_window.code_result.textCursor()
                    text_format = QTextCharFormat()
                    text_format.setForeground(actually_color_dict.get("normal_output_color"))
                    text_cursor.insertText(output_message, text_format)
                    text_cursor.insertBlock()
            if not self.run_error_queue.empty():
                error_message = self.run_error_queue.get_nowait()
                error_message = str(error_message).strip()
                if error_message:
                    text_cursor = self.main_window.code_result.textCursor()
                    text_format = QTextCharFormat()
                    text_format.setForeground(actually_color_dict.get("error_output_color"))
                    text_cursor.insertText(error_message, text_format)
                    text_cursor.insertBlock()
        except queue.Empty:
            pass
        if self.process is not None:
            if self.process.returncode == 0:
                if self.timer.isActive():
                    self.timer.stop()
                self.exit_program()
            elif self.process.returncode is not None:
                if self.timer.isActive():
                    self.timer.stop()
                self.exit_program()
            if self.still_run_program:
                # poll return code
                self.process.poll()
        else:
            if self.timer.isActive():
                self.timer.stop()

    # exit program change run flag to false and clean read thread and queue and process
    def exit_program(self):
        self.still_run_program = False
        if self.read_program_output_from_thread is not None:
            self.read_program_output_from_thread = None
        if self.read_program_error_output_from_thread is not None:
            self.read_program_error_output_from_thread = None
        self.drain_and_display_queue()
        if self.process is not None:
            self.process.terminate()
            text_cursor = self.main_window.code_result.textCursor()
            text_format = QTextCharFormat()
            text_format.setForeground(actually_color_dict.get("normal_output_color"))
            text_cursor.insertText(f"Task exit with code {self.process.returncode}", text_format)
            text_cursor.insertBlock()
            self.process = None
        if self.task_done_trigger_function is not None:
            try:
                self.task_done_trigger_function()
            except Exception as e:
                print(repr(e), file=sys.stderr)

    def drain_and_display_queue(self):
        while not self.run_output_queue.empty():
            try:
                output_message = self.run_output_queue.get_nowait()
                output_message = str(output_message).strip()
                if output_message:
                    text_cursor = self.main_window.code_result.textCursor()
                    text_format = QTextCharFormat()
                    text_format.setForeground(actually_color_dict.get("normal_output_color"))
                    text_cursor.insertText(output_message, text_format)
                    text_cursor.insertBlock()
            except queue.Empty:
                break
        while not self.run_error_queue.empty():
            try:
                error_message = self.run_error_queue.get_nowait()
                error_message = str(error_message).strip()
                if error_message:
                    text_cursor = self.main_window.code_result.textCursor()
                    text_format = QTextCharFormat()
                    text_format.setForeground(actually_color_dict.get("error_output_color"))
                    text_cursor.insertText(error_message, text_format)
                    text_cursor.insertBlock()
            except queue.Empty:
                break

    def read_program_output_from_process(self):
        while self.still_run_program:
            proc = self.process
            if proc is None:
                break
            program_output_data = proc.stdout.readline(self.program_buffer_size)
            if isinstance(program_output_data, bytes):
                program_output_data = program_output_data.decode(self.program_encoding, "replace")
            if program_output_data.strip():
                self.run_output_queue.put(program_output_data)

    def read_program_error_output_from_process(self):
        while self.still_run_program:
            proc = self.process
            if proc is None:
                break
            program_error_output_data = proc.stderr.readline(self.program_buffer_size)
            if isinstance(program_error_output_data, bytes):
                program_error_output_data = program_error_output_data.decode(self.program_encoding, "replace")
            if program_error_output_data.strip():
                self.run_error_queue.put(program_error_output_data)

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from typing import Callable
from pathlib import Path
from queue import Queue
from threading import Thread

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCharFormat
from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict
from je_editor.utils.exception.exceptions import JEditorExecException
from je_editor.utils.venv_check.check_venv import check_and_choose_venv

from pybreeze.extend.process_executor.queue_pump import pump_message_queue
from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.subprocess_util import no_window_creationflags, utf8_subprocess_env


def find_venv_path() -> Path:
    """Find virtual environment path, checking multiple common locations."""
    if sys.platform in ["win32", "cygwin", "msys"]:
        candidates = [
            Path.cwd() / "venv" / "Scripts",
            Path.cwd() / ".venv" / "Scripts",
        ]
    else:
        candidates = [
            Path.cwd() / "venv" / "bin",
            Path.cwd() / ".venv" / "bin",
        ]
    for path in candidates:
        if path.exists():
            return path
    # Fallback to first candidate
    return candidates[0]


class TaskProcessManager:
    def __init__(
            self,
            main_window: CodeWindow,
            task_done_trigger_function: Callable | None = None,
            error_trigger_function: Callable | None = None,
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

        self.task_done_trigger_function: Callable = task_done_trigger_function
        self.error_trigger_function: Callable = error_trigger_function
        self.program_buffer_size = program_buffer_size

    def renew_path(self) -> bool:
        """Resolve the interpreter path. Returns False (without raising) when no
        Python can be found, surfacing the error in the run window instead of
        crashing the menu callback."""
        if self.main_window.python_compiler is None:
            venv_path = find_venv_path()
            try:
                self.compiler_path = check_and_choose_venv(venv_path)
            except JEditorExecException as error:
                pybreeze_logger.error("No Python interpreter found for run: %r", error)
                self._append_text(f"[Error] No Python interpreter found: {error}", is_error=True)
                self.main_window.show()
                return False
        else:
            self.compiler_path = self.main_window.python_compiler
        return True

    def start_test_process(self, package: str, exec_str: str):
        if not self.renew_path():
            return
        if sys.platform in ["win32", "cygwin", "msys"]:
            exec_str = json.dumps(exec_str)
        args = [
            str(self.compiler_path),
            "-m",
            package,
            "--execute_str",
            exec_str
        ]
        self._spawn_and_pump(package, args)

    def start_test_process_file(self, package: str, file_path: str):
        # Pass the action JSON as a path so we never hit the Windows ~32K
        # command-line cap when scripts are large. Caller owns the file.
        if not self.renew_path():
            return
        args = [
            str(self.compiler_path),
            "-m",
            package,
            "--execute_file",
            str(file_path),
        ]
        self._spawn_and_pump(package, args)

    def _spawn_and_pump(self, package: str, args: list) -> None:
        # Launch user-authored automation script in a child interpreter.
        # Argument list is validated upstream; shell=False, no user string ever
        # reaches a shell. nosec B603 — intentional local process execution.
        self.process = subprocess.Popen(  # nosec B603  # nosemgrep  # noqa: S603
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=no_window_creationflags(),
            env=utf8_subprocess_env(self.program_encoding),
        )
        self.still_run_program = True
        self.read_program_output_from_thread = Thread(
            target=self.read_program_output_from_process,
            daemon=True
        )
        self.read_program_output_from_thread.start()
        self.read_program_error_output_from_thread = Thread(
            target=self.read_program_error_output_from_process,
            daemon=True
        )
        self.read_program_error_output_from_thread.start()
        self.main_window.setWindowTitle(package)
        self.main_window.show()
        self.timer = QTimer(self.main_window)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.pull_text)
        self.timer.start()

    def _append_text(self, text: str, is_error: bool = False) -> None:
        """Append text to the code result widget."""
        text_cursor = self.main_window.code_result.textCursor()
        text_format = QTextCharFormat()
        color_key = "error_output_color" if is_error else "normal_output_color"
        text_format.setForeground(actually_color_dict.get(color_key))
        text_cursor.insertText(text, text_format)
        text_cursor.insertBlock()

    # Pyside UI update method
    def pull_text(self):
        pump_message_queue(self.run_output_queue, self._append_text, is_error=False)
        pump_message_queue(self.run_error_queue, self._append_text, is_error=True)
        if self.process is None:
            if self.timer.isActive():
                self.timer.stop()
            return
        if self.process.returncode is not None:
            if self.timer.isActive():
                self.timer.stop()
            self.exit_program()
        elif self.still_run_program:
            self.process.poll()

    # exit program change run flag to false and clean read thread and queue and process
    def exit_program(self):
        self.still_run_program = False
        # Wait for threads to finish before cleanup
        if self.read_program_output_from_thread is not None:
            self.read_program_output_from_thread.join(timeout=2)
            self.read_program_output_from_thread = None
        if self.read_program_error_output_from_thread is not None:
            self.read_program_error_output_from_thread.join(timeout=2)
            self.read_program_error_output_from_thread = None
        self.drain_and_display_queue()
        if self.process is not None:
            self.process.terminate()
            self._append_text(f"Task exit with code {self.process.returncode}")
            self.process = None
        if self.task_done_trigger_function is not None:
            try:
                self.task_done_trigger_function()
            except Exception as e:
                pybreeze_logger.error(f"Task done trigger failed: {e}")

    def drain_and_display_queue(self):
        while not self.run_output_queue.empty():
            try:
                output_message = str(self.run_output_queue.get_nowait()).strip()
                if output_message:
                    self._append_text(output_message)
            except queue.Empty:
                break
        while not self.run_error_queue.empty():
            try:
                error_message = str(self.run_error_queue.get_nowait()).strip()
                if error_message:
                    self._append_text(error_message, is_error=True)
            except queue.Empty:
                break

    def _read_stream_into_queue(self, stream_name: str, target_queue: Queue) -> None:
        # Block on readline until a line arrives or the pipe hits EOF. Stopping on
        # EOF (empty read) is essential: without it the loop spins at 100% CPU
        # re-reading a closed pipe until the QTimer notices the process exited.
        while self.still_run_program:
            proc = self.process
            if proc is None:
                break
            stream = getattr(proc, stream_name)
            if stream is None:
                break
            try:
                line = stream.readline(self.program_buffer_size)
            except (ValueError, OSError):
                # Pipe closed underneath us during shutdown.
                break
            if not line:
                break
            if isinstance(line, bytes):
                line = line.decode(self.program_encoding, "replace")
            if line.strip():
                target_queue.put(line)

    def read_program_output_from_process(self):
        self._read_stream_into_queue("stdout", self.run_output_queue)

    def read_program_error_output_from_process(self):
        self._read_stream_into_queue("stderr", self.run_error_queue)

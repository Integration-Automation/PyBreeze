from __future__ import annotations

import json
import subprocess
import sys
import threading
from typing import Callable
from pathlib import Path
from queue import Queue
from threading import Thread

from PySide6.QtCore import QTimer
from je_editor import JEditorExecException
from je_editor.utils.venv_check.check_venv import check_and_choose_venv

from pybreeze.extend.process_executor.queue_pump import (
    OUTPUT_STILL_HELD_NOTE,
    ReaderGrace,
    any_alive,
    output_queue,
    pump_message_queue,
    read_stream_into_queue,
)
from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.subprocess_util import (
    no_window_creationflags, own_session_options, stop_tree, utf8_subprocess_env,
)


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
        self.run_output_queue: Queue = output_queue()
        self.run_error_queue: Queue = output_queue()
        self.process: subprocess.Popen | None = None
        self._reader_grace = ReaderGrace()
        # Stop was asked for: a batch run that follows this one does not go on
        self.was_stopped = False

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
                self.main_window.append_output(
                    f"[Error] No Python interpreter found: {error}\n", is_error=True, own_line=True)
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

    def start_module_process(
            self, package: str, arguments: list, environment: dict | None = None):
        """Run ``python -m package`` with *arguments*, adding *environment* if given.

        The general form behind the two calls above, for a package driven by
        subcommands and flags rather than by a script to execute. A setting that
        would be a secret on a command line -- an API key, a forge token -- goes
        through *environment* instead, where the process list cannot show it.
        """
        if not self.renew_path():
            return
        args = [str(self.compiler_path), "-m", package, *[str(one) for one in arguments]]
        self._spawn_and_pump(package, args, environment)

    def _spawn_and_pump(
            self, package: str, args: list, environment: dict | None = None) -> None:
        # Launch user-authored automation script in a child interpreter.
        # Argument list is validated upstream; shell=False, no user string ever
        # reaches a shell. nosec B603 — intentional local process execution.
        child_environment = utf8_subprocess_env(self.program_encoding)
        if environment:
            child_environment.update(environment)
        try:
            self.process = subprocess.Popen(  # nosec B603  # nosemgrep  # noqa: S603
                args,
                # Not the IDE's own stdin: a script calling input() blocked on
                # the IDE's console and consumed what was typed there. It gets
                # end of file, as FileRunnerProcess's children do.
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=no_window_creationflags(),
                env=child_environment,
                **own_session_options(),
            )
        except OSError as error:
            # An interpreter that is gone, or a command line over Windows'
            # limit (a large script run as --execute_str): this raised out of
            # the menu and left a run window no one would ever see.
            pybreeze_logger.error("%s could not start: %r", package, error)
            self.main_window.append_output(
                f"[Error] {package} could not start: {error.strerror or error}\n",
                is_error=True, own_line=True)
            self.main_window.show()
            return
        self.still_run_program = True
        self._reader_grace.restart()
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

    def stop(self) -> None:
        """Stop the child if it is still running.

        The child and every process it started (``stop_tree``): a browser a
        web run opened, or a program a launcher started, used to be left
        running. The run window reports the exit on the next pump, as for any
        other exit.
        """
        self.was_stopped = True
        if self.process is not None:
            stop_tree(self.process)

    # Pyside UI update method
    def pull_text(self):
        pumped = pump_message_queue(self.run_output_queue, self.main_window.append_output, is_error=False)
        pumped += pump_message_queue(self.run_error_queue, self.main_window.append_output, is_error=True)
        if self.process is None:
            if self.timer.isActive():
                self.timer.stop()
            return
        if self.process.returncode is not None:
            # Output still on its way is pumped on the next ticks, not waited
            # for here: this is the UI thread
            if self._reader_grace.still_reading(
                    self.read_program_output_from_thread, self.read_program_error_output_from_thread,
                    progressed=pumped > 0):
                return
            if self.timer.isActive():
                self.timer.stop()
            self.exit_program()
        elif self.still_run_program:
            self.process.poll()

    def exit_program(self):
        """End the run: show what is left of its output, report the exit, run the done hook.

        Does not wait for the reader threads; the pump gave them their grace.
        One still alive means a process the run started holds the output, and
        the window says so.
        """
        self.still_run_program = False
        readers = (self.read_program_output_from_thread, self.read_program_error_output_from_thread)
        self.read_program_output_from_thread = None
        self.read_program_error_output_from_thread = None
        self.drain_and_display_queue()
        if any_alive(*readers):
            self.main_window.append_output(OUTPUT_STILL_HELD_NOTE, own_line=True)
        if self.process is not None:
            self.process.terminate()
            self.main_window.append_output(
                f"Task exit with code {self.process.returncode}\n", own_line=True)
            self.process = None
        if self.task_done_trigger_function is not None:
            try:
                self.task_done_trigger_function()
            except Exception as error:  # noqa: BLE001 — a failing hook (e.g. the report mail) must not break the run window
                pybreeze_logger.error("Task done trigger failed: %r", error)
        self.main_window.run_ended()

    def drain_and_display_queue(self):
        pump_message_queue(
            self.run_output_queue, self.main_window.append_output, is_error=False, max_messages=None)
        pump_message_queue(
            self.run_error_queue, self.main_window.append_output, is_error=True, max_messages=None)

    def _read_stream_into_queue(self, stream_name: str, target_queue: Queue) -> None:
        stream = getattr(self.process, stream_name, None)
        if stream is None:
            return
        read_stream_into_queue(
            stream, target_queue,
            buffer_size=self.program_buffer_size,
            encoding=self.program_encoding,
            keep_reading=lambda: self.still_run_program,
        )

    def read_program_output_from_process(self):
        self._read_stream_into_queue("stdout", self.run_output_queue)

    def read_program_error_output_from_process(self):
        self._read_stream_into_queue("stderr", self.run_error_queue)

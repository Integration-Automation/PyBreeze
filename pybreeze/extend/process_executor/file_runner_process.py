"""
File Runner Process - runs arbitrary language files via plugin run configs.

Supports two modes:
- Direct run: compiler [args...] file  (e.g. go run main.go, java Main.java)
- Compile then run: compiler file -o output && ./output  (e.g. gcc main.c -o main)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from queue import Queue
from threading import Thread

from PySide6.QtCore import QTimer

from pybreeze.extend.process_executor.queue_pump import pump_message_queue, read_stream_into_queue
from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.subprocess_util import no_window_creationflags, utf8_subprocess_env

COMPILE_TIME_LIMIT_SECONDS = 60


class FileRunnerProcess:
    """Manages subprocess execution for any language file."""

    def __init__(
        self,
        main_window: CodeWindow,
        program_encoding: str = "utf-8",
        program_buffer_size: int = 1024,
    ):
        self.main_window = main_window
        self.program_encoding = program_encoding
        self.program_buffer_size = program_buffer_size
        self.still_running: bool = False
        self.process: subprocess.Popen | None = None
        self.output_queue: Queue = Queue()
        self.error_queue: Queue = Queue()
        self.timer: QTimer | None = None
        self._stdout_thread: Thread | None = None
        self._stderr_thread: Thread | None = None
        self._cleanup_binary: str | None = None
        # What to do with the exit code instead of reporting it (the compile
        # step starts the run from here), and when to give up on the child
        self._after_exit: Callable[[int], None] | None = None
        self._deadline: float | None = None

    def run_file(self, run_config: dict, file_path: str) -> None:
        """
        Run a file using the given plugin run config.

        run_config keys:
            name: str           - display name
            compiler: str       - executable name (e.g. "go", "gcc", "java")
            args: tuple[str]    - args between compiler and file (e.g. ("run",))
            compile_then_run: bool (optional) - if True, compile first then run output
            output_flag: str (optional)       - flag for output file (e.g. "-o")
        """
        compile_then_run = run_config.get("compile_then_run", False)
        compiler = run_config["compiler"]
        args = list(run_config.get("args", ()))

        if compile_then_run:
            self._compile_and_run(compiler, args, run_config.get("output_flag", "-o"), file_path)
        else:
            command = [compiler] + args + [file_path]
            self._start_process(command)

    def _compile_and_run(self, compiler: str, args: list, output_flag: str, file_path: str) -> None:
        """Compile, then run the output binary.

        The compiler is a child like the run: its output streams into the window
        as it comes, and the IDE stays usable while it works. It used to run to
        completion on the UI thread, which froze the IDE for up to a minute.
        """
        path = Path(file_path)
        output_name = str(path.with_suffix(""))
        if sys.platform in ("win32", "cygwin", "msys"):
            output_name += ".exe"

        compile_cmd = [compiler] + args + [file_path, output_flag, output_name]
        self.main_window.append_output(f"[Compile] {' '.join(compile_cmd)}\n", is_error=False)

        def run_if_compiled(exit_code: int) -> None:
            if exit_code != 0:
                self.main_window.append_output(f"[Compile failed] exit code {exit_code}\n", is_error=True)
                return
            self.main_window.append_output(f"[Run] {output_name}\n", is_error=False)
            self._start_process([output_name], cleanup_binary=output_name)

        self._start_process(
            compile_cmd, after_exit=run_if_compiled, time_limit=COMPILE_TIME_LIMIT_SECONDS)

    def _start_process(self, command: list[str], cleanup_binary: str | None = None,
                       after_exit: Callable[[int], None] | None = None,
                       time_limit: float | None = None) -> None:
        """Launch subprocess and start output reading.

        :param command: the argv to run
        :param cleanup_binary: a file to delete once the child has exited
        :param after_exit: called with the exit code, on the UI thread, in place
            of the exit line
        :param time_limit: seconds after which the child is stopped
        """
        cmd_display = " ".join(command)
        self.main_window.append_output(f"> {cmd_display}\n", is_error=False)

        try:
            # Run the user's plugin-configured command. shell=False is explicit;
            # argv comes from a plugin run_config + user-opened file path. nosec B603.
            self.process = subprocess.Popen(  # nosec B603  # nosemgrep  # noqa: S603
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # A run window has no input box: a read gets end-of-file at once
                # instead of waiting on a pipe nobody writes to.
                stdin=subprocess.DEVNULL,
                shell=False,
                creationflags=no_window_creationflags(),
                env=utf8_subprocess_env(self.program_encoding),
            )
        except FileNotFoundError:
            self.main_window.append_output(f"[Error] Command not found: {command[0]}\n", is_error=True)
            return

        self._cleanup_binary = cleanup_binary
        self._after_exit = after_exit
        self._deadline = None if time_limit is None else time.monotonic() + time_limit
        self.still_running = True

        self._stdout_thread = Thread(target=self._read_stdout, daemon=True)
        self._stdout_thread.start()

        self._stderr_thread = Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

        self.main_window.show()
        if self.timer is None:
            self.timer = QTimer(self.main_window)
            self.timer.setInterval(50)
            self.timer.timeout.connect(self._pull_text)
        self.timer.start()

    def stop(self) -> None:
        """Stop the child if it is still running.

        Only the child itself: processes it started are left to it. The run
        window reports the exit on the next pump, as for any other exit.
        """
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()

    def _pull_text(self) -> None:
        """Timer callback: pump queues to UI."""
        pump_message_queue(self.output_queue, self.main_window.append_output, is_error=False)
        pump_message_queue(self.error_queue, self.main_window.append_output, is_error=True)

        if self.process is not None:
            self.process.poll()
            if self.process.returncode is not None:
                self._finish()
            elif self._deadline is not None and time.monotonic() > self._deadline:
                self._deadline = None
                self.main_window.append_output(
                    f"[Error] Timed out after {COMPILE_TIME_LIMIT_SECONDS}s\n", is_error=True)
                self.process.terminate()

    def _finish(self) -> None:
        """Clean up after process exits."""
        self.still_running = False
        if self.timer and self.timer.isActive():
            self.timer.stop()

        # Wait for reader threads to finish
        if self._stdout_thread is not None:
            self._stdout_thread.join(timeout=2)
            self._stdout_thread = None
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=2)
            self._stderr_thread = None

        # Drain remaining output directly (not via _pull_text to avoid recursion)
        self._drain_queues()

        after_exit, self._after_exit = self._after_exit, None
        if self.process is not None:
            exit_code = self.process.returncode
            self.process = None
            if after_exit is not None:
                after_exit(exit_code)
                return
            self.main_window.append_output(
                f"\n[Process exited with code {exit_code}]\n",
                is_error=exit_code != 0,
            )

        # Clean up compiled binary
        if self._cleanup_binary:
            try:
                os.remove(self._cleanup_binary)
            except OSError as error:
                pybreeze_logger.debug("Could not remove compiled binary %s: %s", self._cleanup_binary, error)

    def _drain_queues(self) -> None:
        """Drain all remaining messages from output/error queues to UI."""
        pump_message_queue(self.output_queue, self.main_window.append_output, is_error=False, max_messages=None)
        pump_message_queue(self.error_queue, self.main_window.append_output, is_error=True, max_messages=None)

    def _read_stream(self, stream_name: str, target_queue: Queue) -> None:
        stream = getattr(self.process, stream_name, None)
        if stream is None:
            return
        read_stream_into_queue(
            stream, target_queue,
            buffer_size=self.program_buffer_size,
            encoding=self.program_encoding,
            keep_reading=lambda: self.still_running,
        )

    def _read_stdout(self) -> None:
        self._read_stream("stdout", self.output_queue)

    def _read_stderr(self) -> None:
        self._read_stream("stderr", self.error_queue)

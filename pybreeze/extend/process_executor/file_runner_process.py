"""
File Runner Process - runs arbitrary language files via plugin run configs.

Supports two modes:
- Direct run: compiler [args...] file  (e.g. go run main.go, java Main.java)
- Compile then run: compiler file -o output && ./output  (e.g. gcc main.c -o main)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from queue import Queue
from threading import Event, Thread

from PySide6.QtCore import QTimer

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
        self.output_queue: Queue = output_queue()
        self.error_queue: Queue = output_queue()
        self.timer: QTimer | None = None
        self._stdout_thread: Thread | None = None
        self._stderr_thread: Thread | None = None
        # The folder a compiled binary was built in, removed once it has run
        self._cleanup_dir: str | None = None
        # Set while this process's readers should read: one per process, so a
        # compile's reader still alive stops when the compile ends and does
        # not carry on into the run's output
        self._reading: Event | None = None
        # Stop was pressed: a compile that ends then does not start the run
        self._cancelled = False
        # What to do with the exit code instead of reporting it (the compile
        # step starts the run from here), and when to give up on the child
        self._after_exit: Callable[[int], None] | None = None
        self._deadline: float | None = None
        self._reader_grace = ReaderGrace()

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
        self._cancelled = False
        compile_then_run = run_config.get("compile_then_run", False)
        compiler = run_config.get("compiler")
        if not isinstance(compiler, str) or not compiler:
            # A plugin's config is not checked by JEditor when it registers.
            self.main_window.append_output("[Error] The run config names no compiler\n", is_error=True)
            return
        args = [str(arg) for arg in run_config.get("args", ())]

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

        The binary is built in a folder of its own, removed after the run: built
        beside the source, it replaced (and then deleted) a file of that name
        there, and two runs of one file fought over it.
        """
        build_dir = tempfile.mkdtemp(prefix="pybreeze-run-")
        output_name = str(Path(build_dir) / Path(file_path).stem)
        if sys.platform in ("win32", "cygwin", "msys"):
            output_name += ".exe"

        compile_cmd = [compiler] + args + [file_path, output_flag, output_name]
        self.main_window.append_output(f"[Compile] {' '.join(compile_cmd)}\n", is_error=False)

        def run_if_compiled(exit_code: int) -> None:
            if self._cancelled:
                # Stopped: while compiling (reported as a failed compile), or
                # just after it succeeded (the binary ran anyway)
                self.main_window.append_output("[Stopped]\n", is_error=True, own_line=True)
                self._remove_build_dir(build_dir)
                return
            if exit_code != 0:
                self.main_window.append_output(f"[Compile failed] exit code {exit_code}\n", is_error=True)
                self._remove_build_dir(build_dir)
                return
            self.main_window.append_output(f"[Run] {output_name}\n", is_error=False)
            self._start_process([output_name], cleanup_dir=build_dir)

        self._start_process(
            compile_cmd, after_exit=run_if_compiled, time_limit=COMPILE_TIME_LIMIT_SECONDS,
            cleanup_dir=build_dir)

    def _start_process(self, command: list[str], cleanup_dir: str | None = None,
                       after_exit: Callable[[int], None] | None = None,
                       time_limit: float | None = None) -> None:
        """Launch subprocess and start output reading.

        :param command: the argv to run
        :param cleanup_dir: a folder to remove once the child has exited (and
            its ``after_exit`` has not taken it over)
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
            self._remove_build_dir(cleanup_dir)
            return
        except OSError as error:
            # Not executable, a folder, or a compiled binary locked or blocked
            # by antivirus: this raised out of the menu, or out of the timer
            # slot after a compile, and the window said nothing.
            self.main_window.append_output(
                f"[Error] Could not start {command[0]}: {error.strerror or error}\n", is_error=True)
            self._remove_build_dir(cleanup_dir)
            return

        self._cleanup_dir = cleanup_dir
        self._after_exit = after_exit
        self._deadline = None if time_limit is None else time.monotonic() + time_limit
        self.still_running = True
        self._reading = Event()
        self._reading.set()
        self._reader_grace.restart()

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
        window reports the exit on the next pump, as for any other exit. A
        compile that is stopped, or that has just finished, starts no run.
        """
        self._cancelled = True
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()

    def _pull_text(self) -> None:
        """Timer callback: pump queues to UI."""
        pumped = pump_message_queue(self.output_queue, self.main_window.append_output, is_error=False)
        pumped += pump_message_queue(self.error_queue, self.main_window.append_output, is_error=True)

        if self.process is not None:
            self.process.poll()
            if self.process.returncode is not None:
                # Output still on its way is pumped on the next ticks, not
                # waited for here: this is the UI thread
                if not self._reader_grace.still_reading(
                        self._stdout_thread, self._stderr_thread, progressed=pumped > 0):
                    self._finish()
            elif self._deadline is not None and time.monotonic() > self._deadline:
                self._deadline = None
                self.main_window.append_output(
                    f"[Error] Timed out after {COMPILE_TIME_LIMIT_SECONDS}s\n", is_error=True)
                self.process.terminate()

    def _finish(self) -> None:
        """Clean up after process exits."""
        self.still_running = False
        if self._reading is not None:
            self._reading.clear()
        if self.timer and self.timer.isActive():
            self.timer.stop()

        # Not waited for: the pump gave the readers their grace. One still
        # alive means a process the child started holds the output.
        readers = (self._stdout_thread, self._stderr_thread)
        self._stdout_thread = self._stderr_thread = None

        # Drain remaining output directly (not via _pull_text to avoid recursion)
        self._drain_queues()
        if any_alive(*readers):
            self.main_window.append_output(OUTPUT_STILL_HELD_NOTE, is_error=False, own_line=True)

        after_exit, self._after_exit = self._after_exit, None
        if self.process is not None:
            exit_code = self.process.returncode
            self.process = None
            if after_exit is not None:
                # It takes the build folder over: the run removes it, or it does
                self._cleanup_dir = None
                after_exit(exit_code)
                if self.process is None:  # the compile failed: nothing runs next
                    self.main_window.run_ended()
                return
            self.main_window.append_output(
                f"\n[Process exited with code {exit_code}]\n",
                is_error=exit_code != 0,
            )

        self._remove_build_dir(self._cleanup_dir)
        self._cleanup_dir = None
        self.main_window.run_ended()

    @staticmethod
    def _remove_build_dir(folder: str | None) -> None:
        """Delete a compile's build folder once its binary has run, or could not."""
        if not folder:
            return
        shutil.rmtree(folder, ignore_errors=True)
        if Path(folder).exists():  # a binary something still holds open
            pybreeze_logger.debug("Could not remove the build folder %s", folder)

    def _drain_queues(self) -> None:
        """Drain all remaining messages from output/error queues to UI."""
        pump_message_queue(self.output_queue, self.main_window.append_output, is_error=False, max_messages=None)
        pump_message_queue(self.error_queue, self.main_window.append_output, is_error=True, max_messages=None)

    def _read_stream(self, stream_name: str, target_queue: Queue) -> None:
        stream = getattr(self.process, stream_name, None)
        if stream is None:
            return
        # This process's flag, as it is when the reader starts
        reading = getattr(self, "_reading", None)
        read_stream_into_queue(
            stream, target_queue,
            buffer_size=self.program_buffer_size,
            encoding=self.program_encoding,
            keep_reading=lambda: self.still_running and (reading is None or reading.is_set()),
        )

    def _read_stdout(self) -> None:
        self._read_stream("stdout", self.output_queue)

    def _read_stderr(self) -> None:
        self._read_stream("stderr", self.error_queue)

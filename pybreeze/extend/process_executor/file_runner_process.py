"""
File Runner Process - runs arbitrary language files via plugin run configs.

Supports two modes:
- Direct run: compiler [args...] file  (e.g. go run main.go, java Main.java)
- Compile then run: compiler file -o output && ./output  (e.g. gcc main.c -o main)
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
from pathlib import Path
from queue import Queue
from threading import Thread

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCharFormat

from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict

from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow


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
        """Compile, then run the output binary."""
        path = Path(file_path)
        output_name = str(path.with_suffix(""))
        if sys.platform in ("win32", "cygwin", "msys"):
            output_name += ".exe"

        compile_cmd = [compiler] + args + [file_path, output_flag, output_name]
        self._append_text(f"[Compile] {' '.join(compile_cmd)}\n", is_error=False)

        try:
            result = subprocess.run(
                compile_cmd,
                capture_output=True,
                timeout=60,
            )
        except FileNotFoundError:
            self._append_text(f"[Error] Compiler not found: {compiler}\n", is_error=True)
            return
        except subprocess.TimeoutExpired:
            self._append_text("[Error] Compilation timed out (60s)\n", is_error=True)
            return

        if result.stdout:
            self._append_text(result.stdout.decode(self.program_encoding, "replace"), is_error=False)
        if result.stderr:
            self._append_text(result.stderr.decode(self.program_encoding, "replace"), is_error=True)

        if result.returncode != 0:
            self._append_text(f"[Compile failed] exit code {result.returncode}\n", is_error=True)
            return

        self._append_text(f"[Run] {output_name}\n", is_error=False)
        self._start_process([output_name], cleanup_binary=output_name)

    def _start_process(self, command: list[str], cleanup_binary: str | None = None) -> None:
        """Launch subprocess and start output reading."""
        self._cleanup_binary = cleanup_binary

        cmd_display = " ".join(command)
        self._append_text(f"> {cmd_display}\n", is_error=False)

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                shell=False,
            )
        except FileNotFoundError:
            self._append_text(f"[Error] Command not found: {command[0]}\n", is_error=True)
            return

        self.still_running = True

        self._stdout_thread = Thread(target=self._read_stdout, daemon=True)
        self._stdout_thread.start()

        self._stderr_thread = Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

        self.main_window.show()
        self.timer = QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._pull_text)
        self.timer.start()

    def _pull_text(self) -> None:
        """Timer callback: pump queues to UI."""
        try:
            while not self.output_queue.empty():
                msg = self.output_queue.get_nowait()
                msg = str(msg).strip()
                if msg:
                    self._append_text(msg + "\n", is_error=False)
        except queue.Empty:
            pass

        try:
            while not self.error_queue.empty():
                msg = self.error_queue.get_nowait()
                msg = str(msg).strip()
                if msg:
                    self._append_text(msg + "\n", is_error=True)
        except queue.Empty:
            pass

        if self.process is not None:
            self.process.poll()
            if self.process.returncode is not None:
                self._finish()

    def _finish(self) -> None:
        """Clean up after process exits."""
        self.still_running = False
        if self.timer and self.timer.isActive():
            self.timer.stop()

        # Drain remaining output directly (not via _pull_text to avoid recursion)
        self._drain_queues()

        if self.process is not None:
            self._append_text(
                f"\n[Process exited with code {self.process.returncode}]\n",
                is_error=self.process.returncode != 0,
            )
            self.process = None

        # Clean up compiled binary
        if self._cleanup_binary:
            try:
                os.remove(self._cleanup_binary)
            except OSError:
                pass

    def _drain_queues(self) -> None:
        """Drain all remaining messages from output/error queues to UI."""
        while not self.output_queue.empty():
            try:
                msg = self.output_queue.get_nowait()
                msg = str(msg).strip()
                if msg:
                    self._append_text(msg + "\n", is_error=False)
            except queue.Empty:
                break
        while not self.error_queue.empty():
            try:
                msg = self.error_queue.get_nowait()
                msg = str(msg).strip()
                if msg:
                    self._append_text(msg + "\n", is_error=True)
            except queue.Empty:
                break

    def _read_stdout(self) -> None:
        try:
            while self.still_running:
                proc = self.process
                if proc is None:
                    break
                data = proc.stdout.readline(self.program_buffer_size)
                if not data and proc.poll() is not None:
                    break
                if isinstance(data, bytes):
                    data = data.decode(self.program_encoding, "replace")
                if data:
                    self.output_queue.put(data)
        except (OSError, ValueError):
            pass

    def _read_stderr(self) -> None:
        try:
            while self.still_running:
                proc = self.process
                if proc is None:
                    break
                data = proc.stderr.readline(self.program_buffer_size)
                if not data and proc.poll() is not None:
                    break
                if isinstance(data, bytes):
                    data = data.decode(self.program_encoding, "replace")
                if data:
                    self.error_queue.put(data)
        except (OSError, ValueError):
            pass

    def _append_text(self, text: str, is_error: bool) -> None:
        """Append text to the code result widget."""
        text_cursor = self.main_window.code_result.textCursor()
        text_format = QTextCharFormat()
        color_key = "error_output_color" if is_error else "normal_output_color"
        text_format.setForeground(actually_color_dict.get(color_key))
        text_cursor.insertText(text, text_format)

"""Regression tests for the subprocess reader threads.

These lock in the EOF fix: an empty read from ``readline`` means the pipe
closed, so the reader must stop instead of spinning on a closed pipe (which
previously pinned a CPU core until the process was reaped).
"""
from __future__ import annotations

import io
from queue import Queue

from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager


class _CountingStream:
    """A byte stream that records how many times readline was called."""

    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)
        self.readline_calls = 0

    def readline(self, size: int = -1) -> bytes:
        self.readline_calls += 1
        return self._buf.readline(size)


class _FakeProc:
    def __init__(self, stdout: bytes = b"", stderr: bytes = b""):
        self.stdout = _CountingStream(stdout)
        self.stderr = _CountingStream(stderr)


def _make_task_manager(proc) -> TaskProcessManager:
    manager = TaskProcessManager.__new__(TaskProcessManager)
    manager.still_run_program = True
    manager.program_buffer_size = 1024
    manager.program_encoding = "utf-8"
    manager.run_output_queue = Queue()
    manager.run_error_queue = Queue()
    manager.process = proc
    return manager


def _drain(q: Queue) -> list[str]:
    items = []
    while not q.empty():
        items.append(q.get())
    return items


class TestTaskProcessManagerReader:
    def test_reads_all_lines_then_stops(self):
        proc = _FakeProc(stdout=b"alpha\nbeta\n")
        manager = _make_task_manager(proc)
        manager._read_stream_into_queue("stdout", manager.run_output_queue)
        assert _drain(manager.run_output_queue) == ["alpha\n", "beta\n"]

    def test_eof_does_not_spin(self):
        # Pipe already at EOF: readline should be called exactly once, then break.
        proc = _FakeProc(stdout=b"")
        manager = _make_task_manager(proc)
        manager._read_stream_into_queue("stdout", manager.run_output_queue)
        assert proc.stdout.readline_calls == 1
        assert manager.run_output_queue.empty()


def _make_file_runner(proc) -> FileRunnerProcess:
    runner = FileRunnerProcess.__new__(FileRunnerProcess)
    runner.still_running = True
    runner.program_buffer_size = 1024
    runner.program_encoding = "utf-8"
    runner.output_queue = Queue()
    runner.error_queue = Queue()
    runner.process = proc
    return runner


class TestFileRunnerReader:
    def test_reads_all_lines_then_stops(self):
        proc = _FakeProc(stderr=b"warn1\nwarn2\n")
        runner = _make_file_runner(proc)
        runner._read_stream("stderr", runner.error_queue)
        assert _drain(runner.error_queue) == ["warn1\n", "warn2\n"]

    def test_eof_does_not_spin(self):
        proc = _FakeProc(stdout=b"")
        runner = _make_file_runner(proc)
        runner._read_stream("stdout", runner.output_queue)
        assert proc.stdout.readline_calls == 1
        assert runner.output_queue.empty()

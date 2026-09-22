from __future__ import annotations

import io
from queue import Queue

from pybreeze.extend.process_executor.queue_pump import (
    MAX_MESSAGES_PER_PUMP,
    pump_message_queue,
    read_stream_into_queue,
)


def _collect_pump(messages, *, max_messages=MAX_MESSAGES_PER_PUMP):
    q: Queue = Queue()
    for message in messages:
        q.put(message)
    received: list[tuple[str, bool]] = []
    pump_message_queue(
        q,
        lambda text, is_error: received.append((text, is_error)),
        is_error=False,
        max_messages=max_messages,
    )
    return q, received


def _read_all(data: bytes, *, keep_reading=lambda: True) -> list[str]:
    q: Queue = Queue()
    read_stream_into_queue(
        io.BytesIO(data), q, buffer_size=1024, encoding="utf-8", keep_reading=keep_reading)
    items = []
    while not q.empty():
        items.append(q.get())
    return items


class TestPumpBatching:
    def test_drains_many_messages_in_one_call(self):
        q, received = _collect_pump([f"line {i}" for i in range(50)])
        assert len(received) == 50
        assert q.empty()

    def test_respects_max_messages_bound(self):
        q, received = _collect_pump([f"line {i}" for i in range(10)], max_messages=4)
        assert len(received) == 4
        assert q.qsize() == 6  # remaining drained on later ticks

    def test_none_drains_everything(self):
        q, received = _collect_pump(
            [f"line {i}" for i in range(MAX_MESSAGES_PER_PUMP * 3)], max_messages=None)
        assert len(received) == MAX_MESSAGES_PER_PUMP * 3
        assert q.empty()

    def test_empty_queue_is_noop(self):
        _, received = _collect_pump([])
        assert received == []

    def test_messages_pass_through_unchanged(self):
        _, received = _collect_pump(["    indented\n", "\n", "  \n", "last"])
        assert [text for text, _ in received] == ["    indented\n", "\n", "  \n", "last"]

    def test_only_empty_messages_are_skipped(self):
        _, received = _collect_pump(["", "real"])
        assert received == [("real", False)]

    def test_is_error_flag_forwarded(self):
        q: Queue = Queue()
        q.put("boom")
        received: list[tuple[str, bool]] = []
        pump_message_queue(
            q, lambda text, is_error: received.append((text, is_error)), is_error=True
        )
        assert received == [("boom", True)]


class TestReadStreamIntoQueue:
    def test_lines_keep_indentation_blank_lines_and_endings(self):
        data = b"def f():\n    return 1\n\n\tdone\r\n"
        assert _read_all(data) == ["def f():\n", "    return 1\n", "\n", "\tdone\r\n"]

    def test_bytes_are_decoded_with_replacement(self):
        assert _read_all("café\n".encode() + b"\xff\n") == ["café\n", "�\n"]

    def test_stops_when_told_to(self):
        assert _read_all(b"one\ntwo\n", keep_reading=lambda: False) == []

    def test_a_closed_pipe_ends_the_reader(self):
        class Closed:
            def readline(self, _size):
                raise ValueError("I/O operation on closed file")

        q: Queue = Queue()
        read_stream_into_queue(
            Closed(), q, buffer_size=16, encoding="utf-8", keep_reading=lambda: True)
        assert q.empty()

    def test_a_line_longer_than_the_buffer_arrives_in_pieces(self):
        # The pieces carry no line break of their own, so displayed back to back
        # they form the original line again.
        pieces = []
        q: Queue = Queue()
        read_stream_into_queue(
            io.BytesIO(b"abcdefghij\n"), q, buffer_size=4, encoding="utf-8",
            keep_reading=lambda: True)
        while not q.empty():
            pieces.append(q.get())
        assert pieces == ["abcd", "efgh", "ij\n"]

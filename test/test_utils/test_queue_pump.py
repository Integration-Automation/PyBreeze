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
        assert "".join(_read_all(data)) == "def f():\n    return 1\n\n\tdone\r\n"

    def test_bytes_are_decoded_with_replacement(self):
        assert "".join(_read_all("café\n".encode() + b"\xff\n")) == "café\n�\n"

    def test_what_has_arrived_is_passed_on_without_waiting_for_a_newline(self):
        # readline waited for one: a progress bar rewinding with \r showed nothing
        # until the run's next newline
        class Trickle:
            def __init__(self) -> None:
                self.pieces = [b"0%\r", b"50%\r", b"100%\r", b"done\n"]

            def read1(self, _size: int) -> bytes:
                return self.pieces.pop(0) if self.pieces else b""

        target: Queue = Queue()
        read_stream_into_queue(Trickle(), target, buffer_size=1024, encoding="utf-8", keep_reading=lambda: True)

        got = []
        while not target.empty():
            got.append(target.get())
        # Each piece as it came (a trailing \r held for the next one)
        assert got == ["0%", "\r50%", "\r100%", "\rdone\n"]

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

    def _pieces(self, data: bytes, buffer_size: int, encoding: str = "utf-8") -> list[str]:
        q: Queue = Queue()
        read_stream_into_queue(
            io.BytesIO(data), q, buffer_size=buffer_size, encoding=encoding,
            keep_reading=lambda: True)
        items = []
        while not q.empty():
            items.append(q.get())
        return items

    def test_a_character_cut_by_the_buffer_is_joined(self):
        # Each of these characters is three bytes; a four-byte buffer cuts them.
        text = "中文輸出\n"
        pieces = self._pieces(text.encode("utf-8"), buffer_size=4)
        assert "".join(pieces) == text
        assert "�" not in "".join(pieces)

    def test_a_line_ending_cut_by_the_buffer_stays_one_line_ending(self):
        pieces = self._pieces(b"abc\r\ndef\r\n", buffer_size=4)
        # Normalised for display piece by piece, a lone "\r" then "\n" would be
        # two line breaks.
        assert not any(piece.endswith("\r") for piece in pieces)
        assert "".join(pieces) == "abc\r\ndef\r\n"

    def test_a_carriage_return_at_the_very_end_is_not_lost(self):
        assert "".join(self._pieces(b"50%\r", buffer_size=1024)) == "50%\r"

    def test_an_unknown_encoding_falls_back_to_utf8(self):
        assert self._pieces("ok 中\n".encode("utf-8"), 1024, encoding="no-such-codec") == ["ok 中\n"]


class TestABoundedQueue:
    """A reader waits on a full queue instead of holding every line of a runaway run in memory."""

    def test_the_reader_waits_while_the_queue_is_full(self):
        import threading

        from pybreeze.extend.process_executor import queue_pump

        class LineByLine:
            """A pipe that has one line ready each time it is read."""

            def __init__(self) -> None:
                self.lines = [f"{i}\n".encode() for i in range(10)]

            def read1(self, _size: int) -> bytes:
                return self.lines.pop(0) if self.lines else b""

        target: Queue = Queue(maxsize=3)
        reader = threading.Thread(target=queue_pump.read_stream_into_queue, args=(LineByLine(), target),
                                  kwargs={"buffer_size": 1024, "encoding": "utf-8", "keep_reading": lambda: True})
        reader.start()
        reader.join(0.5)

        assert reader.is_alive()
        assert target.qsize() == 3
        got = [target.get(timeout=2) for _ in range(10)]
        reader.join(2)
        assert got == [f"{i}\n" for i in range(10)]
        assert not reader.is_alive()

    def test_a_waiting_reader_gives_up_once_told_to_stop(self):
        import threading

        from pybreeze.extend.process_executor import queue_pump

        target: Queue = Queue(maxsize=1)
        running = {"on": True}
        reader = threading.Thread(target=queue_pump.read_stream_into_queue, args=(io.BytesIO(b"a\nb\nc\n"), target),
                                  kwargs={"buffer_size": 1024, "encoding": "utf-8",
                                          "keep_reading": lambda: running["on"]})
        reader.start()
        reader.join(0.3)
        running["on"] = False
        reader.join(2)

        assert not reader.is_alive()

    def test_the_executors_queues_are_bounded(self):
        from pybreeze.extend.process_executor.queue_pump import MAX_QUEUED_MESSAGES, output_queue

        assert output_queue().maxsize == MAX_QUEUED_MESSAGES > 0


class TestTheGraceWhileOutputStillComes:
    def test_output_still_arriving_keeps_the_run_open(self, monkeypatch):
        import threading

        from pybreeze.extend.process_executor import queue_pump

        now = {"t": 100.0}
        monkeypatch.setattr(queue_pump.time, "monotonic", lambda: now["t"])
        alive = threading.Event()
        reader = threading.Thread(target=alive.wait, args=(5,))
        reader.start()
        grace = queue_pump.ReaderGrace()
        try:
            assert grace.still_reading(reader)
            now["t"] += 1.5
            assert grace.still_reading(reader, progressed=True)
            now["t"] += 1.5  # three seconds after the exit, but output came 1.5 s ago
            assert grace.still_reading(reader)
            now["t"] += 1.0
            assert not grace.still_reading(reader)
        finally:
            alive.set()
            reader.join()

    def test_never_past_the_drain_limit(self, monkeypatch):
        import threading

        from pybreeze.extend.process_executor import queue_pump

        now = {"t": 0.0}
        monkeypatch.setattr(queue_pump.time, "monotonic", lambda: now["t"])
        alive = threading.Event()
        reader = threading.Thread(target=alive.wait, args=(5,))
        reader.start()
        grace = queue_pump.ReaderGrace()
        try:
            grace.still_reading(reader)
            now["t"] = queue_pump.MAX_DRAIN_SECONDS + 0.1
            assert not grace.still_reading(reader, progressed=True)
        finally:
            alive.set()
            reader.join()


def test_the_pump_says_how_many_it_took():
    from pybreeze.extend.process_executor.queue_pump import pump_message_queue

    target: Queue = Queue()
    for message in ("a", "", "b"):
        target.put(message)

    assert pump_message_queue(target, lambda _text, _is_error: None, is_error=False) == 3


class TestAQueueNobodyEmpties:
    def test_the_reader_stops_waiting_once_it_is_told_to(self):
        # The run window gone, the queue full: the reader must not wait for room for ever
        import threading

        full: Queue = Queue(maxsize=1)
        full.put("already there")
        asked = {"count": 0}

        def keep_reading() -> bool:
            asked["count"] += 1
            return asked["count"] < 3  # a check to start reading, then a wait or two for room

        reader = threading.Thread(target=read_stream_into_queue, args=(io.BytesIO(b"one\ntwo\n"), full), kwargs={
            "buffer_size": 1024, "encoding": "utf-8", "keep_reading": keep_reading}, daemon=True)
        reader.start()
        reader.join(10)

        assert not reader.is_alive()
        assert list(full.queue) == ["already there"]


def test_an_escape_cut_off_by_the_end_of_the_output_is_still_passed_on():
    # Held for the rest that never comes: at the end it goes out as it is
    assert "".join(_read_all(b"done \x1b[3")) == "done \x1b[3"

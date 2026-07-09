from __future__ import annotations

from queue import Queue

from pybreeze.extend.process_executor.queue_pump import (
    MAX_MESSAGES_PER_PUMP,
    pump_message_queue,
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


class TestPumpBatching:
    def test_drains_many_messages_in_one_call(self):
        q, received = _collect_pump([f"line {i}" for i in range(50)])
        assert len(received) == 50
        assert q.empty()

    def test_respects_max_messages_bound(self):
        q, received = _collect_pump([f"line {i}" for i in range(10)], max_messages=4)
        assert len(received) == 4
        assert q.qsize() == 6  # remaining drained on later ticks

    def test_empty_queue_is_noop(self):
        _, received = _collect_pump([])
        assert received == []

    def test_blank_messages_are_skipped(self):
        _, received = _collect_pump(["  ", "\n", "real"])
        assert received == [("real", False)]

    def test_is_error_flag_forwarded(self):
        q: Queue = Queue()
        q.put("boom")
        received: list[tuple[str, bool]] = []
        pump_message_queue(
            q, lambda text, is_error: received.append((text, is_error)), is_error=True
        )
        assert received == [("boom", True)]

from __future__ import annotations

import pytest

from pybreeze.utils.network.http_client import (
    CONNECT_TIMEOUT,
    ResponseTooLargeError,
    read_capped_text,
    truncate_for_display,
)


class TestConnectTimeout:
    def test_is_a_positive_number(self):
        assert isinstance(CONNECT_TIMEOUT, (int, float))
        assert CONNECT_TIMEOUT > 0

    def test_shorter_than_typical_read_timeouts(self):
        # Used as the connect half of timeout=(CONNECT_TIMEOUT, read); it should
        # be well under the 30/60s read budgets so connect failures fail fast.
        assert CONNECT_TIMEOUT < 30


class FakeResponse:
    """Minimal stand-in for a streamed requests.Response."""

    def __init__(self, body: bytes, encoding: str | None = "utf-8", chunk: int = 8):
        self._body = body
        self.encoding = encoding
        self._chunk = chunk
        self.closed = False

    def iter_content(self, chunk_size: int = 65536):
        step = self._chunk
        for i in range(0, len(self._body), step):
            yield self._body[i:i + step]

    def close(self):
        self.closed = True


class TestReadCappedText:
    def test_reads_full_body_under_cap(self):
        resp = FakeResponse(b"hello world")
        assert read_capped_text(resp, max_bytes=1024) == "hello world"
        assert resp.closed is True

    def test_raises_when_over_cap(self):
        resp = FakeResponse(b"x" * 5000)
        with pytest.raises(ResponseTooLargeError):
            read_capped_text(resp, max_bytes=1000)
        assert resp.closed is True  # closed even on abort

    def test_exact_cap_is_allowed(self):
        resp = FakeResponse(b"x" * 100)
        assert len(read_capped_text(resp, max_bytes=100)) == 100

    def test_falls_back_to_default_encoding_when_none(self):
        resp = FakeResponse("héllo".encode("utf-8"), encoding=None)
        assert read_capped_text(resp, default_encoding="utf-8") == "héllo"

    def test_decode_errors_are_replaced_not_raised(self):
        resp = FakeResponse(b"\xff\xfe bad bytes", encoding="utf-8")
        # Should not raise; invalid bytes replaced.
        assert isinstance(read_capped_text(resp), str)


class TestTruncateForDisplay:
    def test_short_text_unchanged(self):
        assert truncate_for_display("short", limit=100) == "short"

    def test_long_text_truncated_with_marker(self):
        result = truncate_for_display("x" * 5000, limit=100)
        assert result.startswith("x" * 100)
        assert "truncated" in result
        assert "5000" in result

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pybreeze.utils.network.http_client import (
    CONNECT_TIMEOUT,
    ResponseTooLargeError,
    read_capped_text,
    succeeded,
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

    def __init__(self, body: bytes, encoding: str | None = "utf-8", chunk: int = 8,
                 content_type: str | None = None):
        self._body = body
        self.encoding = encoding
        # The charset is read from the header, as a server sends it
        if content_type is None and encoding is not None:
            content_type = f"text/plain; charset={encoding}"
        self.headers = {"Content-Type": content_type} if content_type else {}
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


class TestAnEncodingTheServerNames:
    def test_an_encoding_python_does_not_know_falls_back(self):
        # The charset comes from the response's Content-Type: a server naming
        # one Python has never heard of must not raise out of the read.
        resp = FakeResponse("héllo".encode("utf-8"), encoding="totally-made-up")

        assert read_capped_text(resp, default_encoding="utf-8") == "héllo"


class TestSucceeded:
    @pytest.mark.parametrize("status", [200, 201, 204, 299])
    def test_a_2xx_is_an_answer(self, status):
        assert succeeded(SimpleNamespace(status_code=status))

    @pytest.mark.parametrize("status", [199, 301, 302, 304, 400, 404, 500])
    def test_anything_else_is_not(self, status):
        # 3xx included, although requests calls it "ok"
        assert not succeeded(SimpleNamespace(status_code=status))


class TestWhichCharset:
    def test_text_without_a_charset_is_utf8_not_latin1(self):
        # requests sets ISO-8859-1 on any text/* without a charset
        resp = FakeResponse("程式碼審查 ✓".encode("utf-8"), encoding="ISO-8859-1", content_type="text/plain")

        assert read_capped_text(resp) == "程式碼審查 ✓"

    def test_a_named_charset_is_used(self):
        resp = FakeResponse("héllo".encode("latin-1"), encoding="ISO-8859-1",
                            content_type='text/plain; charset="ISO-8859-1"')

        assert read_capped_text(resp) == "héllo"

    def test_json_without_a_charset_is_utf8(self):
        resp = FakeResponse('{"a": "ü"}'.encode("utf-8"), encoding=None, content_type="application/json")

        assert read_capped_text(resp) == '{"a": "ü"}'

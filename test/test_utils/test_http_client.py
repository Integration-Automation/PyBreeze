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

    def test_one_byte_over_the_cap_is_refused(self):
        with pytest.raises(ResponseTooLargeError):
            read_capped_text(FakeResponse(b"x" * 101), max_bytes=100)

    def test_by_default_an_answer_may_take_five_minutes_as_the_guide_says(self):
        # docs/source/*/ai_tools.rst: a request past five minutes is stopped
        import inspect

        from pybreeze.utils.network.http_client import DEFAULT_MAX_READ_SECONDS

        assert DEFAULT_MAX_READ_SECONDS == 5 * 60
        assert inspect.signature(read_capped_text).parameters["max_seconds"].default == DEFAULT_MAX_READ_SECONDS

    def test_by_default_an_answer_of_a_few_megabytes_is_read_and_16_mb_is_the_cap(self):
        from pybreeze.utils.network.http_client import DEFAULT_MAX_RESPONSE_BYTES

        assert DEFAULT_MAX_RESPONSE_BYTES == 16 * 1024 * 1024
        answer = b"x" * (3 * 1024 * 1024)
        assert len(read_capped_text(FakeResponse(answer, chunk=65536))) == len(answer)

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

    def test_text_exactly_at_the_limit_is_unchanged_and_one_more_is_cut(self):
        assert truncate_for_display("x" * 100, limit=100) == "x" * 100
        assert truncate_for_display("x" * 101, limit=100).startswith("x" * 100 + "…")

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

    @pytest.mark.parametrize("status", [199, 300, 301, 302, 304, 400, 404, 500])
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


class TestHowLongAnAnswerMayTake:
    def test_a_trickle_is_cut_off_at_the_deadline(self, monkeypatch):
        # Each chunk came inside the read timeout, so nothing ever stopped it
        import requests

        from pybreeze.utils.network import http_client

        clock = iter(range(0, 10_000, 25))  # every chunk 25 s after the last
        monkeypatch.setattr(http_client.time, "monotonic", lambda: next(clock))
        resp = FakeResponse(b"x" * 100, chunk=1)

        with pytest.raises(requests.exceptions.ReadTimeout):
            read_capped_text(resp, max_seconds=300)
        assert resp.closed

    def test_reading_stops_at_the_first_chunk_past_the_deadline(self, monkeypatch):
        # Not only the timeout at the end: the rest of a slow answer is not read.
        # The clock never lands on the deadline itself, as a real one does not.
        import requests

        from pybreeze.utils.network import http_client

        # From 1000, not 0: a deadline computed wrongly from the start time (1000 * 300,
        # say) would be far off and never reached; from 0 it is 0 either way
        clock = iter(range(1000, 20_000, 7))
        monkeypatch.setattr(http_client.time, "monotonic", lambda: next(clock))
        read: list = []

        class Counted(FakeResponse):
            def iter_content(self, chunk_size: int = 65536):
                for piece in super().iter_content(chunk_size):
                    read.append(piece)
                    yield piece

        with pytest.raises(requests.exceptions.ReadTimeout):
            read_capped_text(Counted(b"x" * 100, chunk=1), max_seconds=300)
        # 7 s a chunk: 300 s is passed around the 43rd of the 100
        assert len(read) < 50

    def test_a_byte_now_and_then_inside_one_chunk_is_cut_off_too(self):
        # A server announcing a long body and sending a byte every so often held
        # one chunk's read for as long as it liked: each byte restarted the read
        # timeout, and the deadline was only looked at between chunks
        import socket
        import threading
        import time

        import requests

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        stop = threading.Event()

        def trickle() -> None:
            connection, _ = listener.accept()
            with connection:
                connection.recv(65536)
                connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 100000\r\n\r\n")
                while not stop.is_set():
                    try:
                        connection.sendall(b"x")
                    except OSError:
                        return
                    stop.wait(0.2)

        server = threading.Thread(target=trickle, daemon=True)
        server.start()
        try:
            response = requests.get(  # noqa: S113 — a loopback server this test started; timeout given
                f"http://127.0.0.1:{listener.getsockname()[1]}/", stream=True, timeout=(5, 5))
            started = time.monotonic()
            with pytest.raises(requests.exceptions.ReadTimeout):
                read_capped_text(response, max_seconds=1)
            assert time.monotonic() - started < 4
        finally:
            stop.set()
            listener.close()
            server.join(5)

    def test_a_timely_answer_is_read_whole(self):
        assert read_capped_text(FakeResponse(b"x" * 100, chunk=1), max_seconds=300) == "x" * 100

    def test_the_deadline_reads_as_a_timeout_to_the_user(self):
        import requests

        from pybreeze.utils.network.http_client import describe_request_error

        assert "timed out" in describe_request_error(requests.exceptions.ReadTimeout("slow"))


class TestWhatTheReadSkipsAndPassesOn:
    def test_empty_chunks_are_skipped(self):
        # A chunked or kept-alive stream can hand back an empty chunk between real ones
        class Gappy(FakeResponse):
            def iter_content(self, chunk_size: int = 65536):
                yield from (b"", b"ab", b"", b"c")

        assert read_capped_text(Gappy(b""), max_bytes=10) == "abc"

    def test_an_error_the_watchdog_did_not_cause_is_raised(self):
        import requests

        class Broken(FakeResponse):
            def iter_content(self, chunk_size: int = 65536):
                yield b"ab"
                raise requests.exceptions.ChunkedEncodingError("connection broken")

        response = Broken(b"")
        with pytest.raises(requests.exceptions.ChunkedEncodingError):
            read_capped_text(response, max_bytes=10)
        assert response.closed


class TestTheWatchdog:
    def test_a_cancelled_watchdog_does_nothing_when_its_time_comes(self):
        from pybreeze.utils.network.http_client import _Watchdog

        response = FakeResponse(b"")
        watchdog = _Watchdog(response, 60)
        watchdog.cancel()
        watchdog._fire()  # the timer, had it fired late

        assert not watchdog.fired
        assert not response.closed

    def test_a_connection_that_cannot_be_shut_is_logged_not_raised(self):
        # On the timer's thread an exception would go nowhere and leave the read waiting
        from pybreeze.utils.network.http_client import _Watchdog

        def refuse():
            raise OSError("already closed")

        response = FakeResponse(b"")
        response.raw = SimpleNamespace(shutdown=refuse)
        watchdog = _Watchdog(response, 60)
        watchdog._fire()

        assert watchdog.fired
        watchdog.cancel()


def _compressed(encoding: str, megabytes: int) -> bytes:
    """*megabytes* of zeros compressed as HTTP's *encoding* names it, built a megabyte at a time."""
    import zlib

    block = bytes(1024 * 1024)
    if encoding == "br":
        brotli = pytest.importorskip("brotli")
        compressor = brotli.Compressor(quality=5)
        return b"".join(compressor.process(block) for _ in range(megabytes)) + compressor.finish()
    compressor = zlib.compressobj(wbits=31 if encoding == "gzip" else 15)
    return b"".join(compressor.compress(block) for _ in range(megabytes)) + compressor.flush()


class TestACompressedBomb:
    """The cap counts what the body decodes to, and decoding stops with it.

    A body of a few hundred bytes can decode to hundreds of megabytes. urllib3
    before 2.7.0 decoded all the rest of a Brotli body on the second read
    (CVE-2026-44432); read chunk by chunk here, it did not, and this keeps it so.
    """

    @pytest.mark.parametrize("encoding", ["gzip", "deflate", "br"])
    def test_it_is_refused_at_the_cap_without_being_decoded_whole(self, encoding):
        import http.server
        import threading
        import tracemalloc

        import requests

        payload = _compressed(encoding, 128)

        class Bomb(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Encoding", encoding)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Bomb)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        tracemalloc.start()
        try:
            response = requests.get(  # noqa: S113 — a loopback server this test started; timeout given
                f"http://127.0.0.1:{server.server_port}/", stream=True, timeout=(5, 30))
            with pytest.raises(ResponseTooLargeError):
                read_capped_text(response, max_bytes=1024 * 1024)
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            server.shutdown()
            server.server_close()

        assert peak < 32 * 1024 * 1024

"""The AI review panel: what it keeps on disk, what it logs, and what it shows.

An API URL can carry a token in its query, which this project treats as a
credential, so the panel records only that a URL was seen before.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.url import ai_code_review_gui
from pybreeze.pybreeze_ui.connect_gui.url.ai_code_review_gui import (
    AICodeReviewClient, looks_like_a_fingerprint, url_fingerprint,
)

_A_URL = "https://api.example/v1/review?api_key=sk-live-not-a-real-key"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def client(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ai_code_review_gui, "pybreeze_data_dir", lambda: tmp_path)
    made = AICodeReviewClient()
    yield made
    made.deleteLater()


def stored(client) -> str:
    from pathlib import Path

    return Path(client.url_file).read_text(encoding="utf-8")


class TestRecordingAUrl:
    def test_the_url_itself_never_reaches_the_file(self, client):
        assert client.record_url(_A_URL) is True

        text = stored(client)
        assert _A_URL not in text
        assert "sk-live-not-a-real-key" not in text
        assert url_fingerprint(_A_URL) in text

    def test_a_url_sent_before_is_recognised(self, client):
        client.record_url(_A_URL)

        assert client.record_url(_A_URL) is False

    def test_a_different_url_is_new(self, client):
        client.record_url(_A_URL)

        assert client.record_url("https://api.example/v2/review") is True

    def test_a_file_from_an_older_version_is_rewritten_as_fingerprints(self, client):
        from pathlib import Path

        Path(client.url_file).write_text(
            f"{_A_URL}\nhttps://other.example/review\n", encoding="utf-8")

        assert client.record_url(_A_URL) is False, "it was recorded before, in plain text"

        text = stored(client)
        assert "api.example" not in text
        assert "other.example" not in text
        assert url_fingerprint("https://other.example/review") in text
        assert all(looks_like_a_fingerprint(line) for line in text.split() if line)


class TestTheRequestItself:
    """The request runs on its own thread; its two signals are what reaches the UI."""

    def _run(self, monkeypatch, response=None, raises=None, method="GET"):
        from pybreeze.pybreeze_ui.connect_gui.url.ai_code_review_gui import ReviewRequestThread

        monkeypatch.setattr(ai_code_review_gui, "validate_url", lambda url: url)
        if raises is None:
            monkeypatch.setattr(
                ai_code_review_gui.requests, method.lower(), lambda *a, **k: response)
            monkeypatch.setattr(ai_code_review_gui, "read_capped_text", lambda resp: resp.text)
        else:
            def refuse(*_args, **_kwargs):
                raise raises

            monkeypatch.setattr(ai_code_review_gui.requests, method.lower(), refuse)
        thread = ReviewRequestThread(method, _A_URL, "print(1)")
        answered: list = []
        failed: list = []
        thread.answered.connect(answered.append)
        thread.failed.connect(failed.append)
        thread.run()
        return answered, failed

    def test_an_answer_reaches_the_panel(self, app, monkeypatch):
        class Response:
            ok = True
            status_code = 200
            reason = "OK"
            text = "looks fine to me"

        answered, failed = self._run(monkeypatch, Response())

        assert answered == ["looks fine to me"]
        assert failed == []

    def test_a_failed_status_is_reported_instead_of_an_empty_panel(self, app, monkeypatch):
        class Response:
            ok = False
            status_code = 500
            reason = "Internal Server Error"
            text = ""

        answered, failed = self._run(monkeypatch, Response())

        assert answered and "500" in answered[0]

    def test_a_request_that_fails_does_not_log_the_url(self, app, monkeypatch):
        logged: list = []
        monkeypatch.setattr(
            ai_code_review_gui.pybreeze_logger, "error",
            lambda message, *args: logged.append(message % args))
        error = ai_code_review_gui.requests.ConnectionError(
            f"HTTPSConnectionPool(host='api.example'): Max retries exceeded with url: {_A_URL}")

        answered, failed = self._run(monkeypatch, raises=error)

        assert failed, "the panel was told nothing"
        assert logged and all("sk-live-not-a-real-key" not in line for line in logged)

    def test_a_url_that_cannot_be_sent_to_is_reported_not_raised(self, app, monkeypatch):
        from pybreeze.pybreeze_ui.connect_gui.url.ai_code_review_gui import ReviewRequestThread

        thread = ReviewRequestThread("GET", "http://.example", "print(1)")
        failed: list = []
        thread.failed.connect(failed.append)

        thread.run()

        assert failed


class TestWhileARequestIsInFlight:
    class NeverEnding:
        def isRunning(self) -> bool:
            return True

    def test_a_second_send_is_ignored(self, client, monkeypatch):
        started: list = []
        monkeypatch.setattr(
            ai_code_review_gui, "ReviewRequestThread",
            lambda *args: started.append(args))
        client.url_input.setText(_A_URL)
        client.request_thread = self.NeverEnding()

        client.send_request()

        assert started == []

    def test_closing_lets_it_run_out_without_waiting(self, client):
        from unittest.mock import MagicMock

        from pybreeze.pybreeze_ui import thread_keeper

        thread = MagicMock()
        thread.isRunning.return_value = True
        client.request_thread = thread

        client.close()

        thread.wait.assert_not_called()
        thread.answered.disconnect.assert_called_once()
        thread.failed.disconnect.assert_called_once()
        assert thread_keeper.is_kept(thread)
        thread_keeper._OUTLIVING_THEIR_WIDGET.discard(thread)

    def test_an_unsupported_method_says_so_and_starts_nothing(self, client, monkeypatch):
        started: list = []
        monkeypatch.setattr(
            ai_code_review_gui, "ReviewRequestThread", lambda *args: started.append(args))
        client.url_input.setText(_A_URL)
        client.method_box.addItem("TRACE")
        client.method_box.setCurrentText("TRACE")

        client.send_request()

        assert started == []
        assert client.response_panel.toPlainText()

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


class TestSending:
    def _answer_with(self, monkeypatch, response):
        monkeypatch.setattr(ai_code_review_gui, "validate_url", lambda url: url)
        monkeypatch.setattr(ai_code_review_gui.requests, "get", lambda *a, **k: response)
        monkeypatch.setattr(ai_code_review_gui, "read_capped_text", lambda resp: resp.text)

    def test_a_failed_status_is_reported_instead_of_an_empty_panel(self, client, monkeypatch):
        class Response:
            ok = False
            status_code = 500
            reason = "Internal Server Error"
            text = ""

        self._answer_with(monkeypatch, Response())
        client.url_input.setText(_A_URL)

        client.send_request()

        assert "500" in client.response_panel.toPlainText()

    def test_a_request_that_fails_does_not_log_the_url(self, client, monkeypatch):
        logged: list = []
        monkeypatch.setattr(ai_code_review_gui, "validate_url", lambda url: url)
        monkeypatch.setattr(
            ai_code_review_gui.pybreeze_logger, "error",
            lambda message, *args: logged.append(message % args))

        def refuse(*_args, **_kwargs):
            raise ai_code_review_gui.requests.ConnectionError(
                f"HTTPSConnectionPool(host='api.example'): Max retries exceeded with url: {_A_URL}")

        monkeypatch.setattr(ai_code_review_gui.requests, "get", refuse)
        client.url_input.setText(_A_URL)

        client.send_request()

        assert logged, "nothing was logged"
        assert all("sk-live-not-a-real-key" not in line for line in logged)

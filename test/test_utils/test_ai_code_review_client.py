"""The AI review panel: what it keeps on disk, what it logs, and what it shows.

An API URL can carry a token in its query, which this project treats as a
credential, so the panel records only that a URL was seen before.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThread, Signal
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


class _FakeSession:
    """The session a request goes through, handing every request to *request*."""

    def __init__(self, request) -> None:
        self.request = request

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        """Nothing to close."""


class TestTheRequestItself:
    """The request runs on its own thread; its two signals are what reaches the UI."""

    def _run(self, monkeypatch, response=None, raises=None, method="GET"):
        from pybreeze.pybreeze_ui.connect_gui.url.ai_code_review_gui import ReviewRequestThread

        monkeypatch.setattr(ai_code_review_gui, "validate_url", lambda url: url)
        sent: list = []

        def request(sent_method, *_args, **_kwargs):
            sent.append(sent_method)
            if raises is not None:
                raise raises
            return response

        monkeypatch.setattr(ai_code_review_gui, "public_session", lambda: _FakeSession(request))
        monkeypatch.setattr(ai_code_review_gui, "read_capped_text", lambda resp: resp.text)
        thread = ReviewRequestThread(method, _A_URL, "print(1)")
        answered: list = []
        failed: list = []
        thread.answered.connect(answered.append)
        thread.failed.connect(failed.append)
        thread.run()
        assert sent == [method]  # sent with the method chosen in the panel
        return answered, failed

    def test_no_code_is_not_sent_in_a_body(self, client, monkeypatch):
        # An empty code field went out, and the answer was about nothing
        started: list = []
        monkeypatch.setattr(ai_code_review_gui, "ReviewRequestThread", lambda *args: started.append(args))
        client.url_input.setText(_A_URL)
        client.code_input.setPlainText(" \n")

        client.send_request()

        assert started == []
        assert client.response_panel.toPlainText() == client.word_dict.get(
            "ai_code_review_gui_message_paste_code")

    def test_a_method_without_a_body_needs_no_code(self, client, monkeypatch):
        started: list = []
        monkeypatch.setattr(ai_code_review_gui, "ReviewRequestThread", lambda *args: started.append(args) or _Silent())
        monkeypatch.setattr(client, "record_url", lambda url: True)
        client.url_input.setText(_A_URL)
        client.method_box.setCurrentText("GET")

        client.send_request()

        assert [args[0] for args in started] == ["GET"]
        client.request_thread.wait(5000)

    def test_the_code_goes_as_pasted(self, client, monkeypatch):
        # It was stripped: the first line of a selection from inside a function lost its indent
        started: list = []
        monkeypatch.setattr(ai_code_review_gui, "ReviewRequestThread", lambda *args: started.append(args) or _Silent())
        monkeypatch.setattr(client, "record_url", lambda url: True)
        client.url_input.setText(_A_URL)
        client.code_input.setPlainText("    total = 1\n    return total\n")

        client.send_request()

        assert started[0][2] == "    total = 1\n    return total\n"
        client.request_thread.wait(5000)

    def test_a_new_panel_sends_the_code(self, client):
        # It started on GET, which sends no body: the code pasted went nowhere
        assert client.method_box.currentText() in ai_code_review_gui.METHODS_WITH_A_BODY

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

        # A failure, not an answer: an answer can be voted on.
        assert answered == []
        assert failed and "500" in failed[0]

    def test_a_redirect_is_reported_not_shown_as_an_empty_answer(self, app, monkeypatch):
        # requests calls every status below 400 "ok", a 302 included.
        class Response:
            ok = True
            status_code = 302
            reason = "Found"
            text = ""

        answered, failed = self._run(monkeypatch, Response())

        assert answered == []
        assert failed and failed[0].startswith("HTTP 302 Found")

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


class TestVotingOnAnAnswer:
    def test_there_is_nothing_to_vote_on_before_an_answer(self, client):
        # It used to count a vote with an empty panel.
        assert not client.accept_button.isEnabled()
        assert not client.reject_button.isEnabled()

    def test_an_answer_can_be_voted_on_once(self, client):
        client.on_answered("looks fine")
        assert client.accept_button.isEnabled() and client.reject_button.isEnabled()

        client.accept_button.click()

        assert not client.accept_button.isEnabled()
        assert not client.reject_button.isEnabled()

    def test_a_failure_cannot_be_voted_on(self, client):
        client.on_failed("HTTP 500 Internal Server Error\n")

        assert not client.accept_button.isEnabled()


class _Silent(QThread):
    """A request that ends without emitting answered or failed."""

    answered = Signal(str)
    failed = Signal(str)

    def __init__(self, *_args) -> None:
        super().__init__()

    def run(self) -> None:
        """Nothing to report."""


class TestSendComesBack:
    def test_however_the_request_ended(self, client, monkeypatch):
        monkeypatch.setattr(ai_code_review_gui, "ReviewRequestThread", _Silent)
        monkeypatch.setattr(client, "record_url", lambda url: True)
        client.url_input.setText(_A_URL)
        client.code_input.setPlainText("print(1)")

        client.send_request()
        assert not client.send_button.isEnabled()
        client.request_thread.wait(5000)
        QApplication.processEvents()

        assert client.send_button.isEnabled()


class TestTheRunningTotals:
    def test_a_new_panel_carries_on_from_the_saved_totals(self, app, tmp_path, monkeypatch):
        (tmp_path / "response_stats.txt").write_text("Accepted: 7\nRejected: 2\n", encoding="utf-8")
        monkeypatch.setattr(ai_code_review_gui, "pybreeze_data_dir", lambda: tmp_path)
        panel = AICodeReviewClient()

        panel.accept_response()

        # It used to start from 0 and write "Accepted: 1" over the 7.
        assert (tmp_path / "response_stats.txt").read_text(encoding="utf-8") == "Accepted: 8\nRejected: 2\n"
        panel.deleteLater()

    @pytest.mark.parametrize("text", [
        "", "garbage", "Accepted: -3\nRejected: x", "Accepted: " + "9" * 40, "Accepted 5",
    ])
    def test_a_file_that_is_not_ours_counts_as_none(self, tmp_path, text):
        from pybreeze.pybreeze_ui.connect_gui.url.ai_code_review_gui import read_stats

        path = tmp_path / "response_stats.txt"
        path.write_text(text, encoding="utf-8")

        assert read_stats(str(path)) == (0, 0)

    def test_a_missing_or_unreadable_file_counts_as_none(self, tmp_path):
        from pybreeze.pybreeze_ui.connect_gui.url.ai_code_review_gui import read_stats

        assert read_stats(str(tmp_path / "absent.txt")) == (0, 0)
        binary = tmp_path / "binary.txt"
        binary.write_bytes(b"\xff\xfe\x00")
        assert read_stats(str(binary)) == (0, 0)


class TestASentUrlsFileThatCannotBeUsed:
    def test_a_damaged_file_does_not_stop_the_request(self, client):
        from pathlib import Path

        Path(client.url_file).write_bytes(b"\xff\xfe not utf-8")

        # It used to raise from the Send slot, on every click.
        assert client.record_url(_A_URL) is True
        assert url_fingerprint(_A_URL) in stored(client)

    def test_a_file_that_cannot_be_written_does_not_stop_the_request(self, client, monkeypatch):
        from pathlib import Path

        def refuse(*_args, **_kwargs):
            raise PermissionError(13, "Access is denied")

        monkeypatch.setattr(Path, "write_text", refuse)

        assert client.record_url(_A_URL) is True


class TestTwoPanelsOpenAtOnce:
    def test_neither_writes_away_the_others_votes(self, app, tmp_path, monkeypatch):
        (tmp_path / "response_stats.txt").write_text("Accepted: 5\nRejected: 5\n", encoding="utf-8")
        monkeypatch.setattr(ai_code_review_gui, "pybreeze_data_dir", lambda: tmp_path)
        first, second = AICodeReviewClient(), AICodeReviewClient()

        for _ in range(3):
            first.accept_response()
        second.reject_response()

        # The second panel used to count on from the 5/5 it read at opening
        # and save 5/6, losing the first panel's three accepts.
        assert (tmp_path / "response_stats.txt").read_text(encoding="utf-8") == "Accepted: 8\nRejected: 6\n"
        first.deleteLater()
        second.deleteLater()


class TestWhatTheAnswerLooksLike:
    def test_an_answer_about_html_is_shown_as_text(self, client):
        # append() read it as rich text: the tags vanished and <img> was loaded
        answer = '<b>Use</b> <script>alert(1)</script> instead of <img src="x"> here'

        client.on_answered(answer)
        client.accept_response()

        text = client.response_panel.toPlainText()
        assert text.startswith(answer)
        assert "<img" not in client.response_panel.toHtml().replace("&lt;img", "")

    def test_a_long_error_page_is_cut_short(self, app, monkeypatch):
        class Response:
            status_code = 500
            reason = "Internal Server Error"
            ok = False
            is_redirect = False
            headers: dict = {}
            encoding = "utf-8"

        monkeypatch.setattr(ai_code_review_gui, "validate_url", lambda url: None)
        monkeypatch.setattr(ai_code_review_gui, "public_session", lambda: _FakeSession(lambda *_a, **_k: Response()))
        monkeypatch.setattr(ai_code_review_gui, "read_capped_text", lambda response: "x" * 1_000_000)
        thread = ai_code_review_gui.ReviewRequestThread("POST", _A_URL, "code")
        failed: list = []
        thread.failed.connect(failed.append)
        thread.run()

        assert len(failed[0]) < 20_000


class TestSavingTheTotals:
    def test_a_save_that_fails_keeps_the_totals_on_disk(self, client, monkeypatch):
        # The file was opened for writing, emptied first
        from pathlib import Path

        from pybreeze.utils.file_process import replace_file

        Path(client.stats_file).write_text("Accepted: 5\nRejected: 2\n", encoding="utf-8")

        def refuse(*_args):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(replace_file.os, "replace", refuse)
        client.on_answered("fine")
        client.accept_response()

        assert Path(client.stats_file).read_text(encoding="utf-8") == "Accepted: 5\nRejected: 2\n"
        assert "No space left on device" in client.response_panel.toPlainText()
        assert str(client.stats_file) not in client.response_panel.toPlainText()

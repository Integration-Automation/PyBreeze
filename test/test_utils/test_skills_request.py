"""What a Skills request reports for each kind of answer the endpoint gives."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import requests

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.extend_ai_gui.skills import skills_send_gui
from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import RequestThread

_URL = "https://skills.example/api"


@pytest.fixture(scope="module", autouse=True)
def app():
    from PySide6.QtWidgets import QApplication

    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class FakeResponse:
    def __init__(self, status_code: int, body: str = "", location: str | None = None) -> None:
        self.status_code = status_code
        self.ok = status_code < 400
        self.is_redirect = location is not None
        self.headers = {"Location": location} if location else {}
        self.encoding = "utf-8"
        self._body = body.encode("utf-8")

    def iter_content(self, chunk_size: int = 65536):
        yield self._body

    def close(self) -> None:
        """Nothing to close."""


class FakeSession:
    """The session a request is sent through, answering every post with *post*."""

    def __init__(self, post) -> None:
        self.post = post

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        """Nothing to close."""


def _run(monkeypatch, answer) -> tuple[list[str], list[str]]:
    """Run one request against *answer* (a response, or an exception to raise)."""
    monkeypatch.setattr(skills_send_gui, "validate_url", lambda url: url)

    def post(*_args, **_kwargs):
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(skills_send_gui, "public_session", lambda: FakeSession(post))
    answered: list[str] = []
    errors: list[str] = []
    thread = RequestThread(_URL, "print(1)")
    thread.answered.connect(answered.append)
    thread.error.connect(errors.append)
    thread.run()  # on this thread: direct connections, no event loop needed
    return answered, errors


class TestWhatARequestReports:
    def test_a_good_answer_is_shown_as_is(self, monkeypatch):
        assert _run(monkeypatch, FakeResponse(200, "looks fine")) == (["looks fine"], [])

    def test_a_redirect_is_shown_with_where_it_went(self, monkeypatch):
        answered, errors = _run(monkeypatch, FakeResponse(302, location="https://elsewhere.example"))

        assert errors == []
        assert "302" in answered[0] and "Redirect (not followed) to https://elsewhere.example" in answered[0]

    def test_a_redirect_shows_only_the_host_it_names(self, monkeypatch):
        # A trailing-slash redirect repeats the query, and the token in it was shown
        answered, _errors = _run(monkeypatch, FakeResponse(
            301, location="https://user:pw@api.example:8443/x/?key=SECRET"))

        assert "https://api.example:8443" in answered[0]
        assert "SECRET" not in answered[0] and "pw" not in answered[0] and "/x/" not in answered[0]

    @pytest.mark.parametrize("status", [401, 403])
    def test_a_refusal_is_an_error(self, monkeypatch, status):
        answered, errors = _run(monkeypatch, FakeResponse(status, "no"))

        assert answered == []
        assert str(status) in errors[0] and "Authentication/Authorization failed" in errors[0]

    def test_a_server_error_is_an_error_with_its_body(self, monkeypatch):
        answered, errors = _run(monkeypatch, FakeResponse(503, "overloaded"))

        assert answered == []
        assert "503" in errors[0] and "Server error: overloaded" in errors[0]

    def test_another_client_error_is_shown_with_its_body(self, monkeypatch):
        answered, errors = _run(monkeypatch, FakeResponse(422, "bad field"))

        assert errors == []
        assert "422" in answered[0] and "bad field" in answered[0]

    def test_a_failed_request_is_an_error(self, monkeypatch):
        answered, errors = _run(monkeypatch, requests.ConnectionError("refused"))

        assert answered == []
        assert "could not connect to the server" in errors[0]


def test_a_failed_request_does_not_log_the_url(monkeypatch):
    # A requests error names the whole URL, and an API URL may carry a token.
    logged: list = []
    monkeypatch.setattr(
        skills_send_gui.pybreeze_logger, "error",
        lambda message, *args: logged.append(message % args))

    _run(monkeypatch, requests.ConnectionError(
        "Max retries exceeded with url: /v1?token=not-a-real-token"))

    assert logged and all("not-a-real-token" not in line for line in logged)

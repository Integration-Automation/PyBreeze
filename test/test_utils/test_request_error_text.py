"""A failed request is described to the user without its URL.

A ``requests`` error quotes the URL, path and query included, and an API URL
may carry a token. The logs already left it out; the panels showed it.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import requests

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.utils.network.http_client import ResponseTooLargeError, describe_request_error
from pybreeze.utils.network.url_validation import UnsafeURLError

_SECRET = "sk-live-not-a-real-key"
_URL = f"https://api.example/v1/review?api_key={_SECRET}"
_QUOTING_THE_URL = f"HTTPSConnectionPool(host='api.example', port=443): Max retries exceeded with url: {_URL}"


@pytest.fixture(scope="module", autouse=True)
def app():
    from PySide6.QtWidgets import QApplication

    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class _Refusing:
    """A session whose every request raises *error*."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        """Nothing to close."""

    def close(self) -> None:
        """Nothing to close."""

    def post(self, *_args, **_kwargs):
        raise self._error

    def request(self, *_args, **_kwargs):
        raise self._error


class TestDescribeRequestError:
    @pytest.mark.parametrize(("error", "words"), [
        (requests.ConnectTimeout(_QUOTING_THE_URL), "timed out"),
        (requests.ReadTimeout(_QUOTING_THE_URL), "timed out"),
        (requests.exceptions.SSLError(_QUOTING_THE_URL), "secure connection"),
        (requests.ConnectionError(_QUOTING_THE_URL), "could not connect"),
        (requests.TooManyRedirects(_QUOTING_THE_URL), "too many redirects"),
        (requests.exceptions.InvalidURL(_QUOTING_THE_URL), "not valid"),
        (requests.RequestException(_QUOTING_THE_URL), "RequestException"),
    ])
    def test_it_says_what_happened_and_not_where(self, error, words):
        text = describe_request_error(error)

        assert words in text
        assert _SECRET not in text
        assert "api.example" not in text

    def test_the_size_cap_and_the_ssrf_check_keep_their_own_words(self):
        assert describe_request_error(ResponseTooLargeError("too big")) == "too big"
        assert describe_request_error(UnsafeURLError("blocked")) == "blocked"


def test_the_skills_panel_does_not_show_the_url(monkeypatch):
    from pybreeze.pybreeze_ui.extend_ai_gui.skills import skills_send_gui

    monkeypatch.setattr(skills_send_gui, "validate_url", lambda url: url)
    monkeypatch.setattr(
        skills_send_gui, "public_session", lambda: _Refusing(requests.ConnectionError(_QUOTING_THE_URL)))
    errors: list = []
    thread = skills_send_gui.RequestThread(_URL, "print(1)")
    thread.error.connect(errors.append)

    thread.run()

    assert errors
    assert all(_SECRET not in error for error in errors)


def test_the_review_client_does_not_show_the_url(monkeypatch):
    from pybreeze.pybreeze_ui.connect_gui.url import ai_code_review_gui

    monkeypatch.setattr(ai_code_review_gui, "validate_url", lambda url: url)
    monkeypatch.setattr(
        ai_code_review_gui, "public_session", lambda: _Refusing(requests.ConnectionError(_QUOTING_THE_URL)))
    failed: list = []
    thread = ai_code_review_gui.ReviewRequestThread("POST", _URL, "print(1)")
    thread.failed.connect(failed.append)

    thread.run()

    assert failed
    assert all(_SECRET not in message for message in failed)


def test_the_cot_review_does_not_show_the_url():
    from pybreeze.pybreeze_ui.extend_ai_gui.code_review.code_review_thread import SenderThread

    thread = SenderThread(files=["linter.md"], code="print(1)", url=_URL)

    reply, answered = thread._ask(_Refusing(requests.ConnectionError(_QUOTING_THE_URL)), "linter.md", "prompt")

    assert not answered
    assert _SECRET not in reply
    assert "could not connect" in reply

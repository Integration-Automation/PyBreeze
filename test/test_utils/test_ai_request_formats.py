"""What the AI panels send, as the README tells whoever writes the endpoint.

AI Code Review: the form field ``code`` in a POST or PUT body. Skill Send: the
JSON ``{"code": ...}`` holding the prompt. (CoT Code Review's JSON
``{"prompt": ...}`` is checked in ``test_cot_session_reuse.py``.)
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pybreeze.pybreeze_ui.connect_gui.url import ai_code_review_gui
from pybreeze.pybreeze_ui.extend_ai_gui.skills import skills_send_gui

_URL = "https://llm.example.com/api"


class _Response:
    ok = True
    status_code = 200
    reason = "OK"
    text = "fine"


class _Session:
    """Records what is sent; used as ``public_session()`` or as its context."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        """Nothing to close."""

    def request(self, method, _url, **kwargs):
        self.sent.append((method, kwargs))
        return _Response()

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


@pytest.fixture
def session(monkeypatch):
    recorder = _Session()
    for module in (ai_code_review_gui, skills_send_gui):
        monkeypatch.setattr(module, "validate_url", lambda url: url)
        monkeypatch.setattr(module, "public_session", lambda: recorder)
        monkeypatch.setattr(module, "read_capped_text", lambda response: response.text)
    return recorder


@pytest.mark.parametrize("method", ai_code_review_gui.METHODS_WITH_A_BODY)
def test_ai_code_review_sends_the_code_as_a_form_field(session, method):
    ai_code_review_gui.ReviewRequestThread(method, _URL, "print(1)").run()
    assert [(sent, kwargs["data"]) for sent, kwargs in session.sent] == [(method, {"code": "print(1)"})]


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_ai_code_review_sends_the_url_alone_otherwise(session, method):
    ai_code_review_gui.ReviewRequestThread(method, _URL, "print(1)").run()
    assert "data" not in session.sent[0][1] and "json" not in session.sent[0][1]


def test_skill_send_posts_the_prompt_as_json_code(session):
    skills_send_gui.RequestThread(_URL, "Explain this code").run()
    assert [(method, kwargs["json"]) for method, kwargs in session.sent] == [("POST", {"code": "Explain this code"})]

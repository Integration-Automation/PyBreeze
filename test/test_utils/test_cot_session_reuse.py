from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body
        self.encoding = "utf-8"
        self.closed = False

    def iter_content(self, chunk_size: int = 65536):
        yield self._body

    def close(self):
        self.closed = True


class _FakeSession:
    """Records every post call so we can assert one session served them all."""

    def __init__(self):
        self.post_calls = []
        self.closed = False

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return _FakeResponse(b"reply for prompt")

    def close(self):
        self.closed = True


def _qt_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_one_session_serves_all_templates():
    _qt_app()
    from pybreeze.pybreeze_ui.extend_ai_gui.code_review.code_review_thread import SenderThread
    from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import COT_TEMPLATE_FILES

    thread = SenderThread(files=list(COT_TEMPLATE_FILES), code="print('x')", url="https://example.com/api")
    received = []
    thread.update_response.connect(lambda name, resp: received.append((name, resp)))

    session = _FakeSession()
    thread._run_templates(session, "print('x')")

    # Every template posts through the SAME session (connection reuse) ...
    assert len(session.post_calls) == len(COT_TEMPLATE_FILES)
    # ... always to the configured URL ...
    assert all(url == "https://example.com/api" for url, _ in session.post_calls)
    # ... with streaming + no redirects preserved.
    assert all(kw.get("stream") is True and kw.get("allow_redirects") is False
               for _, kw in session.post_calls)
    # ... and each produced a UI response — including the final total summary,
    # which a `case _: continue` used to drop before it reached the UI.
    assert len(received) == len(COT_TEMPLATE_FILES)
    assert "total_summary.md" in {name for name, _ in received}


def test_run_closes_session_even_on_error(monkeypatch):
    _qt_app()
    from pybreeze.pybreeze_ui.extend_ai_gui.code_review import code_review_thread as mod
    from pybreeze.pybreeze_ui.extend_ai_gui.code_review.code_review_thread import SenderThread

    created = {}

    class _TrackedSession(_FakeSession):
        def __init__(self):
            super().__init__()
            created["session"] = self

    monkeypatch.setattr(mod.requests, "Session", _TrackedSession)
    # Make the work raise to prove the finally still closes the session.
    monkeypatch.setattr(SenderThread, "_run_templates",
                        lambda self, session, code: (_ for _ in ()).throw(RuntimeError("boom")))

    thread = SenderThread(files=[], code="", url="https://example.com/api")
    try:
        thread.run()
    except RuntimeError:
        pass
    assert created["session"].closed is True

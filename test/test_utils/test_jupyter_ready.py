from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        try:
            app = QApplication([])
        except Exception as exc:  # pragma: no cover - no usable Qt platform
            pytest.skip(f"Cannot start QApplication: {exc}")
    return app


class _DeadProcess:
    returncode = 1

    class _Stderr:
        @staticmethod
        def read(size=-1):
            text = "ImportError: jupyterlab not installed"
            return text if size < 0 else text[:size]

    stderr = _Stderr()

    @staticmethod
    def poll():
        return 1


class _AliveProcess:
    returncode = None
    stderr = None

    @staticmethod
    def poll():
        return None


def _thread(qt_app):
    from pybreeze.pybreeze_ui.jupyter_lab_gui.jupyter_lab_thread import JupyterLauncherThread
    return JupyterLauncherThread(startup_timeout=5)


class TestWaitUntilReady:
    def test_early_exit_fails_fast(self, qt_app):
        thread = _thread(qt_app)
        thread.process = _DeadProcess()
        with pytest.raises(RuntimeError) as exc:
            thread._wait_until_ready(59999)
        assert "exited early" in str(exc.value)
        assert "jupyterlab not installed" in str(exc.value)

    def test_returns_when_port_open(self, qt_app, monkeypatch):
        thread = _thread(qt_app)
        thread.process = _AliveProcess()
        monkeypatch.setattr(thread, "_port_open", lambda port: True)
        # Should return without raising and without sleeping.
        assert thread._wait_until_ready(59999) is None

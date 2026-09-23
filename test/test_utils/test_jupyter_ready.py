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
        import tempfile

        thread = _thread(qt_app)
        thread.process = _DeadProcess()
        # What the server wrote goes to a file the launcher keeps, not a pipe.
        thread._output = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        thread._output.write("ImportError: jupyterlab not installed\n")
        with pytest.raises(RuntimeError) as exc:
            thread._wait_until_ready(59999)
        assert "exited early" in str(exc.value)
        assert "jupyterlab not installed" in str(exc.value)
        thread._output.close()

    def test_returns_when_port_open(self, qt_app, monkeypatch):
        thread = _thread(qt_app)
        thread.process = _AliveProcess()
        monkeypatch.setattr(thread, "_port_open", lambda port: True)
        # Should return without raising and without sleeping.
        assert thread._wait_until_ready(59999) is None


class TestRunCleansUpOnFailure:
    def test_startup_failure_terminates_orphan_process(self, qt_app, monkeypatch):
        import pybreeze.pybreeze_ui.jupyter_lab_gui.jupyter_lab_thread as mod

        class _RecordingProc:
            terminated = False

            def terminate(self):
                self.terminated = True

        proc = _RecordingProc()
        monkeypatch.setattr(mod, "get_venv_python", lambda: "python")
        monkeypatch.setattr(mod, "is_jupyter_installed", lambda exe: True)
        monkeypatch.setattr(mod, "find_free_port", lambda: 59999)
        monkeypatch.setattr(mod.subprocess, "Popen", lambda *a, **k: proc)

        thread = mod.JupyterLauncherThread(startup_timeout=5)

        def _boom(_port):
            raise TimeoutError("startup timeout")

        monkeypatch.setattr(thread, "_wait_until_ready", _boom)

        errors = []
        thread.error_occurred.connect(errors.append)
        thread.run()

        # The half-started server must be terminated, not left holding the port.
        assert proc.terminated is True
        assert errors


class TestWhatAFailureShows:
    def _run(self, monkeypatch, fail, stop_first=False):
        from pybreeze.pybreeze_ui.jupyter_lab_gui import jupyter_lab_thread as mod

        monkeypatch.setattr(mod, "choose_python", lambda _chosen: fail())
        thread = mod.JupyterLauncherThread()
        if stop_first:
            thread.stop()
        errors: list = []
        logged: list = []
        thread.error_occurred.connect(errors.append)
        monkeypatch.setattr(mod.pybreeze_logger, "error", lambda *args: logged.append(args))
        thread.run()
        return errors, logged

    def test_the_reason_reaches_the_tab_without_the_traceback(self, qt_app, monkeypatch):
        def no_venv():
            raise RuntimeError("Cannot find venv python executable")

        errors, logged = self._run(monkeypatch, no_venv)

        assert errors == ["Cannot find venv python executable"]
        assert logged  # the traceback still goes to the log

    def test_a_tab_closed_during_startup_is_not_a_failure(self, qt_app, monkeypatch):
        def exited():
            raise RuntimeError("JupyterLab exited early (code 1): ")

        # stop() ends the server; the wait then sees it gone. That used to be
        # logged as "JupyterLab launch failed".
        errors, logged = self._run(monkeypatch, exited, stop_first=True)

        assert errors == []
        assert logged == []

    def test_the_tab_says_why_as_plain_text(self, qt_app, monkeypatch):
        from pybreeze.extend_multi_language.update_language_dict import update_language_dict
        from pybreeze.pybreeze_ui.jupyter_lab_gui import jupyter_lab_widget
        from PySide6.QtCore import Qt

        update_language_dict()
        monkeypatch.setattr(jupyter_lab_widget.JupyterLauncherThread, "start", lambda self: None)
        tab = jupyter_lab_widget.JupyterLabWidget()

        tab.show_error("ERROR: <b>No matching distribution</b> for jupyterlab")

        # It used to say only "init failed".
        assert "No matching distribution" in tab.status_label.text()
        assert tab.status_label.textFormat() == Qt.TextFormat.PlainText
        tab.close()
        tab.deleteLater()


class TestWhichInterpreterRunsTheLab:
    def test_the_one_chosen_in_the_ide_comes_first(self, monkeypatch):
        from pybreeze.pybreeze_ui.jupyter_lab_gui import jupyter_lab_thread as mod

        monkeypatch.setattr(mod, "get_venv_python", lambda: "venv-python")

        assert mod.choose_python("C:/envs/project/python.exe") == "C:/envs/project/python.exe"
        assert mod.choose_python(None) == "venv-python"

    def test_without_a_venv_the_ides_own_is_used(self, monkeypatch):
        # It raised "Cannot find venv python executable" and the lab never started
        import sys

        from pybreeze.pybreeze_ui.jupyter_lab_gui import jupyter_lab_thread as mod

        def no_venv():
            raise RuntimeError("Cannot find venv python executable")

        monkeypatch.setattr(mod, "get_venv_python", no_venv)

        assert mod.choose_python(None) == sys.executable

    def test_installed_is_asked_of_the_interpreter_not_of_pip(self, tmp_path, monkeypatch):
        # A venv made without pip failed "pip show" with jupyterlab installed
        import os
        import subprocess
        import sys

        from pybreeze.pybreeze_ui.jupyter_lab_gui import jupyter_lab_thread as mod

        asked: list = []
        real_run = subprocess.run

        def run(argv, **kwargs):
            asked.append(argv)
            return real_run(argv, **kwargs)

        monkeypatch.setattr(mod.subprocess, "run", run)
        (tmp_path / "jupyterlab").mkdir()
        (tmp_path / "jupyterlab" / "__init__.py").write_text("", encoding="utf-8")

        monkeypatch.setenv("PYTHONPATH", str(tmp_path))
        found = mod.is_jupyter_installed(sys.executable)
        monkeypatch.setenv("PYTHONPATH", os.devnull)
        monkeypatch.setattr(mod, "_HAS_JUPYTERLAB", mod._HAS_JUPYTERLAB.replace("jupyterlab", "no_such_lab"))
        missing = mod.is_jupyter_installed(sys.executable)

        assert (found, missing) == (True, False)
        assert all("pip" not in argv for argv in asked)


def test_the_server_is_told_not_to_move_to_another_port(monkeypatch):
    # With port_retries left at 50 it moved to the next free port, and the tab
    # waited on the one it was given
    from pybreeze.pybreeze_ui.jupyter_lab_gui import jupyter_lab_thread as mod

    started: list = []
    monkeypatch.setattr(mod.subprocess, "Popen", lambda argv, **_kwargs: started.append(argv))
    mod.JupyterLauncherThread()._start_server("python", 8888)

    assert "--ServerApp.port_retries=0" in started[0]
    assert "--ServerApp.port=8888" in started[0]

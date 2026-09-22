"""The embedded JupyterLab: how its server is started, and that it goes when the tab does.

The server runs with no token, so the loopback bind and the same-origin rule are
what keep other software away from it; and it outlives its launcher thread, so the
tab has to stop it by name.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.jupyter_lab_gui import jupyter_lab_thread, jupyter_lab_widget
from test_utils.started_window import run_started_window

# The readiness wait as the launcher has it, before a test replaces it
_REAL_WAIT_UNTIL_READY = jupyter_lab_thread.JupyterLauncherThread._wait_until_ready


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class FakeServer:
    """Stands in for the JupyterLab process."""

    def __init__(self, argv, **options) -> None:
        self.argv = argv
        self.options = options
        self.terminated = False
        self.returncode = None

    def terminate(self) -> None:
        self.terminated = True

    def poll(self):
        return self.returncode


@pytest.fixture()
def launched(monkeypatch) -> list:
    """Start the launcher's run() against a fake server and collect what it started."""
    started: list = []

    def popen(argv, **options):
        server = FakeServer(argv, **options)
        started.append(server)
        return server

    monkeypatch.setattr(jupyter_lab_thread, "get_venv_python", lambda: "python")
    monkeypatch.setattr(jupyter_lab_thread, "is_jupyter_installed", lambda _python: True)
    monkeypatch.setattr(jupyter_lab_thread.subprocess, "Popen", popen)
    monkeypatch.setattr(
        jupyter_lab_thread.JupyterLauncherThread, "_wait_until_ready", lambda self, port: None)
    return started


class TestHowTheServerIsStarted:
    def test_it_is_bound_to_this_machine_and_takes_no_other_origin(self, app, launched):
        thread = jupyter_lab_thread.JupyterLauncherThread()

        thread.run()

        argv = launched[0].argv
        assert "--ServerApp.ip=localhost" in argv
        # With no token, a wildcard origin would let any page the user visits
        # drive this server's API and kernel sockets.
        assert not [arg for arg in argv if arg.startswith("--ServerApp.allow_origin")]
        thread.stop()

    def test_its_output_goes_to_a_file_not_a_pipe_nobody_reads(self, app, launched):
        import subprocess

        thread = jupyter_lab_thread.JupyterLauncherThread()

        thread.run()

        options = launched[0].options
        assert options["stdout"] is not subprocess.PIPE
        assert options["stderr"] is subprocess.STDOUT
        thread.stop()

    def test_an_early_exit_reports_what_the_server_said(self, app, launched, monkeypatch):
        thread = jupyter_lab_thread.JupyterLauncherThread(startup_timeout=5)
        thread.run()
        thread._output.write("ImportError: jupyterlab is broken\n")
        thread._output.flush()
        launched[0].returncode = 1
        monkeypatch.setattr(
            jupyter_lab_thread.JupyterLauncherThread, "_port_open", staticmethod(lambda port: False))

        with pytest.raises(RuntimeError, match="jupyterlab is broken"):
            _REAL_WAIT_UNTIL_READY(thread, 1)
        thread.stop()

    def test_stopping_twice_is_harmless(self, app, launched):
        thread = jupyter_lab_thread.JupyterLauncherThread()
        thread.run()

        thread.stop()
        thread.stop()

        assert launched[0].terminated


class FinishedLauncher:
    """A launcher whose thread has finished: the server it started is still up."""

    def __init__(self) -> None:
        self.stopped = False
        from PySide6.QtCore import QObject, Signal

        class Signals(QObject):
            status_update = Signal(str)
            server_ready = Signal(str)
            error_occurred = Signal(str)

        self._signals = Signals()
        self.status_update = self._signals.status_update
        self.server_ready = self._signals.server_ready
        self.error_occurred = self._signals.error_occurred

    def start(self) -> None:
        """Nothing to start in a stand-in."""

    def isRunning(self) -> bool:
        return False

    def stop(self) -> None:
        self.stopped = True


class TestClosingTheTab:
    def test_the_server_is_stopped_after_the_lab_has_loaded(self, app, monkeypatch):
        monkeypatch.setattr(jupyter_lab_widget, "JupyterLauncherThread", FinishedLauncher)
        tab = jupyter_lab_widget.JupyterLabWidget()

        tab.close()

        assert tab.thread.stopped


_CLOSE_WITH_A_TOOL_TAB_AND_DOCK = """
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from je_editor.pyside_ui.main_ui.dock.destroy_dock import DestroyDock
closed = []
class Tool(QWidget):
    def __init__(self, name):
        super().__init__()
        self.name = name
    def closeEvent(self, event):
        closed.append(self.name)
        super().closeEvent(event)
window.tab_widget.addTab(Tool("tab"), "Tool")
dock = DestroyDock()
dock.setWidget(Tool("dock"))
window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
window.close()
result = {"closed": sorted(closed)}
"""


def test_closing_the_ide_closes_its_own_tabs_and_docks(tmp_path):
    # JEditor closes editor tabs only; a JupyterLab server, an SSH session or a
    # diagram's downloads live in PyBreeze's own tabs and docks.
    seen = run_started_window(tmp_path, _CLOSE_WITH_A_TOOL_TAB_AND_DOCK)

    assert "tab" in seen["closed"]
    assert "dock" in seen["closed"]


class TestStoppingBeforeTheServerStarts:
    """A tab closed while the launcher checks or installs gets no server afterwards."""

    def test_a_stopped_launcher_starts_nothing(self, app, launched, monkeypatch):
        thread = jupyter_lab_thread.JupyterLauncherThread()

        def installed_while_the_tab_closes(_python: str) -> bool:
            thread.stop()  # the tab closes during the check (or the install)
            return True

        monkeypatch.setattr(jupyter_lab_thread, "is_jupyter_installed", installed_while_the_tab_closes)

        thread.run()

        assert launched == []

    def test_closing_the_tab_does_not_wait_for_the_launcher(self, app, monkeypatch):
        import threading
        import time

        from pybreeze.pybreeze_ui.thread_keeper import is_kept

        installing = threading.Event()
        monkeypatch.setattr(
            jupyter_lab_thread.JupyterLauncherThread, "run", lambda self: installing.wait(5))
        tab = jupyter_lab_widget.JupyterLabWidget()
        launcher = tab.thread

        tab.close()  # returns with the install still going

        assert is_kept(launcher)
        assert launcher._stopped.is_set()
        installing.set()
        deadline = time.monotonic() + 5
        while is_kept(launcher):
            assert time.monotonic() < deadline, "the launcher was never let go"
            app.processEvents()
            time.sleep(0.01)

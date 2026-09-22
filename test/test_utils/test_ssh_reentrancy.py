"""Connecting an SSH tab: off the UI thread, and never leaking the prior session."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading
import time

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_command_widget as shell_mod
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as tree_mod
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_host_key_policy as host_key_mod
from pybreeze.pybreeze_ui.thread_keeper import is_kept

WAIT_SECONDS = 5


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _wait_for(condition) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        QApplication.processEvents()
        time.sleep(0.01)


class FakeClient:
    """A paramiko client whose connect waits for *release*, then succeeds or raises *error*."""

    def __init__(self, release: threading.Event | None = None, error: Exception | None = None) -> None:
        self.release = release
        self.error = error
        self.closed = False
        self.connect_thread: QThread | None = None

    def connect(self, **_kwargs) -> None:
        self.connect_thread = QThread.currentThread()
        if self.release is not None:
            self.release.wait(WAIT_SECONDS)
        if self.error is not None:
            raise self.error

    def close(self) -> None:
        self.closed = True


def _shell(monkeypatch, client: FakeClient):
    widget = shell_mod.SSHCommandWidget()
    widget.login_widget.host_edit.setText("host")
    widget.login_widget.user_edit.setText("user")
    widget.login_widget.pass_edit.setText("pw")
    monkeypatch.setattr(shell_mod.paramiko, "SSHClient", lambda: client)
    monkeypatch.setattr(shell_mod, "apply_host_key_policy", lambda _client, _parent: None)
    return widget


class TestShellConnect:
    def test_cleanup_runs_before_the_new_session(self, app, monkeypatch):
        widget = _shell(monkeypatch, FakeClient())
        order = []
        widget._cleanup = lambda: order.append("cleanup")
        widget._start_shell = lambda *args: order.append("start_shell")

        widget.connect_ssh()
        _wait_for(lambda: "start_shell" in order)

        # The prior session is torn down before a new client/shell is created,
        # so re-connecting cannot leak the old client or orphan its reader.
        assert order == ["cleanup", "start_shell"]

    def test_the_connect_does_not_hold_the_ui_thread(self, app, monkeypatch):
        release = threading.Event()
        client = FakeClient(release)
        widget = _shell(monkeypatch, client)
        started = []
        widget._start_shell = lambda *args: started.append(QThread.currentThread())
        states = []
        widget.state_changed.connect(lambda: states.append("changed"))

        widget.connect_ssh()
        assert not started  # returned while the host is still answering
        release.set()
        _wait_for(lambda: started and states)

        assert client.connect_thread is not app.thread()
        assert started == [app.thread()]  # the shell is opened on the UI thread

    def test_a_second_click_while_connecting_is_ignored(self, app, monkeypatch):
        release = threading.Event()
        widget = _shell(monkeypatch, FakeClient(release))
        started = []
        widget._start_shell = lambda *args: started.append(True)

        widget.connect_ssh()
        first = widget._connecting
        widget.connect_ssh()
        release.set()
        _wait_for(lambda: started)

        assert widget._connecting is first
        assert started == [True]

    def test_a_failed_connect_is_reported_and_dropped(self, app, monkeypatch):
        client = FakeClient(error=OSError("unreachable"))
        widget = _shell(monkeypatch, client)
        states = []
        widget.state_changed.connect(lambda: states.append("changed"))

        widget.connect_ssh()
        _wait_for(lambda: states)

        assert "unreachable" in widget.terminal.toPlainText()
        assert client.closed
        assert widget.ssh_client is None

    def test_closing_while_connecting_closes_the_late_session(self, app, monkeypatch):
        release = threading.Event()
        client = FakeClient(release)
        widget = _shell(monkeypatch, client)
        widget._start_shell = lambda *args: pytest.fail("shell opened after close")

        widget.connect_ssh()
        thread = widget._connecting
        widget.close()
        assert is_kept(thread)
        client.closed = False  # _cleanup closed it once; the late connect must close it again
        release.set()
        _wait_for(lambda: client.closed and not is_kept(thread))


class FakeManager:
    """The SFTP wrapper, with a connect that waits for *release*."""

    def __init__(self, release: threading.Event, error: Exception | None = None) -> None:
        self.release = release
        self.error = error
        self.connect_thread: QThread | None = None
        self.closes = 0

    def connect(self, *_args, **_kwargs) -> None:
        self.connect_thread = QThread.currentThread()
        self.release.wait(WAIT_SECONDS)
        if self.error is not None:
            raise self.error

    def close(self) -> None:
        self.closes += 1

    @property
    def connected(self) -> bool:
        return False


def _tree(manager: FakeManager):
    widget = tree_mod.SSHFileTreeManager()
    widget.login_widget.host_edit.setText("host")
    widget.login_widget.user_edit.setText("user")
    widget.client = manager
    return widget


class TestFileTreeConnect:
    def test_the_root_is_listed_on_the_ui_thread_after_the_connect(self, app):
        release = threading.Event()
        manager = FakeManager(release)
        widget = _tree(manager)
        listed = []
        widget.load_root = lambda path: listed.append((path, QThread.currentThread()))

        widget._connect()
        assert not listed
        release.set()
        _wait_for(lambda: listed)

        assert manager.connect_thread is not app.thread()
        assert listed == [("/", app.thread())]
        widget.close()

    def test_a_failed_connect_is_reported(self, app, monkeypatch):
        release = threading.Event()
        release.set()
        widget = _tree(FakeManager(release, OSError("refused")))
        shown = []
        monkeypatch.setattr(tree_mod.QMessageBox, "critical", lambda *args: shown.append(args[2]))

        widget._connect()
        _wait_for(lambda: shown)

        assert "refused" in shown[0]
        widget.close()

    def test_closing_while_connecting_closes_the_late_session(self, app):
        release = threading.Event()
        manager = FakeManager(release)
        widget = _tree(manager)
        widget.load_root = lambda path: pytest.fail("listed after close")

        widget._connect()
        thread = widget._connecting
        widget.close()
        closes_at_close = manager.closes
        release.set()
        _wait_for(lambda: not is_kept(thread))

        assert manager.closes > closes_at_close


class TestHostKeyAsker:
    """The unknown-host question is shown on the UI thread whoever asks it."""

    def _asker(self, monkeypatch, answer):
        shown_on = []

        def exec_(_box):
            shown_on.append(QThread.currentThread())
            return answer

        monkeypatch.setattr(host_key_mod.QMessageBox, "exec", exec_)
        return host_key_mod.HostKeyAsker(), shown_on

    def test_asked_on_the_ui_thread_it_answers_directly(self, app, monkeypatch):
        asker, shown_on = self._asker(monkeypatch, host_key_mod.QMessageBox.StandardButton.Yes)

        assert asker.ask(None, "title", "message") is True
        assert shown_on == [app.thread()]

    def test_asked_from_a_connecting_thread_it_waits_for_the_ui(self, app, monkeypatch):
        asker, shown_on = self._asker(monkeypatch, host_key_mod.QMessageBox.StandardButton.No)
        answers = []
        worker = threading.Thread(target=lambda: answers.append(asker.ask(None, "title", "message")))

        worker.start()
        _wait_for(lambda: answers)
        worker.join(WAIT_SECONDS)

        assert answers == [False]
        assert shown_on == [app.thread()]

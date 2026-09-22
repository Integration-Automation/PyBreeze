"""Closing an SSH tab, and what the SFTP wrapper does when nothing is connected.

A closed tab must leave no reader thread running and no transport open: Qt aborts
the process when a running QThread is destroyed, and a queued signal from one
lands in a widget that is already gone.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_file_viewer_widget import SFTPClientWrapper


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class FakeReaderThread:
    def __init__(self) -> None:
        self.stopped = False
        self.waited = False
        self.signals_blocked = False

    def blockSignals(self, blocked: bool) -> None:
        self.signals_blocked = blocked

    def stop(self) -> None:
        self.stopped = True

    def wait(self, _timeout: int) -> bool:
        self.waited = True
        return True


class FakeChannel:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class TestClosingTheShell:
    def _connected_widget(self, app):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import SSHCommandWidget

        widget = SSHCommandWidget()
        widget.reader_thread = FakeReaderThread()
        widget.shell_channel = FakeChannel()
        widget.ssh_client = FakeClient()
        return widget

    def test_closing_the_widget_stops_the_reader_and_the_session(self, app):
        widget = self._connected_widget(app)
        reader, channel, client = widget.reader_thread, widget.shell_channel, widget.ssh_client

        widget.close()

        assert reader.stopped and reader.waited
        assert channel.closed
        assert client.closed
        assert widget.reader_thread is None

    def test_closing_a_widget_that_never_connected_is_harmless(self, app):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import SSHCommandWidget

        SSHCommandWidget().close()


class TestClosingTheFileTree:
    def test_closing_the_widget_closes_the_sftp_session(self, app):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_file_viewer_widget import SSHFileTreeManager

        widget = SSHFileTreeManager()
        widget.client = FakeClient()

        widget.close()

        assert widget.client.closed


class TestClosingTheTab:
    def test_both_halves_are_closed_with_it(self, app):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_main_widget import SSHMainWidget

        tab = SSHMainWidget()
        tab.command_widget.reader_thread = FakeReaderThread()
        tab.command_widget.ssh_client = FakeClient()
        tab.file_tree.client = FakeClient()
        reader = tab.command_widget.reader_thread

        tab.close()

        assert reader.stopped
        assert tab.command_widget.ssh_client is None
        assert tab.file_tree.client.closed


class TestTheSftpWrapperWithoutAConnection:
    @pytest.mark.parametrize("call", [
        lambda w: w.mkdir("/tmp/x"),
        lambda w: w.remove_file("/tmp/x"),
        lambda w: w.remove_dir("/tmp/x"),
        lambda w: w.rename("/tmp/x", "/tmp/y"),
        lambda w: w.download("/tmp/x", "x"),
        lambda w: w.upload("x", "/tmp/x"),
        lambda w: w.list_dir("/tmp"),
    ], ids=["mkdir", "remove_file", "remove_dir", "rename", "download", "upload", "list_dir"])
    def test_it_says_it_is_not_connected(self, app, call):
        # Not an AttributeError about NoneType, which the tree's blanket handler
        # would put in front of the user word for word.
        wrapper = SFTPClientWrapper()

        with pytest.raises(RuntimeError):
            call(wrapper)


class TestATransfer:
    """A transfer runs in the background: a big file must not hold the IDE."""

    def _tree(self, app):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_file_viewer_widget import SSHFileTreeManager

        return SSHFileTreeManager()

    def test_a_download_does_not_hold_the_caller(self, app, monkeypatch):
        import threading

        from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as viewer

        answering = threading.Event()
        started = threading.Event()
        shown: list = []
        monkeypatch.setattr(
            viewer.QMessageBox, "information",
            staticmethod(lambda *args: shown.append(args)))
        tree = self._tree(app)

        def slow_download(_remote, _local):
            started.set()
            answering.wait(10)

        tree.client.download = slow_download

        assert tree._start_transfer(
            downloading=True, remote_path="/tmp/big.bin", local_path="big.bin",
            title="Downloaded", message="Saved to") is True

        assert started.wait(5), "the transfer never started"
        assert tree._transfer.isRunning(), "the caller waited for the transfer"
        answering.set()
        tree._transfer.wait(5000)

    def test_a_second_transfer_is_refused_while_one_runs(self, app, monkeypatch):
        from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as viewer

        said: list = []
        monkeypatch.setattr(
            viewer.QMessageBox, "information", staticmethod(lambda *args: said.append(args)))
        tree = self._tree(app)

        class Running:
            @staticmethod
            def isRunning() -> bool:
                return True

        tree._transfer = Running()

        assert tree._start_transfer(
            downloading=True, remote_path="/tmp/x", local_path="x",
            title="Downloaded", message="Saved to") is False
        assert said, "the user was told nothing"

    def test_a_transfer_that_fails_is_reported(self, app, monkeypatch):
        from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as viewer

        problems: list = []
        monkeypatch.setattr(
            viewer.QMessageBox, "critical", staticmethod(lambda *args: problems.append(args)))
        tree = self._tree(app)
        tree.client.download = lambda *_args: (_ for _ in ()).throw(OSError("link went away"))
        thread = viewer.SftpTransferThread(tree.client, True, "/tmp/x", "x")
        thread.failed.connect(tree._transfer_failed)

        thread.run()

        assert problems and "link went away" in problems[0][2]

    def test_closing_waits_for_a_transfer(self, app):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_file_viewer_widget import SSHFileTreeManager

        class Waited:
            def __init__(self) -> None:
                self.waited = False
                self.blocked = False

            def isRunning(self) -> bool:
                return True

            def blockSignals(self, blocked: bool) -> None:
                self.blocked = blocked

            def wait(self) -> None:
                self.waited = True

        tree = SSHFileTreeManager()
        tree.client = FakeClient()
        tree._transfer = Waited()

        tree.close()

        assert tree._transfer.waited and tree._transfer.blocked
        assert tree.client.closed


class TestWhatTheStatusLabelSays:
    """One Connect button opens two sessions; the label has to report both."""

    def _tab(self, shell_up: bool, files_up: bool):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_main_widget import SSHMainWidget

        tab = SSHMainWidget()
        tab.command_widget.is_connected = lambda: shell_up

        class Client:
            connected = files_up

            @staticmethod
            def close() -> None:
                """Nothing to close in a stand-in."""

        tab.file_tree.client = Client()
        return tab

    @pytest.mark.parametrize("shell_up,files_up,expected", [
        (True, True, "shell and files"),
        (True, False, "shell only"),
        (False, True, "files only"),
        (False, False, "Disconnected"),
    ], ids=["both", "shell only", "files only", "neither"])
    def test_it_reports_both_halves(self, app, shell_up, files_up, expected):
        tab = self._tab(shell_up, files_up)

        tab.report_connection_state()

        assert expected in tab.login_widget.status_label.text()

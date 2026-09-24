"""A transfer can be cancelled: what had arrived goes, and a file it was to replace stays."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import errno
import time
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import sftp_session
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as tree_mod

WAIT_SECONDS = 10


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class ChunkedSftp:
    """Moves a file in blocks, reporting each as paramiko does, until told the whole is there."""

    def __init__(self, files: dict[str, bytes] | None = None, blocks: int = 1000) -> None:
        self.files = dict(files or {})
        self.blocks = blocks

    def stat(self, path: str):
        if path not in self.files:
            raise OSError(errno.ENOENT, "No such file")
        return object()

    def get(self, remote: str, local: str, callback=None) -> None:
        with open(local, "wb") as target:
            for block in range(self.blocks):
                target.write(b"x")
                if callback is not None:
                    callback(block + 1, self.blocks)
                time.sleep(0.001)

    def put(self, _local: str, remote: str, callback=None) -> None:
        self.files[remote] = b""
        for block in range(self.blocks):
            self.files[remote] += b"x"
            if callback is not None:
                callback(block + 1, self.blocks)
            time.sleep(0.001)

    def posix_rename(self, old: str, new: str) -> None:
        self.files[new] = self.files.pop(old)

    def remove(self, path: str) -> None:
        if path not in self.files:
            raise OSError(errno.ENOENT, "No such file")
        del self.files[path]

    def close(self) -> None:
        """Nothing to close."""


def _wrapper(sftp: ChunkedSftp) -> sftp_session.SFTPClientWrapper:
    wrapper = sftp_session.SFTPClientWrapper()
    wrapper._ssh = SimpleNamespace(close=lambda: None)
    wrapper._sftp = sftp
    return wrapper


def _cancel_once_under_way(app, thread) -> list[str]:
    """Start *thread*, cancel it after its first blocks, and return which signals it sent."""
    sent: list[str] = []
    thread.done.connect(lambda _path: sent.append("done"))
    thread.failed.connect(lambda _message: sent.append("failed"))
    thread.cancelled.connect(lambda: sent.append("cancelled"))
    thread.start()
    time.sleep(0.05)
    thread.cancel()
    assert thread.wait(WAIT_SECONDS * 1000), "the transfer did not stop"
    app.processEvents()
    return sent


class TestCancellingADownload:
    def test_removes_what_arrived_and_keeps_the_old_file(self, app, tmp_path):
        target = tmp_path / "report.csv"
        target.write_bytes(b"old report")
        thread = sftp_session.SftpTransferThread(
            _wrapper(ChunkedSftp()), True, "/srv/report.csv", str(target))

        sent = _cancel_once_under_way(app, thread)

        assert sent == ["cancelled"]
        assert target.read_bytes() == b"old report"
        assert [path.name for path in tmp_path.iterdir()] == ["report.csv"]


class TestCancellingAnUpload:
    def test_removes_what_arrived_and_keeps_the_servers_copy(self, app, tmp_path):
        local = tmp_path / "config.yaml"
        local.write_bytes(b"new config")
        sftp = ChunkedSftp({"/etc/app/config.yaml": b"old config"})
        thread = sftp_session.SftpTransferThread(
            _wrapper(sftp), False, "/etc/app/config.yaml", str(local), replace=True)

        sent = _cancel_once_under_way(app, thread)

        assert sent == ["cancelled"]
        assert sftp.files == {"/etc/app/config.yaml": b"old config"}


class TestTheMenu:
    def _menu_entries(self, widget, monkeypatch, choose_last: bool = False) -> list[str]:
        shown: list[str] = []

        class AnsweringMenu(tree_mod.QMenu):
            def exec(self, _pos):
                actions = [action for action in self.actions() if not action.isSeparator()]
                shown.extend(action.text() for action in actions)
                return actions[-1] if choose_last else None

        monkeypatch.setattr(tree_mod, "QMenu", AnsweringMenu)
        monkeypatch.setattr(widget.tree, "itemAt", lambda _pos: None)
        widget.on_context_menu(widget.tree.rect().center())
        return shown

    def test_offers_a_cancel_only_while_a_transfer_runs(self, app, monkeypatch, tmp_path):
        word = tree_mod.language_wrapper.language_word_dict
        cancel_label = word.get("ssh_file_viewer_context_menu_action_cancel_transfer")
        shown_messages: list = []
        monkeypatch.setattr(QMessageBox, "information", lambda *args: shown_messages.append(args[1:3]))
        widget = tree_mod.SSHFileTreeManager()
        widget.client = _wrapper(ChunkedSftp(blocks=5000))
        assert cancel_label not in self._menu_entries(widget, monkeypatch)

        assert widget._start_transfer(
            downloading=True, remote_path="/big.iso", local_path=str(tmp_path / "big.iso"),
            title="Downloaded", message="Saved to")
        assert self._menu_entries(widget, monkeypatch, choose_last=True)[-1] == cancel_label

        deadline = time.monotonic() + WAIT_SECONDS
        while widget._transfer is not None:
            assert time.monotonic() < deadline, "the transfer did not stop"
            app.processEvents()
            time.sleep(0.01)
        assert shown_messages == [(word.get("ssh_file_viewer_dialog_title_transfer_cancelled"),
                                   word.get("ssh_file_viewer_message_transfer_cancelled"))]
        assert not (tmp_path / "big.iso").exists()
        widget.close()
        widget.deleteLater()

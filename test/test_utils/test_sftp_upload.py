"""An upload asks before replacing a file, and never leaves the server's copy cut short."""
from __future__ import annotations

import errno
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import sftp_session
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as viewer

WAIT_SECONDS = 5


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class FakeSftp:
    """A server's files in a dict; ``put`` can fail halfway, ``posix_rename`` can be missing."""

    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files = dict(files or {})
        self.fail_put = False
        self.has_posix_rename = True
        self.put_to: list[str] = []

    def stat(self, path: str):
        if path not in self.files:
            raise OSError(errno.ENOENT, "No such file")
        return object()

    def put(self, local: str, remote: str) -> None:
        self.put_to.append(remote)
        with open(local, "rb") as source:
            data = source.read()
        if self.fail_put:
            self.files[remote] = data[:2]
            raise OSError("the link went away")
        self.files[remote] = data

    def posix_rename(self, old: str, new: str) -> None:
        if not self.has_posix_rename:
            raise OSError("Operation unsupported")
        self.files[new] = self.files.pop(old)

    def rename(self, old: str, new: str) -> None:
        if new in self.files:
            raise OSError("Failure")
        self.files[new] = self.files.pop(old)

    def close(self) -> None:
        """Nothing to close."""

    def remove(self, path: str) -> None:
        if path not in self.files:
            raise OSError(errno.ENOENT, "No such file")
        del self.files[path]


def _wrapper(sftp: FakeSftp) -> sftp_session.SFTPClientWrapper:
    wrapper = sftp_session.SFTPClientWrapper()
    wrapper._ssh = SimpleNamespace(close=lambda: None)
    wrapper._sftp = sftp
    return wrapper


@pytest.fixture()
def local_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_bytes(b"new config")
    return str(path)


class TestTheWrapper:
    def test_a_new_file_arrives_whole_under_its_name(self, app, local_file):
        sftp = FakeSftp()

        assert _wrapper(sftp).upload(local_file, "/etc/app/config.yaml") is True

        assert sftp.files == {"/etc/app/config.yaml": b"new config"}
        # It went through a temporary name beside the target
        assert sftp.put_to[0].startswith("/etc/app/.config.yaml.")

    def test_an_existing_file_is_not_touched_unless_replacing(self, app, local_file):
        # It used to be replaced without a word
        sftp = FakeSftp({"/etc/app/config.yaml": b"old config"})

        assert _wrapper(sftp).upload(local_file, "/etc/app/config.yaml") is False

        assert sftp.files == {"/etc/app/config.yaml": b"old config"}
        assert sftp.put_to == []

    def test_replacing_puts_the_new_file_in_its_place(self, app, local_file):
        sftp = FakeSftp({"/etc/app/config.yaml": b"old config"})

        assert _wrapper(sftp).upload(local_file, "/etc/app/config.yaml", replace=True) is True

        assert sftp.files == {"/etc/app/config.yaml": b"new config"}

    def test_a_broken_upload_leaves_the_old_file_whole_and_no_leftover(self, app, local_file):
        # put() empties its target first: a dropped link left it cut short
        sftp = FakeSftp({"/etc/app/config.yaml": b"old config"})
        sftp.fail_put = True

        with pytest.raises(OSError):
            _wrapper(sftp).upload(local_file, "/etc/app/config.yaml", replace=True)

        assert sftp.files == {"/etc/app/config.yaml": b"old config"}

    def test_a_server_without_posix_rename_still_gets_the_file(self, app, local_file):
        sftp = FakeSftp({"/config.yaml": b"old config"})
        sftp.has_posix_rename = False

        assert _wrapper(sftp).upload(local_file, "/config.yaml", replace=True) is True

        assert sftp.files == {"/config.yaml": b"new config"}


class TestTheTree:
    def _upload(self, app, monkeypatch, sftp: FakeSftp, local_file: str, answer) -> list:
        widget = viewer.SSHFileTreeManager()
        widget.client = _wrapper(sftp)
        asked: list = []

        def question(*args, **_kwargs):
            asked.append(args[2])
            return answer

        monkeypatch.setattr(QMessageBox, "question", question)
        monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
        widget._start_transfer(downloading=False, remote_path="/config.yaml", local_path=local_file,
                               title="Uploaded", message="Uploaded to")
        deadline = time.monotonic() + WAIT_SECONDS

        def transferring() -> bool:
            # A finished transfer is let go of (it is then None)
            return widget._transfer is not None and widget._transfer.isRunning()

        while transferring() or (asked and answer == QMessageBox.StandardButton.Yes
                                 and sftp.files.get("/config.yaml") != b"new config"):
            assert time.monotonic() < deadline, "timed out"
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()
        if widget._transfer is not None:
            widget._transfer.wait(1000)
        widget.close()
        return asked

    def test_the_user_is_asked_and_a_no_keeps_the_file(self, app, monkeypatch, local_file):
        sftp = FakeSftp({"/config.yaml": b"old config"})

        asked = self._upload(app, monkeypatch, sftp, local_file, QMessageBox.StandardButton.No)

        assert len(asked) == 1 and "/config.yaml" in asked[0]
        assert sftp.files == {"/config.yaml": b"old config"}

    def test_a_yes_replaces_it(self, app, monkeypatch, local_file):
        sftp = FakeSftp({"/config.yaml": b"old config"})

        asked = self._upload(app, monkeypatch, sftp, local_file, QMessageBox.StandardButton.Yes)

        assert len(asked) == 1
        assert sftp.files == {"/config.yaml": b"new config"}

    def test_a_new_file_is_not_asked_about(self, app, monkeypatch, local_file):
        sftp = FakeSftp()

        asked = self._upload(app, monkeypatch, sftp, local_file, QMessageBox.StandardButton.No)

        assert asked == []
        assert sftp.files == {"/config.yaml": b"new config"}

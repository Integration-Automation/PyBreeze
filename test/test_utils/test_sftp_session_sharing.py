"""One SFTP session, several users: one request at a time, and no file left cut short."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import sftp_session as viewer

WAIT_SECONDS = 5


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class FakeSftp:
    """Records overlapping requests; ``get`` writes *content* and can be held or made to fail."""

    def __init__(self) -> None:
        self.active = 0
        self.overlapped = False
        self.hold = threading.Event()
        self.hold.set()
        self.inside = threading.Event()
        self.fail_after: bytes | None = None
        self.content = b"new contents"
        self._count = threading.Lock()

    def _request(self) -> None:
        with self._count:
            self.active += 1
            self.overlapped = self.overlapped or self.active > 1
        self.inside.set()
        self.hold.wait(WAIT_SECONDS)
        with self._count:
            self.active -= 1

    def listdir_attr(self, _path):
        self._request()
        return []

    def mkdir(self, _path) -> None:
        self._request()

    def get(self, _remote, local, callback=None) -> None:
        with open(local, "wb") as target:
            if self.fail_after is not None:
                target.write(self.fail_after)
                raise OSError("the link went away")
            self._request()
            target.write(self.content)


def _wrapper(sftp: FakeSftp) -> viewer.SFTPClientWrapper:
    wrapper = viewer.SFTPClientWrapper()
    wrapper._ssh = object()
    wrapper._sftp = sftp
    return wrapper


class TestOneRequestAtATime:
    def test_two_listings_take_turns(self, app):
        sftp = FakeSftp()
        sftp.hold.clear()
        wrapper = _wrapper(sftp)
        workers = [threading.Thread(target=wrapper.list_dir, args=(path,)) for path in ("/home", "/var")]
        for worker in workers:
            worker.start()
        sftp.inside.wait(WAIT_SECONDS)
        sftp.hold.set()
        for worker in workers:
            worker.join(WAIT_SECONDS)

        # Each expand used to run its own listing on the session at once; one
        # thread could read the other's reply and leave it waiting forever.
        assert not sftp.overlapped

    def test_a_menu_action_during_a_transfer_is_refused_not_frozen(self, app, tmp_path):
        sftp = FakeSftp()
        sftp.hold.clear()
        wrapper = _wrapper(sftp)
        download = threading.Thread(
            target=wrapper.download, args=("/big.bin", str(tmp_path / "big.bin")))
        download.start()
        sftp.inside.wait(WAIT_SECONDS)

        with pytest.raises(viewer.SftpBusy):
            wrapper.mkdir("/new")

        sftp.hold.set()
        download.join(WAIT_SECONDS)
        assert not sftp.overlapped

    def test_a_menu_action_on_a_free_session_goes_through(self, app):
        sftp = FakeSftp()

        _wrapper(sftp).mkdir("/new")

        assert sftp.active == 0


class TestADownload:
    def test_it_replaces_the_file_only_when_complete(self, app, tmp_path):
        target = tmp_path / "report.txt"
        target.write_bytes(b"the old report")
        sftp = FakeSftp()

        _wrapper(sftp).download("/report.txt", str(target))

        assert target.read_bytes() == b"new contents"
        assert list(tmp_path.iterdir()) == [target]

    def test_one_that_fails_leaves_the_old_file_whole(self, app, tmp_path):
        target = tmp_path / "report.txt"
        target.write_bytes(b"the old report")
        sftp = FakeSftp()
        sftp.fail_after = b"half"

        with pytest.raises(OSError):
            _wrapper(sftp).download("/report.txt", str(target))

        # get() emptied the target before the first byte; a dropped link left
        # it cut short.
        assert target.read_bytes() == b"the old report"
        assert list(tmp_path.iterdir()) == [target]  # no partial file left behind

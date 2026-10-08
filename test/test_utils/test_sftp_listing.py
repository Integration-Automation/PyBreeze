"""Listing a remote directory runs off the UI thread and lands only where it is still wanted."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import stat
import threading
import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as tree_mod
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


def _entry(name: str, directory: bool = False):
    mode = stat.S_IFDIR if directory else stat.S_IFREG
    return SimpleNamespace(filename=name, st_mode=mode, st_size=10)


class FakeClient:
    """An open session whose listings wait for their path's gate to open."""

    connected = True

    def __init__(self, listings: dict[str, list]) -> None:
        self.listings = listings
        self.gates: dict[str, threading.Event] = {}
        self.listed_on: list[QThread] = []

    def gate(self, path: str) -> threading.Event:
        return self.gates.setdefault(path, threading.Event())

    def list_dir(self, path: str):
        self.listed_on.append(QThread.currentThread())
        self.gate(path).wait(WAIT_SECONDS)
        result = self.listings[path]
        if isinstance(result, Exception):
            raise result
        return result

    def close(self) -> None:
        """Nothing to close."""


def _tree(client: FakeClient):
    widget = tree_mod.SSHFileTreeManager()
    widget.client = client
    return widget


def _names(item) -> list[str]:
    return [item.child(i).text(0) for i in range(item.childCount())]


def _idle(widget) -> bool:
    return not widget._listings


class TestListing:
    def test_the_root_fills_from_a_thread(self, app):
        client = FakeClient({"/": [_entry("b.txt"), _entry("etc", directory=True), _entry("a.txt")]})
        widget = _tree(client)

        widget.load_root("/")
        root = widget.tree.topLevelItem(0)
        assert _names(root) == [widget.word_dict.get("ssh_file_viewer_loading")]
        client.gate("/").set()
        _wait_for(lambda: _idle(widget) and _names(root) == ["etc", "a.txt", "b.txt"])

        assert client.listed_on
        assert client.listed_on[0] is not app.thread()
        widget.close()

    def test_a_listing_that_returns_after_the_tree_is_cleared_is_dropped(self, app):
        client = FakeClient({"/": [_entry("old.txt")]})
        widget = _tree(client)

        widget.load_root("/")
        widget._disconnect()
        client.gate("/").set()
        _wait_for(lambda: _idle(widget))

        assert widget.tree.topLevelItemCount() == 0
        widget.close()

    def test_a_refresh_supersedes_the_listing_before_it(self, app):
        client = FakeClient({"/": [_entry("stale.txt")]})
        widget = _tree(client)
        widget.load_root("/")
        root = widget.tree.topLevelItem(0)
        first_gate = client.gate("/")

        client.gates["/"] = threading.Event()  # the refresh waits on a gate of its own
        client.listings["/"] = [_entry("fresh.txt")]
        widget.action_refresh(root)
        client.gates["/"].set()
        _wait_for(lambda: _names(root) == ["fresh.txt"])
        first_gate.set()
        _wait_for(lambda: _idle(widget))

        assert _names(root) == ["fresh.txt"]
        widget.close()

    def test_a_failed_listing_is_reported(self, app, monkeypatch):
        client = FakeClient({"/": OSError("permission denied")})
        client.gate("/").set()
        widget = _tree(client)
        shown = []
        monkeypatch.setattr(tree_mod.QMessageBox, "critical", lambda *args: shown.append(args[2]))

        widget.load_root("/")
        _wait_for(lambda: shown and _idle(widget))

        assert "permission denied" in shown[0]
        assert _names(widget.tree.topLevelItem(0)) == []
        widget.close()

    def test_closing_mid_listing_lets_it_run_out(self, app):
        client = FakeClient({"/": [_entry("a.txt")]})
        widget = _tree(client)

        widget.load_root("/")
        (listing,) = widget._listings
        widget.close()
        assert is_kept(listing)
        client.gate("/").set()
        _wait_for(lambda: not is_kept(listing))


class TestLinks:
    """A listing describes a link itself: a link to a folder (``/bin`` on most Linux systems) showed as a file."""

    class _Server:
        def __init__(self) -> None:
            link = stat.S_IFLNK | 0o777
            self.listing = [
                SimpleNamespace(filename="bin", st_mode=link, st_size=7),
                SimpleNamespace(filename="latest.log", st_mode=link, st_size=9),
                SimpleNamespace(filename="gone", st_mode=link, st_size=4),
                SimpleNamespace(filename="etc", st_mode=stat.S_IFDIR | 0o755, st_size=4096),
            ]
            self.targets = {
                "/bin": SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_size=4096),
                "/latest.log": SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_size=1234),
            }
            self.stats: list[str] = []

        def listdir_attr(self, _path: str):
            return self.listing

        def stat(self, path: str):
            self.stats.append(path)
            if path not in self.targets:
                raise FileNotFoundError(path)
            return self.targets[path]

    def _listed(self, server) -> dict:
        from pybreeze.pybreeze_ui.connect_gui.ssh.sftp_session import SFTPClientWrapper

        wrapper = SFTPClientWrapper()
        wrapper._ssh = SimpleNamespace(close=lambda: None)
        wrapper._sftp = server
        return {entry.filename: entry for entry in wrapper.list_dir("/")}

    def test_a_link_to_a_folder_is_a_folder(self, app):
        entries = self._listed(self._Server())

        assert stat.S_ISDIR(entries["bin"].st_mode)

    def test_a_link_to_a_file_has_the_files_size(self, app):
        entries = self._listed(self._Server())

        assert stat.S_ISREG(entries["latest.log"].st_mode)
        assert entries["latest.log"].st_size == 1234

    def test_a_link_leading_nowhere_stays_a_link(self, app):
        entries = self._listed(self._Server())

        assert stat.S_ISLNK(entries["gone"].st_mode)

    def test_only_links_are_looked_up(self, app):
        server = self._Server()

        self._listed(server)

        assert sorted(server.stats) == ["/bin", "/gone", "/latest.log"]

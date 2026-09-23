"""Create, rename and upload in the SFTP tree: names are one entry, and the tree follows."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import stat
import time
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as tree_mod
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_file_viewer_widget import folder_item, plain_remote_name

WAIT_SECONDS = 5


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _entry(name: str, directory: bool = False):
    mode = stat.S_IFDIR if directory else stat.S_IFREG
    return SimpleNamespace(filename=name, st_mode=mode, st_size=10)


class FakeClient:
    """A session over an in-memory listing that records what was asked of it."""

    connected = True

    def __init__(self, listings: dict[str, list]) -> None:
        self.listings = listings
        self.made: list[str] = []
        self.renamed: list[tuple[str, str]] = []

    def list_dir(self, path: str):
        return list(self.listings.get(path, []))

    def mkdir(self, path: str) -> None:
        self.made.append(path)

    def rename(self, old: str, new: str) -> None:
        self.renamed.append((old, new))
        self.listings[new] = self.listings.pop(old, [])

    def close(self) -> None:
        """Nothing to close."""


@pytest.fixture()
def tree(app, monkeypatch):
    client = FakeClient({
        "/": [_entry("src", directory=True), _entry("notes.txt")],
        "/src": [_entry("main.py")],
    })
    widget = tree_mod.SSHFileTreeManager()
    widget.client = client
    root = widget.make_item("/", "dir", 0, "/")
    widget.tree.addTopLevelItem(root)
    widget.add_placeholder(root)
    widget.on_item_expanded(root)
    _wait_for(lambda: not widget._listings)
    warnings: list = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    yield widget, client, root, warnings
    widget.close()
    widget.deleteLater()


def _wait_for(condition) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        QApplication.processEvents()
        time.sleep(0.01)


def _child(item, name: str):
    return next(item.child(i) for i in range(item.childCount()) if item.child(i).text(0) == name)


def _answer(widget, monkeypatch, text: str) -> None:
    monkeypatch.setattr(widget, "get_text", lambda *_args: (text, True))


class TestANameIsOneEntry:
    @pytest.mark.parametrize("text", ["../x", "/tmp/x", "a/b", ".", "..", "  ", "a\x00b"])
    def test_a_path_is_not_a_name(self, text):
        assert plain_remote_name(text) is None

    def test_a_name_is_kept_stripped(self):
        assert plain_remote_name("  new folder ") == "new folder"

    def test_a_folder_named_with_a_path_is_refused(self, tree, monkeypatch):
        # "/tmp/x" made posixpath.join drop the folder it was created in
        widget, client, root, warnings = tree
        _answer(widget, monkeypatch, "/tmp/x")

        widget.action_create_folder(root)

        assert client.made == []
        assert warnings

    def test_a_rename_to_the_parent_is_refused(self, tree, monkeypatch):
        widget, client, root, warnings = tree
        _answer(widget, monkeypatch, "../x")

        widget.action_rename(_child(root, "notes.txt"))

        assert client.renamed == []
        assert warnings


class TestTheTreeFollows:
    def test_a_renamed_folders_children_carry_the_new_path(self, tree, monkeypatch):
        # They kept "/src/main.py", and a download or delete went there
        widget, client, root, _warnings = tree
        folder = _child(root, "src")
        widget.on_item_expanded(folder)
        _wait_for(lambda: not widget._listings)
        assert _child(folder, "main.py").text(3) == "/src/main.py"
        _answer(widget, monkeypatch, "lib")

        widget.action_rename(folder)
        _wait_for(lambda: not widget._listings)

        assert folder.text(3) == "/lib"
        assert _child(folder, "main.py").text(3) == "/lib/main.py"

    def test_a_folder_made_from_a_file_shows_in_that_files_folder(self, tree, monkeypatch):
        # The refresh went to the file item, which has nothing to refresh
        widget, client, root, _warnings = tree
        _answer(widget, monkeypatch, "made")

        def made(path: str) -> None:
            client.made.append(path)
            client.listings["/"].append(_entry("made", directory=True))

        client.mkdir = made
        widget.action_create_folder(_child(root, "notes.txt"))
        _wait_for(lambda: not widget._listings)

        assert client.made == ["/made"]
        assert _child(root, "made").text(3) == "/made"

    def test_a_file_items_folder_is_its_parent(self, tree):
        widget, _client, root, _warnings = tree

        assert folder_item(_child(root, "notes.txt")) is root
        assert folder_item(root) is root
        assert folder_item(None) is None

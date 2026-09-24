"""Create, rename and upload in the SFTP tree: names are one entry, and the tree follows."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import stat
import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QThread
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
        self.removed: list[str] = []
        self.threads: list = []

    def list_dir(self, path: str):
        return list(self.listings.get(path, []))

    def mkdir(self, path: str) -> None:
        self.threads.append(QThread.currentThread())
        self.made.append(path)

    def remove_file(self, path: str) -> None:
        self.threads.append(QThread.currentThread())
        self.removed.append(path)

    remove_dir = remove_file

    def rename(self, old: str, new: str) -> None:
        self.threads.append(QThread.currentThread())
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
    _wait_for(lambda: _idle(widget))
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


def _idle(widget) -> bool:
    return not widget._listings and not widget._calls


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
        _wait_for(lambda: _idle(widget))
        assert _child(folder, "main.py").text(3) == "/src/main.py"
        _answer(widget, monkeypatch, "lib")

        widget.action_rename(folder)
        _wait_for(lambda: _idle(widget))

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
        _wait_for(lambda: _idle(widget))

        assert client.made == ["/made"]
        assert _child(root, "made").text(3) == "/made"

    def test_a_file_items_folder_is_its_parent(self, tree):
        widget, _client, root, _warnings = tree

        assert folder_item(_child(root, "notes.txt")) is root
        assert folder_item(root) is root
        assert folder_item(None) is None


class TestTheMenuDoesNotWaitOnTheServer:
    """Create, rename and delete run off the UI thread: an SFTP reply has no timeout."""

    def test_each_request_runs_on_a_worker(self, app, tree, monkeypatch):
        widget, client, root, _warnings = tree
        _answer(widget, monkeypatch, "new")
        monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)

        widget.action_create_folder(root)
        _wait_for(lambda: _idle(widget))
        _answer(widget, monkeypatch, "renamed.txt")
        widget.action_rename(_child(root, "notes.txt"))
        _wait_for(lambda: _idle(widget))
        widget.action_delete(_child(root, "renamed.txt"))
        _wait_for(lambda: _idle(widget))

        assert client.made == ["/new"]
        assert client.renamed == [("/notes.txt", "/renamed.txt")]
        assert client.removed == ["/renamed.txt"]
        assert len(client.threads) == 3
        assert all(thread is not app.thread() for thread in client.threads)
        assert "renamed.txt" not in [root.child(i).text(0) for i in range(root.childCount())]

    def test_a_failed_request_is_shown_and_changes_nothing(self, app, tree, monkeypatch):
        widget, client, root, _warnings = tree
        shown: list = []
        monkeypatch.setattr(QMessageBox, "critical", lambda *args: shown.append(args[2]))
        monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)

        def refuse(_path: str) -> None:
            raise OSError("Permission denied")

        client.remove_file = refuse
        widget.action_delete(_child(root, "notes.txt"))
        _wait_for(lambda: _idle(widget))

        assert any("Permission denied" in text for text in shown)
        assert _child(root, "notes.txt").text(3) == "/notes.txt"


class TestTheNameADownloadSuggests:
    """A server's name may hold backslashes, and one climbing into Startup was offered as the save name."""

    @pytest.mark.parametrize(("remote", "suggested"), [
        ("/home/u/..\\..\\AppData\\Startup\\u.bat", "u.bat"),
        ("/srv/a:b?.txt", "a_b_.txt"),
        ("/data/report.csv", "report.csv"),
        ("/x/..", "download"),
        ("/x/ . ", "download"),
    ])
    def test_only_the_last_safe_part(self, remote, suggested):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_file_viewer_widget import local_file_name

        assert local_file_name(remote) == suggested



class TestAnEntryNamedDots:
    """The row a folder shows until expanded read "...", and was told apart by that text alone."""

    def test_is_not_taken_for_the_placeholder(self, tree):
        widget, client, root, _warnings = tree
        client.listings["/"].append(_entry("odd", directory=True))
        client.listings["/odd"] = [_entry("...", directory=True), _entry("b.txt")]
        widget.action_refresh(root)
        _wait_for(lambda: _idle(widget))
        folder = _child(root, "odd")
        widget.on_item_expanded(folder)
        _wait_for(lambda: _idle(widget))

        assert not widget.is_placeholder_present(folder)
        widget.on_item_expanded(folder)  # collapsed and expanded again
        _wait_for(lambda: _idle(widget))

        assert [folder.child(i).text(0) for i in range(folder.childCount())] == ["...", "b.txt"]
        assert _child(folder, "...").text(3) == "/odd/..."

    def test_a_folder_not_yet_expanded_still_has_its_placeholder(self, tree):
        _widget, _client, root, _warnings = tree
        folder = _child(root, "src")

        assert tree[0].is_placeholder_present(folder)


class TestTheMenu:
    def _open(self, widget, monkeypatch, item, choose: int | None = None) -> list[str]:
        shown: list[str] = []

        def run(menu, _pos):
            shown.extend(action.text() for action in menu.actions())
            return None if choose is None else menu.actions()[choose]

        monkeypatch.setattr(tree_mod.QMenu, "exec_", run)
        monkeypatch.setattr(widget.tree, "itemAt", lambda _pos: item)
        widget.on_context_menu(widget.tree.rect().center())
        return shown

    def test_speaks_the_ide_language(self, app, monkeypatch):
        # The menu and the column headers were English whatever the IDE spoke
        from pybreeze.extend_multi_language.extend_traditional_chinese import (
            pybreeze_traditional_chinese_word_dict as word,
        )
        monkeypatch.setattr(tree_mod.language_wrapper, "language_word_dict", word)
        widget = tree_mod.SSHFileTreeManager()
        try:
            shown = self._open(widget, monkeypatch, None)
            headers = widget.tree.headerItem()

            assert shown == ["重新整理", "建立資料夾", "重新命名", "刪除", "下載", "上傳至此資料夾"]
            assert [headers.text(i) for i in range(4)] == ["名稱", "類型", "大小", "路徑"]
            # The Type column read "dir" / "file"
            folder, file = widget.make_item("a", "dir", 0, "/a"), widget.make_item("b", "file", 5, "/b")
            assert (folder.text(1), file.text(1)) == ("資料夾", "檔案")
            assert tree_mod.is_folder(folder) and tree_mod.is_file(file)
        finally:
            widget.close()
            widget.deleteLater()

    def test_on_the_placeholder_acts_on_its_folder(self, tree, monkeypatch):
        # It has no path: Delete asked about '' and Rename sent ("", "/name")
        widget, _client, root, _warnings = tree
        folder = _child(root, "src")
        refreshed: list = []
        monkeypatch.setattr(widget, "action_refresh", refreshed.append)

        self._open(widget, monkeypatch, folder.child(0), choose=0)

        assert refreshed == [folder]

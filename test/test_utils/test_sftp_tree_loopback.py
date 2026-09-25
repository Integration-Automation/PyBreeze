"""The SFTP file tree against an SFTP server on the loopback address that serves a real folder.

The other file tree tests stand in for the session. Here the tree logs in
through its own Connect and every action goes to the server and ends on disk:
listing, a new folder, a rename, a delete, a download and an upload.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from test_utils.ssh_loopback_server import (
    PASSWORD, USER, LoopbackServer, accept_every_host_key, wait_until,
)

_HELLO = "hello 中文\n".encode("utf-8")


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def remote(tmp_path):
    """The folder the server serves as ``/``: ``docs/readme.txt`` and ``hello.txt``."""
    folder = tmp_path / "remote"
    (folder / "docs").mkdir(parents=True)
    (folder / "docs" / "readme.txt").write_text("read me", encoding="utf-8")
    (folder / "hello.txt").write_bytes(_HELLO)
    return folder


@pytest.fixture
def shown(monkeypatch):
    """Message boxes answered without showing: questions get ``shown["answer"]``; all are recorded."""
    state = {"answer": QMessageBox.StandardButton.Yes, "messages": [], "questions": []}

    def record(kind):
        return staticmethod(lambda _parent, title, text, *_args: state["messages"].append((kind, title, text)))

    for kind in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, kind, record(kind))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda _parent, _title, text, *_args: state["questions"].append(text) or state["answer"]))
    return state


@pytest.fixture
def tree(app, tmp_path, monkeypatch, remote, shown):
    """The SFTP tree connected to the loopback server, its root listed."""
    from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_file_viewer_widget import SSHFileTreeManager

    accept_every_host_key(monkeypatch, tmp_path)
    server = LoopbackServer(sftp_root=remote)
    widget = SSHFileTreeManager()
    widget.login_widget.host_edit.setText("127.0.0.1")
    widget.login_widget.port_spin.setValue(server.port)
    widget.login_widget.user_edit.setText(USER)
    widget.login_widget.pass_edit.setText(PASSWORD)
    widget._connect()
    wait_until(app, lambda: widget.tree.topLevelItemCount() and _names(_root(widget)) == ["docs", "hello.txt"])
    yield widget
    widget.close()
    widget.deleteLater()
    server.stop()


def _root(widget):
    return widget.tree.topLevelItem(0)


def _names(item) -> list[str]:
    return [item.child(index).text(0) for index in range(item.childCount())]


def _child(item, name: str):
    return next(item.child(index) for index in range(item.childCount()) if item.child(index).text(0) == name)


def test_the_root_is_listed_folders_first(tree):
    docs = _child(_root(tree), "docs")

    assert _names(_root(tree)) == ["docs", "hello.txt"]
    assert tree.is_placeholder_present(docs)  # listed when first expanded
    assert _child(_root(tree), "hello.txt").text(3) == "/hello.txt"


def test_expanding_a_folder_lists_it(app, tree):
    docs = _child(_root(tree), "docs")

    docs.setExpanded(True)

    wait_until(app, lambda: _names(docs) == ["readme.txt"])
    assert docs.child(0).text(3) == "/docs/readme.txt"


def test_a_new_folder_is_made_on_the_server(app, tree, remote):
    tree.get_text = lambda *_args: ("made here", True)

    tree.action_create_folder(_root(tree))

    wait_until(app, lambda: "made here" in _names(_root(tree)))
    assert (remote / "made here").is_dir()


def test_a_rename_is_made_on_the_server(app, tree, remote):
    hello = _child(_root(tree), "hello.txt")
    tree.get_text = lambda *_args: ("renamed.txt", True)

    tree.action_rename(hello)

    wait_until(app, lambda: hello.text(0) == "renamed.txt")
    assert hello.text(3) == "/renamed.txt"
    assert (remote / "renamed.txt").read_bytes() == _HELLO
    assert not (remote / "hello.txt").exists()


def test_a_deleted_file_is_gone_from_the_server_and_the_tree(app, tree, remote, shown):
    tree.action_delete(_child(_root(tree), "hello.txt"))

    wait_until(app, lambda: _names(_root(tree)) == ["docs"])
    assert not (remote / "hello.txt").exists()
    assert len(shown["questions"]) == 1


def test_a_folder_that_is_not_empty_is_not_deleted_and_says_so(app, tree, remote, shown):
    tree.action_delete(_child(_root(tree), "docs"))

    wait_until(app, lambda: shown["messages"])
    assert shown["messages"][0][0] == "critical"
    assert (remote / "docs" / "readme.txt").exists()
    assert "docs" in _names(_root(tree))


def test_a_download_ends_on_disk_whole(app, tree, tmp_path, monkeypatch, shown):
    local = tmp_path / "local"
    local.mkdir()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(
        lambda *_args, **_kwargs: (str(local / "copy.txt"), "")))

    tree.action_download(_child(_root(tree), "hello.txt"))

    wait_until(app, lambda: shown["messages"])
    assert shown["messages"][0][0] == "information"
    assert (local / "copy.txt").read_bytes() == _HELLO
    assert [path.name for path in local.iterdir()] == ["copy.txt"]  # no temporary file left


def test_an_upload_ends_on_the_server_and_in_the_folder(app, tree, tmp_path, remote, monkeypatch, shown):
    upload = tmp_path / "up.txt"
    upload.write_bytes(b"uploaded")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *_args, **_kwargs: (str(upload), "")))
    docs = _child(_root(tree), "docs")

    tree.action_upload(docs)

    wait_until(app, lambda: "up.txt" in _names(docs))
    assert (remote / "docs" / "up.txt").read_bytes() == b"uploaded"
    assert sorted(path.name for path in (remote / "docs").iterdir()) == ["readme.txt", "up.txt"]


@pytest.mark.parametrize(("answer", "kept"), [
    (QMessageBox.StandardButton.No, b"on the server"),
    (QMessageBox.StandardButton.Yes, b"uploaded"),
])
def test_an_upload_over_a_file_asks_first(app, tree, tmp_path, remote, monkeypatch, shown, answer, kept):
    (remote / "docs" / "up.txt").write_bytes(b"on the server")
    upload = tmp_path / "up.txt"
    upload.write_bytes(b"uploaded")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *_args, **_kwargs: (str(upload), "")))
    shown["answer"] = answer

    tree.action_upload(_child(_root(tree), "docs"))

    wait_until(app, lambda: shown["questions"] and tree._transfer is None)
    if answer == QMessageBox.StandardButton.Yes:
        wait_until(app, lambda: shown["messages"])
    assert (remote / "docs" / "up.txt").read_bytes() == kept

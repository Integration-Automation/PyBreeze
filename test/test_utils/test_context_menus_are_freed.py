"""The trees' right-click menus: deleted once they close, not kept as children of the tree
for good, and shown where they were asked for."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint
from PySide6.QtWidgets import QApplication, QFileSystemModel, QMenu, QTreeView

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget
from pybreeze.pybreeze_ui.editor_main import file_tree_context_menu


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class DismissedMenu(QMenu):
    """A menu that closes at once, as when the user presses Escape."""

    def exec(self, *args):
        return None


@pytest.fixture
def menus_dismissed(monkeypatch):
    # Setting exec on PySide's QMenu itself does not reach the call
    for module in (file_tree_context_menu, ssh_file_viewer_widget):
        monkeypatch.setattr(module, "QMenu", DismissedMenu)


def _menus_left(widget) -> int:
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return len(widget.findChildren(QMenu))


def test_the_project_tree_menu_goes_once_closed(app, tmp_path, menus_dismissed):
    tree = QTreeView()
    model = QFileSystemModel()
    model.setRootPath(str(tmp_path))
    tree.setModel(model)
    for _ in range(3):
        file_tree_context_menu._show_context_menu(QPoint(1, 1), tree, main_window=None)
    assert _menus_left(tree) == 0
    tree.deleteLater()


def test_the_sftp_tree_menu_goes_once_closed(app, menus_dismissed):
    viewer = ssh_file_viewer_widget.SSHFileTreeManager()
    for _ in range(3):
        viewer.on_context_menu(QPoint(1, 1))
    assert _menus_left(viewer) == 0
    viewer.deleteLater()


def test_the_project_tree_menu_opens_where_it_was_asked_for(app, tmp_path, monkeypatch):
    # It opened at the mouse pointer, wherever that was, when the Menu key asked for it
    shown_at = []

    class RecordingMenu(QMenu):
        def exec(self, position, *args):
            shown_at.append(position)

    monkeypatch.setattr(file_tree_context_menu, "QMenu", RecordingMenu)
    tree = QTreeView()
    model = QFileSystemModel()
    model.setRootPath(str(tmp_path))
    tree.setModel(model)
    file_tree_context_menu._show_context_menu(QPoint(7, 9), tree, main_window=None)
    assert shown_at == [tree.viewport().mapToGlobal(QPoint(7, 9))]
    tree.deleteLater()

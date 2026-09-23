"""The project tree's right-click actions: creating, renaming, deleting, copying.

Every action is driven through a real ``QTreeView`` over a real ``QFileSystemModel``
rooted in a temporary directory, with the modal dialogs stubbed out so the answer
the user would have given is supplied directly.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QFileSystemWatcher, QPoint, Qt
from PySide6.QtWidgets import (
    QApplication, QFileSystemModel, QMessageBox, QTabWidget, QTreeView, QWidget
)

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.editor_main import file_tree_context_menu as ctx
from pybreeze.pybreeze_ui.editor_main.file_tree_context_menu import (
    _action_copy_path, _action_delete, _action_new_file, _action_new_folder,
    _action_rename, _attach_context_menu, _editors_under, _get_tree_root_path,
    _perform_file_op, _resolve_parent_dir, setup_file_tree_context_menu
)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def tree(app, tmp_path):
    """A tree view rooted at *tmp_path*, as the project tree would be."""
    view = QTreeView()
    model = QFileSystemModel()
    model.setRootPath(str(tmp_path))
    view.setModel(model)
    view.setRootIndex(model.index(str(tmp_path)))
    yield view
    view.deleteLater()


def answer(monkeypatch, text: str, accepted: bool = True) -> None:
    """Stub the name prompt with what the user would have typed."""
    monkeypatch.setattr(
        ctx.QInputDialog, "getText",
        staticmethod(lambda *a, **k: (text, accepted)))


def confirm(monkeypatch, yes: bool) -> None:
    """Stub the delete confirmation."""
    button = (QMessageBox.StandardButton.Yes if yes
              else QMessageBox.StandardButton.No)
    monkeypatch.setattr(
        ctx.QMessageBox, "question", staticmethod(lambda *a, **k: button))


@pytest.fixture()
def warnings(monkeypatch):
    """Collect the warning dialogs an action raises instead of showing them."""
    shown: list[str] = []
    monkeypatch.setattr(
        ctx.QMessageBox, "warning",
        staticmethod(lambda _p, _t, message, *a, **k: shown.append(message)))
    return shown


class FakeCodeEdit:
    """The editing area, recording what a rename reloads."""

    def __init__(self, path: str) -> None:
        self.current_file = path
        self.reloaded: list[str] = []

    def reset_highlighter(self) -> None:
        self.reloaded.append("highlighter")

    def load_git_baseline(self) -> None:
        self.reloaded.append("git baseline")

    def start_language_server(self) -> None:
        self.reloaded.append("language server")


class FakeEditor(QWidget):
    """Stands in for an EditorWidget holding one open file.

    A real QWidget, because the delete path looks the editor up with
    ``tab_widget.indexOf`` and removes its tab.
    """

    def __init__(self, path: str) -> None:
        super().__init__()
        self.current_file = path
        self.code_edit = FakeCodeEdit(path)
        # What JEditor's EditorWidget watches its file with
        self._file_watcher = QFileSystemWatcher([path], self)
        self._ignore_next_change = False
        self.renamed = False
        self.closed = False
        self.code_save_thread = None

    def rename_self_tab(self) -> None:
        self.renamed = True

    def close(self) -> bool:
        self.closed = True
        return super().close()


class FakeWindow(QWidget):
    """A main window with just the tab widget the actions reach for; docked editors are its children."""

    def __init__(self) -> None:
        super().__init__()
        self.tab_widget = QTabWidget()


class TestWhereANewItemGoes:
    def test_a_directory_receives_the_new_item(self, tree, tmp_path):
        folder = tmp_path / "pkg"
        folder.mkdir()
        assert _resolve_parent_dir(tree, folder) == folder

    def test_a_file_puts_it_beside_itself(self, tree, tmp_path):
        target = tmp_path / "module.py"
        target.touch()
        assert _resolve_parent_dir(tree, target) == tmp_path

    def test_no_selection_falls_back_to_the_tree_root(self, tree, tmp_path):
        assert _resolve_parent_dir(tree, None) == tmp_path

    def test_the_root_is_what_the_view_is_rooted_at(self, tree, tmp_path):
        assert _get_tree_root_path(tree) == tmp_path


class TestSurfacingFailures:
    def test_a_successful_operation_reports_success(self, tree):
        assert _perform_file_op(tree, lambda: None) is True

    def test_an_os_error_becomes_a_dialog_not_a_traceback(self, tree, warnings):
        def explode() -> None:
            raise OSError("disk is full")

        assert _perform_file_op(tree, explode) is False
        assert "disk is full" in warnings[0]


class TestCreating:
    def test_a_new_file_appears(self, tree, tmp_path, monkeypatch):
        answer(monkeypatch, "notes.txt")
        _action_new_file(tree, None)
        assert (tmp_path / "notes.txt").is_file()

    def test_a_cancelled_prompt_creates_nothing(self, tree, tmp_path, monkeypatch):
        answer(monkeypatch, "notes.txt", accepted=False)
        _action_new_file(tree, None)
        assert not (tmp_path / "notes.txt").exists()

    def test_a_blank_name_creates_nothing(self, tree, tmp_path, monkeypatch):
        answer(monkeypatch, "   ")
        _action_new_file(tree, None)
        assert list(tmp_path.iterdir()) == []

    def test_the_name_is_trimmed(self, tree, tmp_path, monkeypatch):
        answer(monkeypatch, "  notes.txt  ")
        _action_new_file(tree, None)
        assert (tmp_path / "notes.txt").is_file()

    def test_an_existing_name_is_refused_rather_than_overwritten(
            self, tree, tmp_path, monkeypatch, warnings):
        existing = tmp_path / "notes.txt"
        existing.write_text("keep me", encoding="utf-8")
        answer(monkeypatch, "notes.txt")
        _action_new_file(tree, None)
        assert existing.read_text(encoding="utf-8") == "keep me"
        assert warnings

    def test_a_new_folder_appears(self, tree, tmp_path, monkeypatch):
        answer(monkeypatch, "package")
        _action_new_folder(tree, None)
        assert (tmp_path / "package").is_dir()

    def test_a_new_folder_lands_inside_the_selected_directory(
            self, tree, tmp_path, monkeypatch):
        parent = tmp_path / "outer"
        parent.mkdir()
        answer(monkeypatch, "inner")
        _action_new_folder(tree, parent)
        assert (parent / "inner").is_dir()

    def test_an_existing_folder_name_is_refused(
            self, tree, tmp_path, monkeypatch, warnings):
        (tmp_path / "package").mkdir()
        answer(monkeypatch, "package")
        _action_new_folder(tree, None)
        assert warnings


class TestRenaming:
    def test_the_file_moves_to_the_new_name(self, tree, tmp_path, monkeypatch):
        original = tmp_path / "old.py"
        original.write_text("body", encoding="utf-8")
        answer(monkeypatch, "new.py")
        _action_rename(tree, FakeWindow(), original)
        assert not original.exists()
        assert (tmp_path / "new.py").read_text(encoding="utf-8") == "body"

    def test_nothing_selected_does_nothing(self, tree, tmp_path, monkeypatch):
        answer(monkeypatch, "new.py")
        _action_rename(tree, FakeWindow(), None)
        assert list(tmp_path.iterdir()) == []

    def test_the_same_name_is_a_no_op(self, tree, tmp_path, monkeypatch):
        original = tmp_path / "same.py"
        original.touch()
        answer(monkeypatch, "same.py")
        _action_rename(tree, FakeWindow(), original)
        assert original.exists()

    def test_renaming_onto_an_existing_file_is_refused(
            self, tree, tmp_path, monkeypatch, warnings):
        original = tmp_path / "old.py"
        original.touch()
        occupied = tmp_path / "taken.py"
        occupied.write_text("keep me", encoding="utf-8")
        answer(monkeypatch, "taken.py")
        _action_rename(tree, FakeWindow(), original)
        assert original.exists()
        assert occupied.read_text(encoding="utf-8") == "keep me"
        assert warnings

    def test_a_change_of_case_is_a_rename(self, tree, tmp_path, monkeypatch, warnings):
        # On Windows "Main.py" already "exists" -- as the very file being renamed.
        original = tmp_path / "main.py"
        original.write_text("print(1)", encoding="utf-8")
        answer(monkeypatch, "Main.py")

        _action_rename(tree, FakeWindow(), original)

        assert warnings == []
        assert [child.name for child in tmp_path.iterdir()] == ["Main.py"]
        assert (tmp_path / "Main.py").read_text(encoding="utf-8") == "print(1)"

    def test_an_open_tab_follows_the_rename(self, tree, tmp_path, monkeypatch):
        original = tmp_path / "open.py"
        original.touch()
        window = FakeWindow()
        editor = FakeEditor(str(original))
        editor.code_save_thread = None
        monkeypatch.setattr(
            ctx, "_editors_under", lambda _w, _p: [(editor, original)])
        # The real one starts JEditor's save thread; the stand-in only records
        # where the tab now points, the way it does.
        monkeypatch.setattr(
            ctx, "init_new_auto_save_thread",
            lambda file_path, widget: setattr(widget, "current_file", file_path))
        answer(monkeypatch, "renamed.py")
        _action_rename(tree, window, original)
        assert editor.current_file == str(tmp_path / "renamed.py")
        assert editor.code_edit.current_file == str(tmp_path / "renamed.py")
        assert editor.renamed
        # As when JEditor opens a file: it watched the old name, and kept the
        # old name's highlighter, git baseline and language server
        assert [Path(one) for one in editor._file_watcher.files()] == [tmp_path / "renamed.py"]
        assert editor.code_edit.reloaded == ["highlighter", "git baseline", "language server"]


class TestDeleting:
    def test_a_confirmed_delete_removes_the_file(self, tree, tmp_path, monkeypatch):
        target = tmp_path / "gone.py"
        target.touch()
        confirm(monkeypatch, yes=True)
        _action_delete(tree, FakeWindow(), target)
        assert not target.exists()

    def test_declining_keeps_the_file(self, tree, tmp_path, monkeypatch):
        target = tmp_path / "kept.py"
        target.touch()
        confirm(monkeypatch, yes=False)
        _action_delete(tree, FakeWindow(), target)
        assert target.exists()

    def test_a_directory_goes_with_its_contents(self, tree, tmp_path, monkeypatch):
        folder = tmp_path / "pkg"
        folder.mkdir()
        (folder / "inner.py").touch()
        confirm(monkeypatch, yes=True)
        _action_delete(tree, FakeWindow(), folder)
        assert not folder.exists()

    def test_nothing_selected_does_nothing(self, tree, tmp_path, monkeypatch):
        confirm(monkeypatch, yes=True)
        _action_delete(tree, FakeWindow(), None)

    def test_an_open_tab_is_closed_with_the_file(self, tree, tmp_path, monkeypatch):
        target = tmp_path / "open.py"
        target.touch()
        window = FakeWindow()
        editor = FakeEditor(str(target))
        window.tab_widget.addTab(editor, "open.py")
        monkeypatch.setattr(ctx, "_editors_under", lambda _w, _p: [(editor, target)])
        confirm(monkeypatch, yes=True)
        _action_delete(tree, window, target)
        assert editor.closed
        assert window.tab_widget.count() == 0
        assert not target.exists()

    def test_every_tab_inside_a_deleted_folder_is_closed(self, tree, tmp_path, monkeypatch):
        folder = tmp_path / "pkg"
        folder.mkdir()
        inside = [folder / "a.py", folder / "b.py"]
        for file in inside:
            file.touch()
        window = FakeWindow()
        editors = [FakeEditor(str(file)) for file in inside]
        outside = FakeEditor(str(tmp_path / "other.py"))
        for editor in (*editors, outside):
            window.tab_widget.addTab(editor, "tab")
        asked = []

        def under(_window, path):
            asked.append(path)
            return list(zip(editors, inside))

        monkeypatch.setattr(ctx, "_editors_under", under)
        confirm(monkeypatch, yes=True)
        _action_delete(tree, window, folder)

        assert asked == [folder]
        assert all(editor.closed for editor in editors)
        assert not outside.closed
        assert window.tab_widget.count() == 1
        assert not folder.exists()

    def test_a_delete_that_fails_keeps_the_tab_open(self, tree, tmp_path, monkeypatch):
        # The tabs used to close before the delete ran, so a locked file stayed
        # on disk while its tab, and any unsaved edits in it, were gone.
        target = tmp_path / "locked.py"
        target.touch()
        window = FakeWindow()
        editor = FakeEditor(str(target))
        window.tab_widget.addTab(editor, "locked.py")
        monkeypatch.setattr(ctx, "_editors_under", lambda _w, _p: [(editor, target)])
        restarted: list = []
        monkeypatch.setattr(
            ctx, "init_new_auto_save_thread",
            lambda file_path, widget: restarted.append(file_path))
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

        def refuse(self, *args, **kwargs):
            raise PermissionError(13, "The process cannot access the file")

        monkeypatch.setattr(Path, "unlink", refuse)
        confirm(monkeypatch, yes=True)
        _action_delete(tree, window, target)

        assert target.exists()
        assert not editor.closed
        assert window.tab_widget.count() == 1
        # Its auto-save, stopped for the delete, runs again.
        assert restarted == [str(target)]


class TestCopyingThePath:
    def test_the_absolute_path_reaches_the_clipboard(self, tree, tmp_path):
        target = tmp_path / "module.py"
        target.touch()
        _action_copy_path(tree, target, relative=False)
        assert QApplication.clipboard().text() == str(target)

    def test_the_relative_path_is_relative_to_the_tree_root(self, tree, tmp_path):
        nested = tmp_path / "pkg"
        nested.mkdir()
        target = nested / "module.py"
        target.touch()
        _action_copy_path(tree, target, relative=True)
        assert QApplication.clipboard().text() == os.path.join("pkg", "module.py")

    def test_a_path_outside_the_root_falls_back_to_absolute(self, tree, tmp_path):
        outside = tmp_path.parent / "elsewhere.py"
        _action_copy_path(tree, outside, relative=True)
        assert QApplication.clipboard().text() == str(outside)

    def test_nothing_selected_leaves_the_clipboard_alone(self, tree):
        QApplication.clipboard().setText("untouched")
        _action_copy_path(tree, None)
        assert QApplication.clipboard().text() == "untouched"


class TestFindingTheOpenEditors:
    def test_a_window_with_no_editor_tabs_finds_nothing(self, app, tmp_path):
        assert _editors_under(FakeWindow(), tmp_path / "any.py") == []


class TestAttachingTheMenu:
    def test_the_view_switches_to_a_custom_menu(self, tree):
        _attach_context_menu(tree, FakeWindow())
        assert tree.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    def test_attaching_twice_still_opens_one_menu(self, tree, monkeypatch):
        # A second attach must not connect the signal again: two handlers would
        # pop the context menu twice for a single right-click.
        opened: list[object] = []
        monkeypatch.setattr(
            ctx, "_show_context_menu",
            lambda pos, tv, mw: opened.append(pos))
        window = FakeWindow()
        _attach_context_menu(tree, window)
        _attach_context_menu(tree, window)
        tree.customContextMenuRequested.emit(QPoint(1, 1))
        assert len(opened) == 1

    def test_setup_leaves_later_tabs_working(self, app):
        # setup wraps addTab so future editor tabs also get the menu; the wrapper
        # must still add the tab and return the index addTab promises.
        window = FakeWindow()
        setup_file_tree_context_menu(window)
        placeholder = QTreeView()
        index = window.tab_widget.addTab(placeholder, "tab")
        assert index == 0
        assert window.tab_widget.count() == 1
        placeholder.deleteLater()

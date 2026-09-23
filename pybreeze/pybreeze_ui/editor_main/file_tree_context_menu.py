from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QTreeView, QMenu, QFileSystemModel, QInputDialog,
    QMessageBox, QApplication,
)
from je_editor import EditorWidget, language_wrapper
from je_editor.pyside_ui.code.auto_save.auto_save_manager import (
    auto_save_manager_dict, file_is_open_manager_dict, init_new_auto_save_thread,
)

from pybreeze.utils.logging.logger import pybreeze_logger


def _perform_file_op(tree_view: QTreeView, operation: Callable[[], None]) -> bool:
    """Run a filesystem mutation, surfacing failures as a dialog, not a traceback.

    Returns ``True`` on success, ``False`` if the operation raised ``OSError``.
    """
    word = language_wrapper.language_word_dict
    try:
        operation()
        return True
    except OSError as error:
        pybreeze_logger.error("File tree operation failed: %r", error)
        QMessageBox.warning(tree_view, word.get("file_tree_ctx_error"), str(error))
        return False


def setup_file_tree_context_menu(main_window) -> None:
    """
    Attach a right-click context menu to every current and future
    EditorWidget's project_treeview.
    """
    # Attach to existing tabs
    for i in range(main_window.tab_widget.count()):
        widget = main_window.tab_widget.widget(i)
        if isinstance(widget, EditorWidget) and widget.project_treeview is not None:
            _attach_context_menu(widget.project_treeview, main_window)

    # Listen for new tabs so future EditorWidgets also get the context menu
    original_add_tab = main_window.tab_widget.addTab

    def patched_add_tab(*args, **kwargs):
        result = original_add_tab(*args, **kwargs)
        widget = args[0] if args else None
        if isinstance(widget, EditorWidget) and widget.project_treeview is not None:
            _attach_context_menu(widget.project_treeview, main_window)
        return result

    main_window.tab_widget.addTab = patched_add_tab


def _attach_context_menu(tree_view: QTreeView, main_window) -> None:
    # Idempotent: a tree view already switched to CustomContextMenu has our
    # handler connected, so skip it — otherwise a repeated setup would connect
    # the signal again and fire the menu multiple times per right-click.
    if tree_view.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu:
        return
    tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tree_view.customContextMenuRequested.connect(
        lambda pos, tv=tree_view, mw=main_window: _show_context_menu(pos, tv, mw)
    )


def _get_path_from_index(tree_view: QTreeView, index: QModelIndex) -> Path | None:
    model: QFileSystemModel = tree_view.model()
    if not index.isValid():
        return None
    return Path(model.filePath(index))


def _get_tree_root_path(tree_view: QTreeView) -> Path:
    """Get the root directory currently shown in the tree view."""
    model: QFileSystemModel = tree_view.model()
    root_index = tree_view.rootIndex()
    if root_index.isValid():
        return Path(model.filePath(root_index))
    return Path.cwd()


def _show_context_menu(pos, tree_view: QTreeView, main_window) -> None:
    word = language_wrapper.language_word_dict
    index = tree_view.indexAt(pos)
    path = _get_path_from_index(tree_view, index)

    menu = QMenu(tree_view)

    # --- File / Folder creation ---
    new_file_act = menu.addAction(word.get("file_tree_ctx_new_file"))
    new_folder_act = menu.addAction(word.get("file_tree_ctx_new_folder"))
    menu.addSeparator()

    # --- Operations on selected item ---
    rename_act = menu.addAction(word.get("file_tree_ctx_rename"))
    delete_act = menu.addAction(word.get("file_tree_ctx_delete"))
    rename_act.setEnabled(path is not None)
    delete_act.setEnabled(path is not None)
    menu.addSeparator()

    # --- Clipboard ---
    copy_path_act = menu.addAction(word.get("file_tree_ctx_copy_path"))
    copy_rel_path_act = menu.addAction(word.get("file_tree_ctx_copy_relative_path"))
    copy_path_act.setEnabled(path is not None)
    copy_rel_path_act.setEnabled(path is not None)
    menu.addSeparator()

    # --- Explorer ---
    reveal_act = menu.addAction(word.get("file_tree_ctx_reveal_in_explorer"))
    reveal_act.setEnabled(path is not None)

    action = menu.exec(QCursor.pos())
    if action is None:
        return

    if action == new_file_act:
        _action_new_file(tree_view, path)
    elif action == new_folder_act:
        _action_new_folder(tree_view, path)
    elif action == rename_act:
        _action_rename(tree_view, main_window, path)
    elif action == delete_act:
        _action_delete(tree_view, main_window, path)
    elif action == copy_path_act:
        _action_copy_path(tree_view, path, relative=False)
    elif action == copy_rel_path_act:
        _action_copy_path(tree_view, path, relative=True)
    elif action == reveal_act:
        _action_reveal_in_explorer(path)


# --------------- actions ---------------

def _resolve_parent_dir(tree_view: QTreeView, path: Path | None) -> Path:
    """Return the directory where a new file/folder should be created."""
    if path is not None:
        return path if path.is_dir() else path.parent
    return _get_tree_root_path(tree_view)


def _action_new_file(tree_view: QTreeView, path: Path | None) -> None:
    word = language_wrapper.language_word_dict
    parent = _resolve_parent_dir(tree_view, path)
    name, ok = QInputDialog.getText(
        tree_view,
        word.get("file_tree_ctx_new_file"),
        word.get("file_tree_ctx_input_file_name"),
    )
    if not ok or not name.strip():
        return
    new_path = parent / name.strip()
    if new_path.exists():
        QMessageBox.warning(
            tree_view,
            word.get("file_tree_ctx_error"),
            word.get("file_tree_ctx_already_exists").format(name=str(new_path)),
        )
        return
    def _create() -> None:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.touch()

    _perform_file_op(tree_view, _create)


def _action_new_folder(tree_view: QTreeView, path: Path | None) -> None:
    word = language_wrapper.language_word_dict
    parent = _resolve_parent_dir(tree_view, path)
    name, ok = QInputDialog.getText(
        tree_view,
        word.get("file_tree_ctx_new_folder"),
        word.get("file_tree_ctx_input_folder_name"),
    )
    if not ok or not name.strip():
        return
    new_path = parent / name.strip()
    if new_path.exists():
        QMessageBox.warning(
            tree_view,
            word.get("file_tree_ctx_error"),
            word.get("file_tree_ctx_already_exists").format(name=str(new_path)),
        )
        return
    _perform_file_op(tree_view, lambda: new_path.mkdir(parents=True))


def _editors_under(main_window, path: Path) -> list[tuple[EditorWidget, Path]]:
    """The editor tabs open on *path*, or on any file under it, with their files."""
    found = []
    for index in range(main_window.tab_widget.count()):
        widget = main_window.tab_widget.widget(index)
        if not isinstance(widget, EditorWidget) or widget.current_file is None:
            continue
        file_path = Path(widget.current_file)
        if file_path == path or path in file_path.parents:
            found.append((widget, file_path))
    return found


def _stop_auto_save(editor: EditorWidget) -> None:
    """Stop the tab's auto-save and forget the path it was registered under.

    JEditor's save thread loops for as long as the path it *started* with is a
    file, writing to whatever ``file`` holds; after a rename it would write the
    buffer back to the old name -- recreating it, so it never stops -- and never
    save the new one. It cannot be pointed elsewhere, only replaced.
    """
    if editor.code_save_thread is not None:
        editor.code_save_thread.still_run = False
        editor.code_save_thread = None
    old = str(editor.current_file)
    auto_save_manager_dict.pop(old, None)
    file_is_open_manager_dict.pop(str(Path(old)), None)


def _start_auto_save(editor: EditorWidget, file_path: Path) -> None:
    """Point the tab at *file_path* and start its auto-save there."""
    editor.code_edit.current_file = str(file_path)
    file_is_open_manager_dict[str(file_path)] = str(file_path)
    # Sets current_file, carries the tab's encoding and line ending, and starts
    # the thread, as JEditor does when it opens a file.
    init_new_auto_save_thread(str(file_path), editor)
    editor.rename_self_tab()


def _is_the_same_file(first: Path, second: Path) -> bool:
    """Whether *first* and *second* name one file (a different case of one name, say)."""
    try:
        return first.samefile(second)
    except OSError as error:
        pybreeze_logger.debug("Could not compare %s and %s: %r", first, second, error)
        return False


def _action_rename(tree_view: QTreeView, main_window, path: Path | None) -> None:
    if path is None:
        return
    word = language_wrapper.language_word_dict
    new_name, ok = QInputDialog.getText(
        tree_view,
        word.get("file_tree_ctx_rename"),
        word.get("file_tree_ctx_input_new_name").format(name=path.name),
        text=path.name,
    )
    if not ok or not new_name.strip() or new_name.strip() == path.name:
        return
    target = path.parent / new_name.strip()
    # On a case-insensitive filesystem "A.py" already exists when renaming
    # "a.py" to it -- it is the same file, and a change of case is a rename.
    if target.exists() and not _is_the_same_file(target, path):
        QMessageBox.warning(
            tree_view,
            word.get("file_tree_ctx_error"),
            word.get("file_tree_ctx_already_exists").format(name=str(target)),
        )
        return

    # Every tab open on the file, or on a file under the folder, follows it. Their
    # auto-save stops first, so none writes to the old path mid-rename.
    moving = _editors_under(main_window, path)
    for editor, _old in moving:
        _stop_auto_save(editor)
    renamed = _perform_file_op(tree_view, lambda: path.rename(target))
    for editor, old in moving:
        now = target / old.relative_to(path) if renamed else old
        _start_auto_save(editor, now)


def _action_delete(tree_view: QTreeView, main_window, path: Path | None) -> None:
    if path is None:
        return
    word = language_wrapper.language_word_dict
    reply = QMessageBox.question(
        tree_view,
        word.get("file_tree_ctx_confirm_delete"),
        word.get("file_tree_ctx_confirm_delete_message").format(name=str(path)),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    # Every tab open on the file, or on a file under the folder, closes first:
    # closing stops its auto-save, which would otherwise keep writing the
    # buffer back while the files are being removed.
    for editor, _file in _editors_under(main_window, path):
        index = main_window.tab_widget.indexOf(editor)
        editor.close()
        if index >= 0:
            main_window.tab_widget.removeTab(index)

    def _delete() -> None:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    _perform_file_op(tree_view, _delete)


def _action_copy_path(tree_view: QTreeView, path: Path | None, relative: bool = False) -> None:
    if path is None:
        return
    if relative:
        base = _get_tree_root_path(tree_view)
        try:
            text = str(path.relative_to(base))
        except ValueError:
            text = str(path)
    else:
        text = str(path)
    clipboard = QApplication.clipboard()
    clipboard.setText(text)


def _action_reveal_in_explorer(path: Path | None) -> None:
    if path is None:
        return
    target = path if path.is_dir() else path.parent
    # "Reveal in file explorer" — platform file-manager invocation on a path the
    # user already selected in our tree. shell=False, fixed argv[0]. nosec B603/B606/B607.
    if sys.platform == "win32":
        os.startfile(str(target))  # nosec B606  # nosemgrep  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])  # nosec B603 B607  # nosemgrep  # noqa: S603,S607
    else:
        subprocess.Popen(["xdg-open", str(target)])  # nosec B603 B607  # nosemgrep  # noqa: S603,S607

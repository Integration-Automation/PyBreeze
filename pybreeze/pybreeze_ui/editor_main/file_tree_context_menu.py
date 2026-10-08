from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path, PureWindowsPath

from PySide6.QtCore import QFile, Qt, QModelIndex
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QTreeView, QMenu, QFileSystemModel, QInputDialog,
    QMessageBox, QApplication,
)
from je_editor import EditorWidget, language_wrapper
from je_editor.pyside_ui.code.auto_save.auto_save_manager import (
    auto_save_manager_dict, file_is_open_manager_dict, init_new_auto_save_thread,
)
from je_editor.pyside_ui.main_ui.editor.editor_widget_dock import FullEditorWidget

from pybreeze.pybreeze_ui.plain_text import as_text
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.subprocess_util import child_environment


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
        QMessageBox.warning(tree_view, word.get("file_tree_ctx_error"), as_text(str(error)))
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
    _attach_keys(tree_view, main_window)


# Keys that act on the entry in focus while the tree has the focus, as in a file manager
_RENAME_KEY = QKeySequence(Qt.Key.Key_F2)
_DELETE_KEY = QKeySequence(Qt.Key.Key_Delete)


def _attach_keys(tree_view: QTreeView, main_window) -> None:
    """F2 renames and Delete deletes the current entry, through the menu's own actions.

    Only while the tree itself has the focus (``WidgetShortcut``): Delete in the
    editor beside it is the editor's. Delete asks first, No being the default.
    """
    for keys, act in ((_RENAME_KEY, "rename"), (_DELETE_KEY, "delete")):
        shortcut = QShortcut(keys, tree_view)
        shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        shortcut.activated.connect(
            lambda tv=tree_view, mw=main_window, what=act: _act_on_current(what, tv, mw))


def _act_on_current(what: str, tree_view: QTreeView, main_window) -> None:
    """Rename or delete (*what*) the entry in focus, if there is one."""
    path = _get_path_from_index(tree_view, tree_view.currentIndex())
    if what == "rename":
        _action_rename(tree_view, main_window, path)
    else:
        _action_delete(tree_view, main_window, path)


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
    for act, keys in ((rename_act, _RENAME_KEY), (delete_act, _DELETE_KEY)):
        act.setShortcut(keys)  # shown beside the entry: the tree's own keys do it
        act.setShortcutVisibleInContextMenu(True)
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

    action = menu.exec(tree_view.viewport().mapToGlobal(pos))
    menu.deleteLater()  # a child of the tree: kept for good otherwise, one per right-click
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
        _action_reveal_in_explorer(tree_view, path)


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
    new_path = _inside(tree_view, parent, name.strip())
    if new_path is None:
        return
    if new_path.exists():
        QMessageBox.warning(
            tree_view,
            word.get("file_tree_ctx_error"),
            as_text(word.get("file_tree_ctx_already_exists").format(name=str(new_path))),
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
    new_path = _inside(tree_view, parent, name.strip())
    if new_path is None:
        return
    if new_path.exists():
        QMessageBox.warning(
            tree_view,
            word.get("file_tree_ctx_error"),
            as_text(word.get("file_tree_ctx_already_exists").format(name=str(new_path))),
        )
        return
    _perform_file_op(tree_view, lambda: new_path.mkdir(parents=True))


def _is_at_or_under(file_path: Path, path: Path) -> bool:
    """Whether *file_path* is *path* or lies under it."""
    return file_path == path or path in file_path.parents


def _editors_under(main_window, path: Path) -> list[tuple[EditorWidget, Path]]:
    """The editor tabs open on *path*, or on any file under it, with their files."""
    found = []
    for index in range(main_window.tab_widget.count()):
        widget = main_window.tab_widget.widget(index)
        if not isinstance(widget, EditorWidget) or widget.current_file is None:
            continue
        file_path = Path(widget.current_file)
        if _is_at_or_under(file_path, path):
            found.append((widget, file_path))
    return found


def _dock_editors_under(main_window, path: Path) -> list[tuple[FullEditorWidget, Path]]:
    """The docked editors (JEditor's Dock Editor) open on *path* or under it, with their files.

    A docked editor has no auto-save: it writes its buffer back when it closes,
    and only if its file still exists. Left on the old name after a rename, it
    wrote nothing, and every edit made in it was lost.
    """
    found = []
    for editor in main_window.findChildren(FullEditorWidget):
        if editor.current_file and _is_at_or_under(Path(editor.current_file), path):
            found.append((editor, Path(editor.current_file)))
    return found


def _unwatch(editor: EditorWidget) -> None:
    """Stop the tab watching its file for changes made outside the IDE.

    Done before the file moves: once it is gone, Windows does not let go of
    the old name.
    """
    watcher = editor._file_watcher  # noqa: SLF001 — JEditor's own watcher; handled as open_an_file handles it (test_jeditor_contract.py)
    watched = watcher.files()
    if watched:
        watcher.removePaths(watched)


def _watch(editor: EditorWidget, file_path: Path) -> None:
    """Watch *file_path* for changes made outside the IDE, as JEditor's ``open_an_file`` does.

    Left on the old name, a change made to the renamed file outside the IDE
    raised no question, and the tab's auto-save wrote over it.
    """
    _unwatch(editor)
    editor._file_watcher.addPath(str(file_path))  # noqa: SLF001 — see _unwatch
    # A save to the old name may have left it set, and it would swallow the
    # first real change to the new one
    editor._ignore_next_change = False  # noqa: SLF001 — see _unwatch


def _stop_auto_save(editor: EditorWidget) -> None:
    """Stop the tab's auto-save and its watch, and forget the path it was registered under.

    JEditor's save thread loops for as long as the path it *started* with is a
    file, writing to whatever ``file`` holds; after a rename it would write the
    buffer back to the old name -- recreating it, so it never stops -- and never
    save the new one. It cannot be pointed elsewhere, only replaced.
    """
    if editor.code_save_thread is not None:
        editor.code_save_thread.still_run = False
        editor.code_save_thread = None
    _unwatch(editor)
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
    _watch(editor, file_path)
    # As when JEditor opens a file: a new suffix may be another language, and
    # the git baseline and the language server go by the path
    editor.code_edit.reset_highlighter()
    editor.code_edit.load_git_baseline()
    editor.code_edit.start_language_server()
    # rename_self_tab clears the unsaved mark, but nothing was saved: the old
    # save thread was stopped without writing and the new one waits before its
    # first write, and closing the tab in that time lost the edits unasked
    unsaved = bool(getattr(editor, "_is_modified", False))
    editor.rename_self_tab()
    if unsaved:
        editor._on_text_changed()


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
        as_text(word.get("file_tree_ctx_input_new_name").format(name=path.name)),
        text=path.name,
    )
    if not ok or not new_name.strip() or new_name.strip() == path.name:
        return
    target = _inside(tree_view, path.parent, new_name.strip(), single=True)
    if target is None:
        return
    # On a case-insensitive filesystem "A.py" already exists when renaming
    # "a.py" to it -- it is the same file, and a change of case is a rename.
    if target.exists() and not _is_the_same_file(target, path):
        QMessageBox.warning(
            tree_view,
            word.get("file_tree_ctx_error"),
            as_text(word.get("file_tree_ctx_already_exists").format(name=str(target))),
        )
        return

    # Every tab open on the file, or on a file under the folder, follows it. Their
    # auto-save stops first, so none writes to the old path mid-rename.
    moving = _editors_under(main_window, path)
    docked = _dock_editors_under(main_window, path)
    for editor, _old in moving:
        _stop_auto_save(editor)
    renamed = _perform_file_op(tree_view, lambda: path.rename(target))
    for editor, old in moving:
        now = target / old.relative_to(path) if renamed else old
        _start_auto_save(editor, now)
    if renamed:
        for dock_editor, old in docked:
            dock_editor.current_file = str(target / old.relative_to(path))


def _action_delete(tree_view: QTreeView, main_window, path: Path | None) -> None:
    if path is None:
        return
    word = language_wrapper.language_word_dict
    reply = QMessageBox.question(
        tree_view,
        word.get("file_tree_ctx_confirm_delete"),
        as_text(word.get("file_tree_ctx_confirm_delete_message").format(name=str(path))),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    # Every tab open on the file, or on a file under the folder, stops its
    # auto-save first, which would otherwise write the buffer back -- recreating
    # the file -- while it is being removed.
    open_tabs = _editors_under(main_window, path)
    for editor, _file in open_tabs:
        _stop_auto_save(editor)

    _remove(tree_view, path)
    # Only a tab whose file is gone closes. The delete can fail -- a locked or
    # read-only file -- or remove only part of a folder, and closing the tabs
    # beforehand lost a file's tab and its unsaved edits while the file stayed.
    for editor, file_path in open_tabs:
        if file_path.exists():
            _start_auto_save(editor, file_path)
            continue
        index = main_window.tab_widget.indexOf(editor)
        editor.close()
        if index >= 0:
            main_window.tab_widget.removeTab(index)


def _move_to_trash(path: Path) -> bool:
    """Move *path* to the system's trash (the Recycle Bin on Windows); ``False`` where there is none."""
    return QFile.moveToTrash(str(path))


def _remove(tree_view: QTreeView, path: Path) -> None:
    """Move *path* to the trash; where there is none, delete it for good if the user says so.

    A link (a symbolic link, a junction) is removed itself, never moved: what
    it points to stays where it is.
    """
    if _is_link(path):
        _perform_file_op(tree_view, lambda: _remove_link(path))
        return
    if _move_to_trash(path):
        return
    word = language_wrapper.language_word_dict
    reply = QMessageBox.question(
        tree_view,
        word.get("file_tree_ctx_confirm_delete"),
        as_text(word.get("file_tree_ctx_no_trash").format(name=str(path))),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if reply == QMessageBox.StandardButton.Yes:
        _perform_file_op(tree_view, lambda: remove_folder(path) if path.is_dir() else path.unlink())


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


def reveal_command(path: Path, platform: str = sys.platform) -> list[str]:
    """The command that shows *path* in the platform's file manager.

    A file is shown selected in its folder where the file manager can do that
    (Explorer's ``/select,``, Finder's ``open -R``); it used to open the folder
    alone, leaving the user to find the file in it. ``xdg-open`` can only open
    a folder, so elsewhere a file's folder is opened.
    """
    is_folder = path.is_dir()
    if platform == "win32":
        explorer = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "explorer.exe")
        return [explorer, str(path)] if is_folder else [explorer, "/select,", str(path)]
    if platform == "darwin":
        return ["open", str(path)] if is_folder else ["open", "-R", str(path)]
    return ["xdg-open", str(path if is_folder else path.parent)]


def _action_reveal_in_explorer(tree_view: QTreeView, path: Path | None) -> None:
    if path is None:
        return
    command = reveal_command(path)
    # A file manager started on a path the user picked in the tree. shell=False,
    # fixed argv[0]; a missing xdg-open is shown, not raised out of the slot.
    _perform_file_op(tree_view, lambda: subprocess.Popen(command, env=child_environment()))  # nosec B603 B607  # nosemgrep  # noqa: S603


def _inside(tree_view: QTreeView, parent: Path, name: str, *, single: bool = False) -> Path | None:
    """*parent* / *name*, or ``None`` after saying why *name* cannot go there.

    A name with a drive, a root, ``..`` or a ``:`` (a drive-relative path, or an
    NTFS stream) went elsewhere: ``/tmp/notes.py`` was created as
    ``C:\\tmp\\notes.py`` and a rename to ``/a.py`` moved the file to the drive
    root. With *single*, the name must be one entry (a rename), not a path.
    """
    parts = PureWindowsPath(name)
    escapes = (parts.drive or parts.root or ":" in name or ".." in parts.parts
               or (single and len(parts.parts) != 1))
    target = parent / name
    if not escapes:
        try:
            escapes = not target.resolve().is_relative_to(parent.resolve())
        except OSError:
            escapes = True
    if not escapes:
        return target
    word = language_wrapper.language_word_dict
    QMessageBox.warning(tree_view, word.get("file_tree_ctx_error"),
                        as_text(word.get("file_tree_ctx_bad_name").format(name=name)))
    return None


def _is_link(path: Path) -> bool:
    """Whether *path* is a symbolic link or a Windows junction (a link either way)."""
    if path.is_symlink():
        return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _remove_link(path: Path) -> None:
    """Remove the link at *path*, never what it points to.

    ``rmtree`` refuses a link to a folder, so one could not be deleted at all.
    """
    try:
        os.unlink(path)
    except (IsADirectoryError, PermissionError):
        os.rmdir(path)  # a junction, or a directory symlink on an older Windows


def _clear_read_only_and_retry(function: Callable[[str], None], path: str, _error: object) -> None:
    """``rmtree``'s error handler: make *path* writable and try *function* again."""
    os.chmod(path, stat.S_IWRITE)
    function(path)


def remove_folder(path: Path) -> None:
    """Delete the folder *path* and everything in it, read-only files included.

    ``shutil.rmtree`` stops at the first read-only file on Windows, after
    removing what came before it: git makes its objects read-only, so deleting
    a cloned project left it half deleted with a broken repository.

    :raises OSError: when something in it still cannot be removed
    """
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear_read_only_and_retry)
    else:
        shutil.rmtree(path, onerror=_clear_read_only_and_retry)

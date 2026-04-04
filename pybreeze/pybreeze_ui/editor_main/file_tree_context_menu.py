import os
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QTreeView, QMenu, QFileSystemModel, QInputDialog,
    QMessageBox, QApplication,
)
from je_editor import language_wrapper
from je_editor.pyside_ui.main_ui.editor.editor_widget import EditorWidget


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
            if widget.project_treeview.contextMenuPolicy() != Qt.ContextMenuPolicy.CustomContextMenu:
                _attach_context_menu(widget.project_treeview, main_window)
        return result

    main_window.tab_widget.addTab = patched_add_tab


def _attach_context_menu(tree_view: QTreeView, main_window) -> None:
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
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.touch()


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
    new_path.mkdir(parents=True)


def _find_editor_for_file(main_window, file_path: Path) -> EditorWidget | None:
    """Find the EditorWidget that has the given file open."""
    path_str = str(file_path)
    for i in range(main_window.tab_widget.count()):
        widget = main_window.tab_widget.widget(i)
        if isinstance(widget, EditorWidget) and widget.current_file is not None:
            if str(Path(widget.current_file)) == path_str:
                return widget
    return None


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
    if target.exists():
        QMessageBox.warning(
            tree_view,
            word.get("file_tree_ctx_error"),
            word.get("file_tree_ctx_already_exists").format(name=str(target)),
        )
        return

    # If this file is currently open in an editor tab, update the tab
    editor = _find_editor_for_file(main_window, path)
    path.rename(target)
    if editor is not None and target.is_file():
        editor.current_file = str(target)
        editor.code_edit.current_file = str(target)
        editor.rename_self_tab()


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

    # Close editor tab if this file is open
    editor = _find_editor_for_file(main_window, path)
    if editor is not None:
        idx = main_window.tab_widget.indexOf(editor)
        if idx >= 0:
            editor.close()
            main_window.tab_widget.removeTab(idx)

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


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
    import subprocess
    import sys
    target = path if path.is_dir() else path.parent
    if sys.platform == "win32":
        os.startfile(str(target))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])

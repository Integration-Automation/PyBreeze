"""The SFTP file tree: a lazily listed remote tree and its context menu.

The session and the threads that use it live in ``sftp_session.py``; this
module only shows what they report and starts them.
"""
from __future__ import annotations

import os
import posixpath
import re
import stat
from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QMenu, QFileDialog, QMessageBox, QSplitter, QInputDialog, QStyle
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.connect_gui.ssh.sftp_session import (
    SFTPClientWrapper, SftpCallThread, SftpListThread, SftpTransferThread, plain_remote_name,
    remote_join,
)
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_connect_thread import CONNECT_ERRORS, SshConnectThread
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_host_key_policy import host_key_asker
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_login_widget import LoginWidget
from pybreeze.pybreeze_ui.plain_text import as_text
from pybreeze.pybreeze_ui.thread_keeper import let_run_out


_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


def format_size(num_bytes: int) -> str:
    """Format a byte count for display, e.g. ``1536 -> '1.5 KB'`` (1024-based)."""
    if num_bytes < 0:
        return ""
    size = float(num_bytes)
    for unit in _SIZE_UNITS:
        if size < 1024 or unit == _SIZE_UNITS[-1]:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


# How long a replace waits for the upload that asked about it to return
UPLOAD_ASKED_WAIT_MS = 1000


# Item data: the serial of the listing a directory item is waiting for
LISTING_ROLE = Qt.ItemDataRole.UserRole
# Item data: set on the row a folder shows until it is first expanded. Told
# apart by its text, "...", a server entry named "..." was taken for it
PLACEHOLDER_ROLE = Qt.ItemDataRole.UserRole + 1
# Item data: what an entry is, "dir" or "file"; the placeholder and loading rows have none
KIND_ROLE = Qt.ItemDataRole.UserRole + 2


# What a Windows file name cannot hold
_NOT_IN_A_FILE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def local_file_name(remote_path: str) -> str:
    """A name to suggest for saving *remote_path* here: its last part, safe for this machine.

    A server's file name may hold backslashes: ``..\\..\\Startup\\u.bat`` was
    offered as the save name, which a save dialog can take as a path out of
    the folder it shows. Everything up to the last ``/`` or ``\\`` goes, and
    what Windows refuses in a name becomes ``_``.
    """
    name = re.split(r"[/\\]", remote_path)[-1]
    name = _NOT_IN_A_FILE_NAME.sub("_", name).strip(" .")
    return name or "download"


def is_folder(item: QTreeWidgetItem) -> bool:
    """Whether *item* is a remote folder."""
    return item.data(0, KIND_ROLE) == "dir"


def is_file(item: QTreeWidgetItem) -> bool:
    """Whether *item* is a remote file (not a folder, a placeholder or a loading row)."""
    return item.data(0, KIND_ROLE) == "file"


def folder_item(item: QTreeWidgetItem | None) -> QTreeWidgetItem | None:
    """The tree item of the folder *item* is in, or *item* itself when it is a folder."""
    if item is None or is_folder(item):
        return item
    return item.parent()


class SSHFileTreeManager(QWidget):
    """
    QWidget: connection form + tree + context menu.
    QWidget：連線表單 + 樹狀檔案管理 + 右鍵選單。
    """

    # Emitted when the session comes up or goes down, for the tab's status label
    state_changed = Signal()

    def __init__(self, external_login_widget: LoginWidget = None, add_login_widget: bool = True):
        super().__init__()
        self.word_dict = language_wrapper.language_word_dict
        self.setWindowTitle(
            self.word_dict.get("ssh_file_viewer_window_title_file_tree_manager")
        )
        self.add_login_widget = add_login_widget

        self.client = SFTPClientWrapper()
        # The connect in progress, if any / 正在進行的連線
        self._connecting: SshConnectThread | None = None
        host_key_asker()  # built here, on the UI thread, for a connect to ask through
        # The transfer in flight, if any / 正在進行的傳輸
        self._transfer: SftpTransferThread | None = None
        # Listings in flight / 正在進行的目錄列出
        self._listings: set[SftpListThread] = set()
        # The context menu's requests in flight / 右鍵選單正在進行的請求
        self._calls: set[SftpCallThread] = set()
        self._listing_serial = 0
        # Bumped whenever the tree is cleared: a listing started before then
        # returns to items that no longer exist.
        self._tree_generation = 0

        if self.add_login_widget:
            # 使用獨立的登入介面
            self.login_widget = LoginWidget()
        else:
            if external_login_widget is None:
                external_login_widget = LoginWidget()
            self.login_widget = external_login_widget

        # UI: Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            self.word_dict.get(f"ssh_file_viewer_tree_header_{column}")
            for column in ("name", "type", "size", "path")])
        self.tree.itemExpanded.connect(self.on_item_expanded)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_context_menu)

        # Layouts
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.login_widget)  # 插入登入介面
        splitter.addWidget(self.tree)
        splitter.setStretchFactor(1, 1)

        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.addWidget(splitter)
        self.setLayout(root_layout)

        # Signals
        self.login_widget.connect_btn.clicked.connect(self._connect)
        self.login_widget.disconnect_btn.clicked.connect(self._disconnect)

    def _connect(self):
        """
        Connect to SSH and load root.
        連線 SSH 並載入根目錄。
        """
        host = self.login_widget.host_edit.text().strip()
        port = self.login_widget.port_spin.value()
        user = self.login_widget.user_edit.text().strip()
        pwd = self.login_widget.pass_edit.text()
        use_key = self.login_widget.use_key_check.isChecked()
        key_path = self.login_widget.key_edit.text().strip()

        if not host or not user:
            QMessageBox.warning(
                self,
                self.word_dict.get("ssh_file_viewer_dialog_title_missing_input"),
                self.word_dict.get("ssh_file_viewer_dialog_message_missing_input"))
            return
        if self._connecting is not None and self._connecting.isRunning():
            return
        # A connect starts by closing the session, which cut a transfer short;
        # in the combined view the shared Connect button reached it to bring
        # the shell back
        if self._refused_while_transferring():
            return

        def connect() -> None:
            self.client.connect(host, port, user, pwd, use_key, key_path, parent_widget=self)

        # Off the UI thread, as for the shell: an unreachable host used to hold
        # the IDE for every timeout the connect has.
        thread = SshConnectThread(connect)
        thread.connected.connect(self._on_connected)
        thread.failed.connect(self._on_connect_failed)
        self._connecting = thread
        thread.start()

    def _on_connected(self) -> None:
        """List the root once the session is up. UI thread."""
        try:
            self.load_root("/")
        except CONNECT_ERRORS as error:
            self._on_connect_failed(str(error))
            return
        self.state_changed.emit()

    def _on_connect_failed(self, message: str) -> None:
        """Say why the connect failed. UI thread."""
        QMessageBox.critical(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_connection_failed"),
            # The server's text (paramiko quotes its first line): shown as text
            as_text(f"{self.word_dict.get('ssh_file_viewer_dialog_message_connection_failed')}: {message}"))
        self.state_changed.emit()

    def closeEvent(self, event) -> None:
        """Close the SFTP session with the widget.

        Qt delivers a close event only to the widget being closed, so a tab or a
        dock closing takes this route; without it the paramiko transport stays
        open, sending keepalives, for the rest of the session. A transfer still
        going is not waited for -- that froze the IDE for the rest of the
        transfer -- nor cut short, which would leave half a file: it is kept
        until it ends, and the session closes then.
        """
        transfer = self._transfer
        transfer_running = transfer is not None and transfer.isRunning()
        if transfer_running:
            let_run_out(transfer, transfer.done, transfer.failed, transfer.cancelled)
            transfer.finished.connect(self.client.close)
        for listing in list(self._listings):
            if listing.isRunning():
                let_run_out(listing, listing.listed, listing.failed)
        self._listings.clear()
        for call in list(self._calls):
            if call.isRunning():
                let_run_out(call, call.done, call.failed)
        self._calls.clear()
        if self._connecting is not None and self._connecting.isRunning():
            let_run_out(self._connecting, self._connecting.connected, self._connecting.failed)
            # A connect that still succeeds after the widget has gone would leave
            # its session open: close it whatever way the thread ends. (After
            # let_run_out, which cuts off everything connected to ``finished``.)
            self._connecting.finished.connect(self.client.close)
        if not transfer_running:
            self.client.close()
        super().closeEvent(event)

    def _disconnect(self):
        """
        Disconnect SSH.
        斷線 SSH。

        A connect still under way is given up on: it is cut off from this
        widget (no "connection failed" for a disconnect the user asked for),
        and the session it may still bring up is closed by
        ``SFTPClientWrapper.connect`` itself. Connect can be clicked again.
        """
        connecting = self._connecting
        if connecting is not None and connecting.isRunning():
            let_run_out(connecting, connecting.connected, connecting.failed)
            self._connecting = None
        self.client.close()
        self._clear_tree()
        self.state_changed.emit()

    def load_root(self, path: str = "/"):
        """
        Clear and load root items.
        清空並載入根項目。
        """
        self._clear_tree()
        root_item = self.make_item("/", "dir", 0, "/")
        self.tree.addTopLevelItem(root_item)
        # Listed once, here. Expanding an item that still had its placeholder
        # would list it a second time through on_item_expanded.
        self.populate_children(root_item)
        root_item.setExpanded(True)

    def _clear_tree(self) -> None:
        """Empty the tree; listings still running will find nothing to fill."""
        self._tree_generation += 1
        self.tree.clear()

    def make_item(self, name: str, typ: str, size: int, full_path: str) -> QTreeWidgetItem:
        """
        Create a tree item with metadata.
        建立帶有中繼資料的樹狀項目。
        """
        size_text = "" if typ == "dir" else format_size(size)
        kind_text = self.word_dict.get(f"ssh_file_viewer_type_{typ}")
        item = QTreeWidgetItem([name, kind_text, size_text, full_path])
        item.setData(0, KIND_ROLE, typ)
        if typ == "dir":
            # Use QStyle enum for standard icons
            # 使用 QStyle 列舉取得標準資料夾圖示
            item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        else:
            # Use QStyle enum for standard file icon
            # 使用 QStyle 列舉取得標準檔案圖示
            item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        return item

    def add_placeholder(self, item: QTreeWidgetItem):
        """
        Add a dummy child to indicate lazy-load.
        加入占位子項以表示可延遲載入。
        """
        placeholder = QTreeWidgetItem(["...", "", "", ""])
        placeholder.setData(0, PLACEHOLDER_ROLE, True)
        item.addChild(placeholder)

    def is_placeholder_present(self, item: QTreeWidgetItem) -> bool:
        """
        Check if the first child is a placeholder.
        檢查第一個子項是否為占位項。
        """
        if item.childCount() == 0:
            return False
        return item.child(0).data(0, PLACEHOLDER_ROLE) is True

    def on_item_expanded(self, item: QTreeWidgetItem):
        """
        When a directory is expanded, populate its children.
        展開目錄時載入子項目。
        """
        # Only load once
        if self.is_placeholder_present(item):
            # Remove placeholder then populate
            item.takeChild(0)
            self.populate_children(item)

    def populate_children(self, parent_item: QTreeWidgetItem):
        """
        List items under parent path and add to tree.
        列出父路徑下的項目並加入樹。
        """
        if not self.client.connected:
            return
        path = parent_item.text(3)
        # The rows arrive from a thread. Until then the item shows it is loading,
        # and it remembers which listing it is waiting for: a refresh started
        # meanwhile supersedes this one.
        self._listing_serial += 1
        serial = self._listing_serial
        parent_item.setData(0, LISTING_ROLE, serial)
        parent_item.addChild(QTreeWidgetItem([self.word_dict.get("ssh_file_viewer_loading"), "", "", ""]))
        generation = self._tree_generation
        listing = SftpListThread(self.client, path)
        listing.listed.connect(
            lambda rows: self._listing_done(parent_item, generation, serial, rows))
        listing.failed.connect(
            lambda message: self._listing_failed(parent_item, generation, serial, message))
        listing.finished.connect(self._forget_worker)
        self._listings.add(listing)
        listing.start()

    def _is_waiting_for(self, item: QTreeWidgetItem, generation: int, serial: int) -> bool:
        """Whether *item* still exists and is waiting for listing *serial*. UI thread."""
        return generation == self._tree_generation and item.data(0, LISTING_ROLE) == serial

    def _listing_done(self, parent_item: QTreeWidgetItem, generation: int, serial: int, rows) -> None:
        """Fill *parent_item* with its listing, unless it has moved on. UI thread."""
        if not self._is_waiting_for(parent_item, generation, serial):
            return
        parent_item.takeChildren()
        path = parent_item.text(3)
        for name, entry in rows:
            self._add_entry_row(parent_item, path, name, entry)

    def _listing_failed(self, parent_item: QTreeWidgetItem, generation: int, serial: int,
                        message: str) -> None:
        """Say why *parent_item* could not be listed, unless it has moved on. UI thread."""
        if not self._is_waiting_for(parent_item, generation, serial):
            return
        parent_item.takeChildren()
        QMessageBox.critical(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_list_error"),
            as_text(f"{self.word_dict.get('ssh_file_viewer_dialog_message_list_failed')} "
                    f"'{parent_item.text(3)}': {message}"))

    def _add_entry_row(self, parent_item: QTreeWidgetItem, path: str, name: str, entry) -> None:
        full_path = remote_join(path, name)
        typ = "dir" if stat.S_ISDIR(entry.st_mode) else "file"
        size = entry.st_size if typ == "file" else 0
        child = self.make_item(name, typ, size, full_path)
        parent_item.addChild(child)
        if typ == "dir":
            self.add_placeholder(child)

    def on_context_menu(self, pos):
        """
        Show context menu for file operations.
        顯示右鍵選單以進行檔案操作。
        """
        item = self.tree.itemAt(pos)
        if item is not None and not item.text(3):
            # The "..." or loading row: no entry of its own, so the folder it is in
            item = item.parent()
        menu = QMenu(self)
        handlers = {}
        for name, handler in (
                ("refresh", self.action_refresh),
                ("create_folder", self.action_create_folder),
                ("rename", self.action_rename),
                ("delete", self.action_delete),
                ("download", self.action_download),
                ("upload", self.action_upload),
        ):
            handlers[menu.addAction(self.word_dict.get(f"ssh_file_viewer_context_menu_action_{name}"))] = handler
        if self._transfer is not None and self._transfer.isRunning():
            menu.addSeparator()
            cancel = menu.addAction(self.word_dict.get("ssh_file_viewer_context_menu_action_cancel_transfer"))
            handlers[cancel] = self.action_cancel_transfer

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        handler = handlers.get(chosen)
        if handler is None:
            return
        try:
            handler(item)
        # what an SFTP operation raises, a closed session's RuntimeError included
        except CONNECT_ERRORS as e:
            self._operation_failed(str(e))

    def action_refresh(self, item: QTreeWidgetItem | None):
        """
        Refresh current item children (or root).
        重新整理目前項目的子項（或根）。
        """
        target = item or (self.tree.topLevelItem(0) if self.tree.topLevelItemCount() else None)
        if target is None:
            return
        # Clear and reload
        target.takeChildren()
        if is_folder(target):
            self.add_placeholder(target)
            self.on_item_expanded(target)

    def action_create_folder(self, item: QTreeWidgetItem | None):
        """
        Create a subfolder under the selected directory.
        在選定目錄下建立子資料夾。
        """
        if item is None:
            QMessageBox.information(
                self,
                self.word_dict.get("ssh_file_viewer_dialog_title_no_selection"),
                self.word_dict.get("ssh_file_viewer_dialog_message_select_folder_to_create"))
            return
        base_path = item.text(3)
        if not is_folder(item):
            base_path = posixpath.dirname(base_path)
        name, ok = self.get_text(
            self.word_dict.get("ssh_file_viewer_dialog_title_create_folder"),
            self.word_dict.get("ssh_file_viewer_dialog_label_folder_name"))
        if not ok or not name.strip():
            return
        name = self._checked_name(name)
        if name is None:
            return
        new_path = remote_join(base_path, name)
        # The folder it went into: refreshing a file item did nothing
        self._in_background(
            lambda: self.client.mkdir(new_path), lambda: self.action_refresh(folder_item(item)))

    def _in_background(self, call: Callable[[], None], after: Callable[[], None]) -> None:
        """Run *call* on an ``SftpCallThread``; then *after*, unless the tree was cleared meanwhile.

        A failure is shown like the menu's other failures. UI thread.
        """
        generation = self._tree_generation
        thread = SftpCallThread(call)
        thread.done.connect(lambda: after() if generation == self._tree_generation else None)
        thread.failed.connect(self._operation_failed)
        thread.finished.connect(self._forget_worker)
        self._calls.add(thread)
        thread.start()

    def _forget_worker(self) -> None:
        """Let go of the listing or call that just finished. UI thread.

        A bound method: a lambda holding the worker, on the worker, kept it,
        and through its other slots this tree, alive after the tree closed.
        """
        worker = self.sender()
        if isinstance(worker, QThread):
            # finished is emitted just before the thread ends; freed while it
            # still runs, Qt would abort
            worker.wait()
            self._listings.discard(worker)
            self._calls.discard(worker)

    def _operation_failed(self, message: str) -> None:
        """Say that a menu request failed, and why. UI thread."""
        QMessageBox.critical(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_operation_failed"),
            as_text(f"{self.word_dict.get('ssh_file_viewer_dialog_message_operation_failed')}: {message}"))

    def _checked_name(self, text: str) -> str | None:
        """*text* as one entry's name, or ``None`` after saying why it cannot be."""
        name = plain_remote_name(text)
        if name is None:
            QMessageBox.warning(
                self,
                self.word_dict.get("ssh_file_viewer_dialog_title_operation_failed"),
                self.word_dict.get("ssh_file_viewer_dialog_message_bad_name"))
        return name

    def action_rename(self, item: QTreeWidgetItem | None):
        """
        Rename selected item.
        重新命名選定項目。
        """
        if item is None:
            return
        old_path = item.text(3)
        new_name, ok = self.get_text(
            self.word_dict.get("ssh_file_viewer_dialog_title_rename"),
            f"{self.word_dict.get('ssh_file_viewer_dialog_label_new_name_for_item')}: {item.text(0)}",
            item.text(0))
        if not ok or not new_name.strip() or new_name.strip() == item.text(0):
            return
        new_name = self._checked_name(new_name)
        if new_name is None:
            return
        base = posixpath.dirname(old_path) or "/"
        new_path = remote_join(base, new_name)
        self._in_background(
            lambda: self.client.rename(old_path, new_path),
            lambda: self._renamed(item, new_name, new_path))

    def _renamed(self, item: QTreeWidgetItem, new_name: str, new_path: str) -> None:
        """Show *item* under its new name once the server has renamed it. UI thread."""
        item.setText(0, new_name)
        item.setText(3, new_path)
        if is_folder(item) and item.childCount() and not self.is_placeholder_present(item):
            # Its loaded children still carried the old path, and a download,
            # delete or rename of one went there: list them again
            self.action_refresh(item)

    def action_delete(self, item: QTreeWidgetItem | None):
        """
        Delete selected file/folder (folder must be empty).
        刪除選定檔案/資料夾（資料夾需為空）。
        """
        if item is None:
            return
        path = item.text(3)
        reply = QMessageBox.question(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_confirm_delete"),
            as_text(f"{self.word_dict.get('ssh_file_viewer_dialog_message_confirm_delete')} '{path}'?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        remove = self._remove_folder if is_folder(item) else self.client.remove_file
        self._in_background(lambda: remove(path), lambda: self._removed(item))

    def _remove_folder(self, path: str) -> None:
        """Remove the folder at *path*, saying why when it cannot be. Worker thread.

        SFTP removes only an empty folder, and OpenSSH refuses any other with
        a bare "Failure", which was all the message said.
        """
        try:
            self.client.remove_dir(path)
        except OSError as error:
            raise OSError(self.word_dict.get(
                "ssh_file_viewer_message_folder_not_removed").format(error=error)) from error

    def _removed(self, item: QTreeWidgetItem) -> None:
        """Take *item* out of the tree once the server has removed it. UI thread."""
        parent = item.parent()
        if parent:
            parent.removeChild(item)
        else:
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))

    def action_download(self, item: QTreeWidgetItem | None):
        """
        Download selected file to local.
        將選定檔案下載至本地。
        """
        if item is None or not is_file(item):
            QMessageBox.information(
                self,
                self.word_dict.get("ssh_file_viewer_dialog_title_invalid_selection"),
                self.word_dict.get("ssh_file_viewer_dialog_message_select_file_to_download"))
            return
        remote_path = item.text(3)
        suggested = local_file_name(remote_path)
        local_path, _ = QFileDialog.getSaveFileName(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_save_as"),
            suggested)
        if not local_path:
            return
        self._start_transfer(
            downloading=True, remote_path=remote_path, local_path=local_path,
            title=self.word_dict.get("ssh_file_viewer_dialog_title_downloaded"),
            message=self.word_dict.get("ssh_file_viewer_dialog_message_saved_to"))

    def action_upload(self, item: QTreeWidgetItem | None):
        """
        Upload a local file into the selected folder.
        將本地檔案上傳至所選資料夾。
        """
        if item is None:
            return
        target_dir = item.text(3) if is_folder(item) else posixpath.dirname(item.text(3))
        local_path, _ = QFileDialog.getOpenFileName(
            self, self.word_dict.get("ssh_file_viewer_dialog_title_select_local_file"), "")
        if not local_path:
            return
        filename = os.path.basename(local_path)  # local path: OS-native separator is correct
        remote_path = remote_join(target_dir, filename)
        self._start_transfer(
            downloading=False, remote_path=remote_path, local_path=local_path,
            title=self.word_dict.get("ssh_file_viewer_dialog_title_uploaded"),
            message=self.word_dict.get("ssh_file_viewer_dialog_message_uploaded_to"),
            # The folder only holds the new file once the upload is done.
            after=lambda: self.action_refresh(folder_item(item)))

    def _start_transfer(self, *, downloading: bool, remote_path: str, local_path: str,
                        title: str, message: str, after=None, replace: bool = False) -> bool:
        """Start one transfer in the background, unless one is already going.

        :param downloading: download when true, upload when false
        :param remote_path: the path on the server
        :param local_path: the path on this machine
        :param title: the title of the message shown when it is done
        :param message: what that message says, before the path it ended at
        :param after: what to do once it is done, on the UI thread
        :param replace: upload over a file already there; otherwise the user is asked first
        :return: whether it started
        """
        if self._refused_while_transferring():
            return False
        self._transfer = SftpTransferThread(self.client, downloading, remote_path, local_path, replace)
        self._transfer.done.connect(
            lambda path: self._transfer_done(title, message, path, after))
        self._transfer.failed.connect(self._transfer_failed)
        self._transfer.cancelled.connect(self._transfer_cancelled)
        self._transfer.finished.connect(self._forget_transfer)
        self._transfer.exists.connect(lambda path: self._ask_to_replace(path, lambda: self._start_transfer(
            downloading=False, remote_path=remote_path, local_path=local_path,
            title=title, message=message, after=after, replace=True)))
        self._transfer.start()
        return True

    def action_cancel_transfer(self, _item: QTreeWidgetItem | None = None) -> None:
        """Cancel the transfer in flight; the file it was writing is removed, the old copy kept."""
        if self._transfer is not None and self._transfer.isRunning():
            self._transfer.cancel()

    def _transfer_cancelled(self) -> None:
        """Say the transfer was cancelled and nothing was replaced. UI thread."""
        QMessageBox.information(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_transfer_cancelled"),
            self.word_dict.get("ssh_file_viewer_message_transfer_cancelled"))

    def _forget_transfer(self) -> None:
        """Let go of the transfer that just finished. UI thread.

        Its slots hold this tree (and the follow-up it was given): kept after
        it ended, it kept the closed tree alive.
        """
        transfer = self.sender()
        if isinstance(transfer, QThread) and transfer is self._transfer:
            # finished is emitted just before the thread ends; freed while it
            # still runs, Qt would abort
            transfer.wait()
            self._transfer = None

    def _refused_while_transferring(self) -> bool:
        """Say a transfer is going and return ``True`` if one is; ``False`` otherwise. UI thread."""
        if self._transfer is None or not self._transfer.isRunning():
            return False
        QMessageBox.information(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_transfer_running"),
            self.word_dict.get("ssh_file_viewer_dialog_message_transfer_running"))
        return True

    def _ask_to_replace(self, remote_path: str, replace: Callable[[], object]) -> None:
        """Ask whether an upload may replace *remote_path*, and call *replace* if so. UI thread."""
        answer = QMessageBox.question(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_confirm_replace"),
            as_text(self.word_dict.get("ssh_file_viewer_dialog_message_confirm_replace").format(path=remote_path)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            # The asking transfer has sent nothing and is only returning; the
            # new one must not find it still running
            if self._transfer is not None:
                self._transfer.wait(UPLOAD_ASKED_WAIT_MS)
            replace()

    def _transfer_done(self, title: str, message: str, path: str, after=None) -> None:
        """Say where the file ended up, and do whatever was waiting on it. UI thread."""
        QMessageBox.information(self, title, as_text(f"{message}: {path}"))
        if after is not None:
            after()

    def _transfer_failed(self, error_message: str) -> None:
        """Say why the transfer did not finish. UI thread."""
        QMessageBox.critical(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_operation_failed"),
            as_text(f"{self.word_dict.get('ssh_file_viewer_dialog_message_operation_failed')}: "
                    f"{error_message}"))

    def get_text(self, title: str, label: str, text: str = ""):
        """
        Ask for one line of text, starting from *text*; ``(text, ok)`` as ``QInputDialog.getText`` gives it.
        詢問一行文字。
        """
        answer, ok = QInputDialog.getText(self, title, label, QLineEdit.EchoMode.Normal, text)
        return answer, ok

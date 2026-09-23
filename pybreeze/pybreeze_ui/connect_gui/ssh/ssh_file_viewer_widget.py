from __future__ import annotations

import os
import posixpath
import re
import stat
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress

import paramiko
from PySide6.QtCore import Qt, QEvent, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
    QMenu, QFileDialog, QMessageBox, QSplitter, QInputDialog, QStyle
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_connect_thread import (
    CONNECT_ERRORS, SHA1_ALGORITHMS, SshConnectThread
)
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_host_key_policy import (
    apply_host_key_policy, host_key_asker
)
from pybreeze.pybreeze_ui.thread_keeper import let_run_out
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import load_private_key
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_login_widget import LoginWidget
from pybreeze.utils.logging.logger import pybreeze_logger


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


# Keepalive interval (seconds) so an idle SFTP session is not dropped by the
# TCP stack, a NAT/firewall, or the SSH server (≈ OpenSSH ServerAliveInterval).
SSH_KEEPALIVE_SECONDS = 30
# How long a menu action on the UI thread waits for the session before
# saying it is busy: long enough for a listing, short enough not to freeze
UI_WAIT_SECONDS = 1.0


def natural_key(name: str) -> list:
    """Sort key giving natural (human) order, e.g. ``img2`` before ``img10``.

    Embedded digit runs compare as integers and text compares case-insensitively,
    matching how Windows Explorer and most file managers order file listings.
    """
    # isdecimal (not isdigit): a part like "²³" or "①" is isdigit() but int()
    # rejects it, which would crash sorting a file named with such characters.
    return [
        int(part) if part.isdecimal() else part.lower()
        for part in re.split(r"(\d+)", name)
    ]


# Item data: the serial of the listing a directory item is waiting for
LISTING_ROLE = Qt.ItemDataRole.UserRole


def sort_entries(entries) -> list:
    """Return ``[(name, entry)]`` with directories first, each in natural order."""
    dirs: list = []
    files: list = []
    for entry in entries:
        bucket = dirs if stat.S_ISDIR(entry.st_mode) else files
        bucket.append((entry.filename, entry))
    dirs.sort(key=lambda item: natural_key(item[0]))
    files.sort(key=lambda item: natural_key(item[0]))
    return dirs + files


def remote_join(directory: str, name: str) -> str:
    """Join *name* under a remote POSIX *directory* into an absolute path.

    Remote SFTP paths are always POSIX: ``os.path.join`` would emit ``\\`` on a
    Windows client and break navigation/transfers on the server. The result
    always uses ``/`` separators and has a leading slash.
    """
    base = "" if directory == "/" else directory
    joined = posixpath.join(base, name)
    return joined if joined.startswith("/") else f"/{joined}"


class SftpBusy(RuntimeError):
    """Another request holds the SFTP session (a transfer, a listing); try again after it."""


class ConnectAbandoned(RuntimeError):
    """The session came up after the connect was given up on, and was closed."""


class SFTPClientWrapper:
    """
    Lightweight wrapper around Paramiko SFTP client.
    輕量級封裝 Paramiko SFTP 客戶端，提供基本操作。
    """

    def __init__(self):
        self.word_dict = language_wrapper.language_word_dict
        self._ssh: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None
        self.root_path: str = "/"
        # One request at a time on the session: paramiko's SFTP client throws
        # away a reply read by the wrong thread, and the thread that sent that
        # request then waits for it forever. Listings, a transfer and the menu's
        # own calls used to share it freely.
        self._in_use = threading.Lock()

    def connect(self, host: str, port: int, username: str, password: str,
                use_key: bool = False, key_path: str = "",
                parent_widget: QWidget | None = None):
        """
        Establish SSH + SFTP connection.
        建立 SSH + SFTP 連線。

        Runs on the connect thread while ``close()`` may run on the UI thread
        (Disconnect, or the tab closing). The session is kept only if it is
        still this connect's when it is up; otherwise it is closed and
        ``ConnectAbandoned`` raised. Closing during the TCP connect cannot stop
        it, and the session it went on to log in used to stay open, unseen,
        until the IDE exited.
        """
        self.close()
        ssh = paramiko.SSHClient()
        self._ssh = ssh
        apply_host_key_policy(ssh, parent_widget)
        pybreeze_logger.info("SFTP connecting to %s:%s", host, port)
        try:
            self._log_in(ssh, host, port, username, password, use_key, key_path)
            transport = ssh.get_transport()
            if transport is not None:
                transport.set_keepalive(SSH_KEEPALIVE_SECONDS)
            sftp = ssh.open_sftp()
            if self._ssh is not ssh:
                raise ConnectAbandoned("SFTP connect abandoned")
            self._sftp = sftp
        except Exception:
            # A failure partway (auth, keepalive, or open_sftp) must not leak the
            # half-open SSH transport: tear it down so connect() is all-or-nothing.
            # Only this connect's own: a newer one may be under way by now.
            ssh.close()
            if self._ssh is ssh:
                self._ssh = None
            raise

    def _log_in(self, ssh: paramiko.SSHClient, host: str, port: int, username: str,
                password: str, use_key: bool, key_path: str) -> None:
        """Connect *ssh* with the key file, or the password when no key is used."""
        if not (use_key and key_path):
            ssh.connect(hostname=host, port=port, username=username, password=password,
                        timeout=10, disabled_algorithms=SHA1_ALGORITHMS)
            return
        pkey = load_private_key(key_path, password, context="SFTP")
        if pkey is None:
            raise ValueError(
                self.word_dict.get("ssh_command_widget_error_message_unsupported_private_key")
            )
        ssh.connect(hostname=host, port=port, username=username, pkey=pkey, timeout=10,
                    disabled_algorithms=SHA1_ALGORITHMS)

    def close(self):
        """
        Close SFTP and SSH safely.
        安全關閉 SFTP 與 SSH。
        """
        try:
            if self._sftp:
                self._sftp.close()
        finally:
            self._sftp = None
        try:
            if self._ssh:
                self._ssh.close()
        finally:
            self._ssh = None

    @property
    def connected(self) -> bool:
        """
        Check connection state.
        檢查連線狀態。
        """
        return self._ssh is not None and self._sftp is not None

    def _require_connection(self) -> None:
        """Raise unless a session is open.

        Every call below goes through this: without it an operation on a stale
        tree (a dropped session, a closed connection) reaches ``None`` and the
        tree's error box shows the user an ``AttributeError`` about ``NoneType``.
        """
        if not self.connected:
            raise RuntimeError(
                self.word_dict.get("ssh_command_widget_dialog_title_not_connected")
            )

    @contextmanager
    def _session(self, wait: float | None = None) -> Iterator[paramiko.SFTPClient]:
        """Hold the session for one request and yield it, open.

        :param wait: seconds to wait for a request already running; ``None``
            waits as long as it takes (worker threads). The menu's calls run on
            the UI thread and wait briefly: a transfer can hold the session for
            minutes, and they are refused with ``SftpBusy`` instead.
        """
        acquired = self._in_use.acquire() if wait is None else self._in_use.acquire(timeout=wait)
        if not acquired:
            raise SftpBusy(self.word_dict.get("ssh_file_viewer_message_session_busy"))
        try:
            self._require_connection()
            sftp = self._sftp
            if sftp is None:  # closed from the UI thread since the check
                self._require_connection()
            yield sftp
        finally:
            self._in_use.release()

    def list_dir(self, path: str):
        """
        List directory entries with stat attributes. Worker thread.
        列出目錄項目（含屬性）。
        """
        with self._session() as sftp:
            return sftp.listdir_attr(path)

    def mkdir(self, path: str):
        """
        Create directory.
        建立目錄。
        """
        with self._session(UI_WAIT_SECONDS) as sftp:
            sftp.mkdir(path)

    def remove_file(self, path: str):
        """
        Remove file.
        刪除檔案。
        """
        with self._session(UI_WAIT_SECONDS) as sftp:
            sftp.remove(path)

    def remove_dir(self, path: str):
        """
        Remove empty directory.
        刪除空目錄。
        """
        with self._session(UI_WAIT_SECONDS) as sftp:
            sftp.rmdir(path)

    def rename(self, old_path: str, new_path: str):
        """
        Rename file/folder.
        重新命名檔案/資料夾。
        """
        with self._session(UI_WAIT_SECONDS) as sftp:
            sftp.rename(old_path, new_path)

    def download(self, remote_path: str, local_path: str):
        """
        Download remote to local. Worker thread.
        下載遠端檔案至本地。

        The file arrives beside *local_path* under a temporary name and takes
        its place only when complete: ``get`` empties its target before the
        first byte, so a dropped link or a Disconnect used to leave the file
        the user chose to replace cut short.
        """
        self._require_connection()
        folder = os.path.dirname(os.path.abspath(local_path))
        handle, partial = tempfile.mkstemp(
            prefix=f".{os.path.basename(local_path)}.", suffix=".part", dir=folder)
        os.close(handle)
        complete = False
        try:
            with self._session() as sftp:
                sftp.get(remote_path, partial)
            os.replace(partial, local_path)
            complete = True
        finally:
            if not complete:
                with suppress(OSError):
                    os.remove(partial)

    def upload(self, local_path: str, remote_path: str):
        """
        Upload local to remote. Worker thread.
        上傳本地檔案至遠端。
        """
        with self._session() as sftp:
            sftp.put(local_path, remote_path)


class SftpTransferThread(QThread):
    """One SFTP transfer, off the UI thread.

    A transfer has no timeout of its own, and a file can be any size: run in the
    button's slot, a download over a stalled link holds every tab, every run
    window and the editor itself until it finishes. Only the two signals reach
    the UI, and only one transfer runs at a time -- a paramiko SFTP session is
    not meant to be used from two places at once.
    """

    done = Signal(str)
    failed = Signal(str)

    def __init__(self, client: "SFTPClientWrapper", downloading: bool,
                 remote_path: str, local_path: str) -> None:
        super().__init__()
        self._client = client
        self._downloading = downloading
        self._remote_path = remote_path
        self._local_path = local_path

    def run(self) -> None:
        try:
            if self._downloading:
                self._client.download(self._remote_path, self._local_path)
            else:
                self._client.upload(self._local_path, self._remote_path)
        except (OSError, RuntimeError, paramiko.SSHException) as error:
            self.failed.emit(str(error))
        else:
            self.done.emit(self._local_path if self._downloading else self._remote_path)


class SftpListThread(QThread):
    """List one remote directory off the UI thread, sorted for the tree.

    ``listdir_attr()`` has no timeout of its own and returns every entry at
    once, so a stalled server or a directory of tens of thousands of files
    used to hold the IDE until it answered.
    """

    listed = Signal(object)  # [(name, SFTPAttributes)], directories first
    failed = Signal(str)

    def __init__(self, client: "SFTPClientWrapper", path: str) -> None:
        super().__init__()
        self._client = client
        self._path = path

    def run(self) -> None:
        try:
            entries = self._client.list_dir(self._path)
        except (OSError, RuntimeError, EOFError, paramiko.SSHException) as error:
            self.failed.emit(str(error))
        else:
            self.listed.emit(sort_entries(entries))


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
        self.tree.setHeaderLabels(["Name", "Type", "Size", "Path"])
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
            f"{self.word_dict.get('ssh_file_viewer_dialog_message_connection_failed')}: {message}")
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
            let_run_out(transfer, transfer.done, transfer.failed)
            transfer.finished.connect(self.client.close)
        for listing in list(self._listings):
            if listing.isRunning():
                let_run_out(listing, listing.listed, listing.failed)
        self._listings.clear()
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
        item = QTreeWidgetItem([name, typ, size_text, full_path])
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
        item.addChild(placeholder)

    def is_placeholder_present(self, item: QTreeWidgetItem) -> bool:
        """
        Check if the first child is a placeholder.
        檢查第一個子項是否為占位項。
        """
        if item.childCount() == 0:
            return False
        return item.child(0).text(0) == "..."

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
        listing.finished.connect(lambda: self._listings.discard(listing))
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
            f"{self.word_dict.get('ssh_file_viewer_dialog_message_list_failed')} "
            f"'{parent_item.text(3)}': {message}")

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
        menu = QMenu(self)

        refresh_act = menu.addAction("Refresh")
        create_act = menu.addAction("Create folder")
        rename_act = menu.addAction("Rename")
        delete_act = menu.addAction("Delete")
        download_act = menu.addAction("Download")
        upload_act = menu.addAction("Upload to this folder")

        action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
        if action is None:
            return

        try:
            if action == refresh_act:
                self.action_refresh(item)
            elif action == create_act:
                self.action_create_folder(item)
            elif action == rename_act:
                self.action_rename(item)
            elif action == delete_act:
                self.action_delete(item)
            elif action == download_act:
                self.action_download(item)
            elif action == upload_act:
                self.action_upload(item)
        # what an SFTP operation raises, a closed session's RuntimeError included
        except CONNECT_ERRORS as e:
            QMessageBox.critical(
                self,
                self.word_dict.get("ssh_file_viewer_dialog_title_operation_failed"),
                f"{self.word_dict.get('ssh_file_viewer_dialog_message_operation_failed')}: {e}")

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
        if target.text(1) == "dir":
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
        if item.text(1) != "dir":
            base_path = posixpath.dirname(base_path)
        name, ok = self.get_text(
            self.word_dict.get("ssh_file_viewer_dialog_title_create_folder"),
            self.word_dict.get("ssh_file_viewer_dialog_label_folder_name"))
        if not ok or not name.strip():
            return
        new_path = remote_join(base_path, name.strip())
        self.client.mkdir(new_path)
        self.action_refresh(item)

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
            f"{self.word_dict.get('ssh_file_viewer_dialog_label_new_name_for_item')}: {item.text(0)}")
        if not ok or not new_name.strip():
            return
        base = posixpath.dirname(old_path) or "/"
        new_path = remote_join(base, new_name.strip())
        self.client.rename(old_path, new_path)
        # Update item display
        item.setText(0, new_name.strip())
        item.setText(3, new_path)

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
            f"{self.word_dict.get('ssh_file_viewer_dialog_message_confirm_delete')} '{path}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        # Try dir first; if fails, try file
        if item.text(1) == "dir":
            self.client.remove_dir(path)
        else:
            self.client.remove_file(path)
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
        if item is None or item.text(1) != "file":
            QMessageBox.information(
                self,
                self.word_dict.get("ssh_file_viewer_dialog_title_invalid_selection"),
                self.word_dict.get("ssh_file_viewer_dialog_message_select_file_to_download"))
            return
        remote_path = item.text(3)
        suggested = posixpath.basename(remote_path)  # remote path uses POSIX separators
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
        target_dir = item.text(3) if item.text(1) == "dir" else posixpath.dirname(item.text(3))
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
            after=lambda: self.action_refresh(item))

    def _start_transfer(self, *, downloading: bool, remote_path: str, local_path: str,
                        title: str, message: str, after=None) -> bool:
        """Start one transfer in the background, unless one is already going.

        :param downloading: download when true, upload when false
        :param remote_path: the path on the server
        :param local_path: the path on this machine
        :param title: the title of the message shown when it is done
        :param message: what that message says, before the path it ended at
        :param after: what to do once it is done, on the UI thread
        :return: whether it started
        """
        if self._transfer is not None and self._transfer.isRunning():
            QMessageBox.information(
                self,
                self.word_dict.get("ssh_file_viewer_dialog_title_transfer_running"),
                self.word_dict.get("ssh_file_viewer_dialog_message_transfer_running"))
            return False
        self._transfer = SftpTransferThread(self.client, downloading, remote_path, local_path)
        self._transfer.done.connect(
            lambda path: self._transfer_done(title, message, path, after))
        self._transfer.failed.connect(self._transfer_failed)
        self._transfer.start()
        return True

    def _transfer_done(self, title: str, message: str, path: str, after=None) -> None:
        """Say where the file ended up, and do whatever was waiting on it. UI thread."""
        QMessageBox.information(self, title, f"{message}: {path}")
        if after is not None:
            after()

    def _transfer_failed(self, error_message: str) -> None:
        """Say why the transfer did not finish. UI thread."""
        QMessageBox.critical(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_operation_failed"),
            f"{self.word_dict.get('ssh_file_viewer_dialog_message_operation_failed')}: "
            f"{error_message}")

    def get_text(self, title: str, label: str):
        """
        Simple input dialog using QMessageBox alternative.
        簡易文字輸入對話框（基於 QLineEdit）。
        """
        text, ok = QInputDialog.getText(self, title, label)
        return text, ok

    def eventFilter(self, obj, event):
        """
        Allow Enter to trigger OK in our improvised input dialog.
        允許在自製輸入框中使用 Enter 觸發確定。
        """
        if isinstance(obj, QLineEdit) and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                w = obj.window()
                for b in w.findChildren(QPushButton):
                    if b.text().lower() in (self.word_dict.get("ssh_file_viewer_dialog_button_ok"),):
                        b.click()
                        return True
        return super().eventFilter(obj, event)

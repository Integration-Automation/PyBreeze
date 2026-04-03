import os
from pathlib import Path

import paramiko
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
    QMenu, QFileDialog, QMessageBox, QSplitter, QInputDialog, QStyle
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_login_widget import LoginWidget


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

    def connect(self, host: str, port: int, username: str, password: str,
                use_key: bool = False, key_path: str = ""):
        """
        Establish SSH + SFTP connection.
        建立 SSH + SFTP 連線。
        """
        self.close()
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if use_key and key_path:
            pkey = None
            for KeyType in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey):
                try:
                    pkey = KeyType.from_private_key_file(key_path, password if password else None)
                    break
                except Exception:
                    continue
            if pkey is None:
                raise ValueError(
                    self.word_dict.get("ssh_command_widget_error_message_unsupported_private_key")
                )
            self._ssh.connect(hostname=host, port=port, username=username, pkey=pkey, timeout=10)
        else:
            self._ssh.connect(hostname=host, port=port, username=username, password=password, timeout=10)
        self._sftp = self._ssh.open_sftp()

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

    def list_dir(self, path: str):
        """
        List directory entries with stat attributes.
        列出目錄項目（含屬性）。
        """
        if not self.connected:
            raise RuntimeError(
                self.word_dict.get("ssh_command_widget_dialog_title_not_connected")
            )
        return self._sftp.listdir_attr(path)

    def is_dir(self, path: str) -> bool:
        """
        Determine if target path is a directory.
        判斷路徑是否為目錄。
        """
        if not self.connected:
            raise RuntimeError(self.word_dict.get(
                "ssh_command_widget_dialog_title_not_connected"
            ))
        try:
            st = self._sftp.stat(path)
            # S_ISDIR check via stat.S_ISDIR
            import stat
            return stat.S_ISDIR(st.st_mode)
        except OSError:
            return False

    def mkdir(self, path: str):
        """
        Create directory.
        建立目錄。
        """
        self._sftp.mkdir(path)

    def remove_file(self, path: str):
        """
        Remove file.
        刪除檔案。
        """
        self._sftp.remove(path)

    def remove_dir(self, path: str):
        """
        Remove empty directory.
        刪除空目錄。
        """
        self._sftp.rmdir(path)

    def rename(self, old_path: str, new_path: str):
        """
        Rename file/folder.
        重新命名檔案/資料夾。
        """
        self._sftp.rename(old_path, new_path)

    def download(self, remote_path: str, local_path: str):
        """
        Download remote to local.
        下載遠端檔案至本地。
        """
        self._sftp.get(remote_path, local_path)

    def upload(self, local_path: str, remote_path: str):
        """
        Upload local to remote.
        上傳本地檔案至遠端。
        """
        self._sftp.put(local_path, remote_path)


class SSHFileTreeManager(QWidget):
    """
    QWidget: connection form + tree + context menu.
    QWidget：連線表單 + 樹狀檔案管理 + 右鍵選單。
    """

    def __init__(self, external_login_widget: LoginWidget = None, add_login_widget: bool = True):
        super().__init__()
        self.word_dict = language_wrapper.language_word_dict
        self.setWindowTitle(
            self.word_dict.get("ssh_file_viewer_window_title_file_tree_manager")
        )
        self.add_login_widget = add_login_widget

        self.client = SFTPClientWrapper()

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
        try:
            self.client.connect(host, port, user, pwd, use_key, key_path)
            self.load_root("/")
        except Exception as e:
            QMessageBox.critical(
                self,
                self.word_dict.get("ssh_file_viewer_dialog_title_connection_failed"),
                f"{self.word_dict.get('ssh_file_viewer_dialog_message_connection_failed')}: {e}")

    def _disconnect(self):
        """
        Disconnect SSH.
        斷線 SSH。
        """
        self.client.close()
        self.tree.clear()

    def load_root(self, path: str = "/"):
        """
        Clear and load root items.
        清空並載入根項目。
        """
        self.tree.clear()
        root_item = self.make_item("/", "dir", 0, "/")
        # Add a placeholder child to show expandable icon
        self.add_placeholder(root_item)
        self.tree.addTopLevelItem(root_item)
        root_item.setExpanded(True)
        self.populate_children(root_item)

    def make_item(self, name: str, typ: str, size: int, full_path: str) -> QTreeWidgetItem:
        """
        Create a tree item with metadata.
        建立帶有中繼資料的樹狀項目。
        """
        item = QTreeWidgetItem([name, typ, str(size), full_path])
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
        try:
            entries = self.client.list_dir(path)
            # Sort: dirs first, then files
            import stat
            dirs = []
            files = []
            for e in entries:
                name = e.filename
                full_path = os.path.join(path if path != "/" else "", name)
                full_path = full_path if full_path.startswith("/") else f"/{full_path}"
                is_dir = stat.S_ISDIR(e.st_mode)
                if is_dir:
                    dirs.append((name, e))
                else:
                    files.append((name, e))
            for name, e in dirs + files:
                import stat as _stat
                full_path = os.path.join(path if path != "/" else "", name)
                full_path = full_path if full_path.startswith("/") else f"/{full_path}"
                typ = "dir" if _stat.S_ISDIR(e.st_mode) else "file"
                size = e.st_size if typ == "file" else 0
                child = self.make_item(name, typ, size, full_path)
                parent_item.addChild(child)
                if typ == "dir":
                    self.add_placeholder(child)
        except Exception as ex:
            QMessageBox.critical(
                self,
                self.word_dict.get("ssh_file_viewer_dialog_title_list_error"),
                f"{self.word_dict.get('ssh_file_viewer_dialog_message_list_failed')} '{path}': {ex}")

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
        except Exception as e:
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
            base_path = os.path.dirname(base_path)
        name, ok = self.get_text(
            self.word_dict.get("ssh_file_viewer_dialog_title_create_folder"),
            self.word_dict.get("ssh_file_viewer_dialog_label_folder_name"))
        if not ok or not name.strip():
            return
        new_path = os.path.join(base_path if base_path != "/" else "", name.strip())
        new_path = new_path if new_path.startswith("/") else f"/{new_path}"
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
        base = os.path.dirname(old_path) or "/"
        new_path = os.path.join(base if base != "/" else "", new_name.strip())
        new_path = new_path if new_path.startswith("/") else f"/{new_path}"
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
        suggested = Path(remote_path).name
        local_path, _ = QFileDialog.getSaveFileName(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_save_as"),
            suggested)
        if not local_path:
            return
        self.client.download(remote_path, local_path)
        QMessageBox.information(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_downloaded"),
            f"{self.word_dict.get('ssh_file_viewer_dialog_message_saved_to')}: {local_path}")

    def action_upload(self, item: QTreeWidgetItem | None):
        """
        Upload a local file into the selected folder.
        將本地檔案上傳至所選資料夾。
        """
        if item is None:
            return
        target_dir = item.text(3) if item.text(1) == "dir" else os.path.dirname(item.text(3))
        local_path, _ = QFileDialog.getOpenFileName(
            self, self.word_dict.get("ssh_file_viewer_dialog_title_select_local_file"), "")
        if not local_path:
            return
        filename = os.path.basename(local_path)
        remote_path = os.path.join(target_dir if target_dir != "/" else "", filename)
        remote_path = remote_path if remote_path.startswith("/") else f"/{remote_path}"
        self.client.upload(local_path, remote_path)
        QMessageBox.information(
            self,
            self.word_dict.get("ssh_file_viewer_dialog_title_uploaded"),
            f"{self.word_dict.get('ssh_file_viewer_dialog_message_uploaded_to')}: {remote_path}")
        # Refresh folder contents
        self.action_refresh(item)

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

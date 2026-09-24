from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QLineEdit, QSpinBox, QCheckBox, QPushButton, QFileDialog
)
from je_editor import language_wrapper


class LoginWidget(QWidget):
    """登入介面獨立 QWidget"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # UI 控制元件
        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.key_edit = QLineEdit()
        self.use_key_check = QCheckBox(language_wrapper.language_word_dict.get("ssh_login_widget_button_use_key_auth"))
        self.browse_key_btn = QPushButton(language_wrapper.language_word_dict.get("ssh_login_widget_button_browse_key"))
        self.connect_btn = QPushButton(language_wrapper.language_word_dict.get("ssh_login_widget_button_connect"))
        self.disconnect_btn = QPushButton(language_wrapper.language_word_dict.get("ssh_login_widget_button_disconnect"))
        self.status_label = QLabel(language_wrapper.language_word_dict.get("ssh_login_widget_status_disconnected"))
        # The password, or with key authentication the key's passphrase (see _name_the_secret)
        self.pass_label = QLabel()

        # 初始化 UI
        self._setup_ui()

    def _setup_ui(self):
        """建立登入介面 UI"""
        self.host_edit.setPlaceholderText(language_wrapper.language_word_dict.get("ssh_login_widget_placeholder_host"))
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        self.user_edit.setPlaceholderText(
            language_wrapper.language_word_dict.get("ssh_login_widget_placeholder_username"))
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._name_the_secret(False)
        self.use_key_check.toggled.connect(self._name_the_secret)
        self.key_edit.setPlaceholderText(
            language_wrapper.language_word_dict.get("ssh_login_widget_placeholder_private_key"))
        self.browse_key_btn.clicked.connect(self.choose_key_file)
        # Enter in any field connects, as in a login form
        for edit in (self.host_edit, self.user_edit, self.pass_edit, self.key_edit):
            edit.returnPressed.connect(self.connect_btn.click)

        # 佈局設計
        top = QHBoxLayout()
        top.addWidget(QLabel(language_wrapper.language_word_dict.get("ssh_login_widget_label_host")))
        top.addWidget(self.host_edit)
        top.addWidget(QLabel(language_wrapper.language_word_dict.get("ssh_login_widget_label_port")))
        top.addWidget(self.port_spin)
        top.addWidget(QLabel(language_wrapper.language_word_dict.get("ssh_login_widget_label_user")))
        top.addWidget(self.user_edit)

        auth = QHBoxLayout()
        auth.addWidget(self.use_key_check)
        auth.addWidget(QLabel(language_wrapper.language_word_dict.get("ssh_login_widget_label_key")))
        auth.addWidget(self.key_edit)
        auth.addWidget(self.browse_key_btn)
        auth.addWidget(self.pass_label)
        auth.addWidget(self.pass_edit)

        conn = QHBoxLayout()
        conn.addWidget(self.connect_btn)
        conn.addWidget(self.disconnect_btn)
        conn.addWidget(self.status_label)

        root = QVBoxLayout()
        root.addLayout(top)
        root.addLayout(auth)
        root.addLayout(conn)

        self.setLayout(root)

    def _name_the_secret(self, key_auth: bool) -> None:
        """Label the secret field for what it holds: the password, or with *key_auth* the key's passphrase."""
        word = language_wrapper.language_word_dict
        if key_auth:
            label, placeholder = "ssh_login_widget_label_passphrase", "ssh_login_widget_placeholder_passphrase"
        else:
            label, placeholder = "ssh_login_widget_label_password", "ssh_login_widget_placeholder_password"
        self.pass_label.setText(word.get(label))
        self.pass_edit.setPlaceholderText(word.get(placeholder))

    def choose_key_file(self) -> None:
        """Pick the private key file in a dialog, starting in ``~/.ssh``; it also ticks key authentication."""
        start = Path.home() / ".ssh"
        path, _ = QFileDialog.getOpenFileName(
            self, language_wrapper.language_word_dict.get("ssh_login_widget_dialog_title_choose_key"),
            str(start if start.is_dir() else Path.home()))
        if path:
            self.key_edit.setText(path)
            self.use_key_check.setChecked(True)

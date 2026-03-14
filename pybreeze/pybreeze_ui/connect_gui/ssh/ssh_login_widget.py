from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QLineEdit, QSpinBox, QCheckBox, QPushButton
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
        self.connect_btn = QPushButton(language_wrapper.language_word_dict.get("ssh_login_widget_button_connect"))
        self.disconnect_btn = QPushButton(language_wrapper.language_word_dict.get("ssh_login_widget_button_disconnect"))
        self.status_label = QLabel(language_wrapper.language_word_dict.get("ssh_login_widget_status_disconnected"))

        # 初始化 UI
        self._setup_ui()

    def _setup_ui(self):
        """建立登入介面 UI"""
        self.host_edit.setPlaceholderText(language_wrapper.language_word_dict.get("ssh_login_widget_placeholder_host"))
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        self.user_edit.setPlaceholderText(
            language_wrapper.language_word_dict.get("ssh_login_widget_placeholder_username"))
        self.pass_edit.setPlaceholderText(
            language_wrapper.language_word_dict.get("ssh_login_widget_placeholder_password"))
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText(
            language_wrapper.language_word_dict.get("ssh_login_widget_placeholder_private_key"))

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
        auth.addWidget(QLabel(language_wrapper.language_word_dict.get("ssh_login_widget_label_password")))
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

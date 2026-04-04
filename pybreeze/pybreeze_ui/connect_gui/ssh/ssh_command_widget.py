import os
import re

import paramiko
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QLineEdit, QPushButton,
    QPlainTextEdit, QHBoxLayout, QVBoxLayout,
    QMessageBox
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_login_widget import LoginWidget
from pybreeze.utils.logging.logger import pybreeze_logger

ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


class SSHReaderThread(QThread):
    data_received = Signal(bytes)
    closed = Signal(str)

    def __init__(self, chan: paramiko.Channel, parent=None):
        super().__init__(parent)
        self.chan = chan
        self._running = True
        self.word_dict = language_wrapper.language_word_dict

    def run(self):
        try:
            while self._running:
                if self.chan.recv_ready():
                    data = self.chan.recv(4096)
                    if data:
                        self.data_received.emit(data)

                if self.chan.recv_stderr_ready():
                    err = self.chan.recv_stderr(4096)
                    if err:
                        self.data_received.emit(err)

                if self.chan.closed or self.chan.exit_status_ready():
                    break

                self.msleep(10)
        except Exception as e:
            self.closed.emit(
                f"{self.word_dict.get('ssh_command_widget_error_message_reader_failed')} {e}")
        finally:
            self.closed.emit(
                self.word_dict.get("ssh_command_widget_log_message_reader_closed"))

    def stop(self):
        self._running = False


class SSHCommandWidget(QWidget):
    def __init__(self, external_login_widget: LoginWidget = None, add_login_widget: bool = True):
        super().__init__()
        self.word_dict = language_wrapper.language_word_dict
        self.setWindowTitle(
            self.word_dict.get("ssh_command_widget_window_title_ssh_command_widget"))

        self.add_login_widget = add_login_widget

        # SSH 相關物件
        self.ssh_client: paramiko.SSHClient | None = None
        self.shell_channel: paramiko.Channel | None = None
        self.reader_thread: SSHReaderThread | None = None

        if self.add_login_widget:
            # 使用獨立的登入介面
            self.login_widget = LoginWidget()
        else:
            if external_login_widget is None:
                external_login_widget = LoginWidget()
            self.login_widget = external_login_widget

        # 其他 UI 控制元件
        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.command_input_edit = QLineEdit()
        self.command_send_button = QPushButton(
            self.word_dict.get("ssh_command_widget_button_label_send_command"))

        self._setup_ui()
        self._bind_events()

    def _setup_ui(self):
        self.terminal.setReadOnly(True)
        self.terminal.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.command_input_edit.setPlaceholderText(
            self.word_dict.get("ssh_command_widget_input_placeholder_command_line")
        )

        terminal_panel = QVBoxLayout()
        terminal_panel.addWidget(self.terminal)

        command_input_bar = QHBoxLayout()
        command_input_bar.addWidget(self.command_input_edit)
        command_input_bar.addWidget(self.command_send_button)

        main_widget = QVBoxLayout()
        main_widget.addWidget(self.login_widget)  # 插入登入介面
        main_widget.addLayout(terminal_panel)
        main_widget.addLayout(command_input_bar)

        self.setLayout(main_widget)

    def _bind_events(self):
        # 綁定 LoginWidget 的按鈕
        self.login_widget.connect_btn.clicked.connect(self.connect_ssh)
        self.login_widget.disconnect_btn.clicked.connect(self.disconnect_ssh)

        # 綁定其他按鈕
        self.command_send_button.clicked.connect(self.send_command)
        self.command_input_edit.returnPressed.connect(self.send_command)

    def append_text(self, text: str):
        self.terminal.appendPlainText(text)

    def connect_ssh(self):
        host = self.login_widget.host_edit.text().strip()
        port = self.login_widget.port_spin.value()
        user = self.login_widget.user_edit.text().strip()
        use_key = self.login_widget.use_key_check.isChecked()
        key_path = self.login_widget.key_edit.text().strip()
        password = self.login_widget.pass_edit.text()

        if not host or not user:
            QMessageBox.warning(
                self,
                self.word_dict.get("ssh_command_widget_dialog_title_input_error"),
                self.word_dict.get(
                    "ssh_command_widget_dialog_message_input_error_host_user_required"))
            return

        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if use_key:
                if not os.path.exists(key_path):
                    QMessageBox.warning(
                        self,
                        self.word_dict.get("ssh_command_widget_dialog_title_key_error"),
                        self.word_dict.get("ssh_command_widget_dialog_message_key_file_not_exist"))
                    return
                try:
                    pkey = None
                    for KeyType in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey):
                        try:
                            pkey = KeyType.from_private_key_file(key_path, password if password else None)
                            break
                        except Exception as error:
                            pybreeze_logger.debug(f"SSH key type failed: {error}")
                            continue
                    if pkey is None:
                        raise ValueError(
                            self.word_dict.get(
                                "ssh_command_widget_error_message_unsupported_private_key"
                            ))
                    self.ssh_client.connect(hostname=host, port=port, username=user, pkey=pkey, timeout=10)
                except Exception as e:
                    raise RuntimeError(
                        f"{self.word_dict.get('ssh_command_widget_error_message_key_auth_failed')} {e}") from e
            else:
                self.ssh_client.connect(
                    hostname=host, port=port, username=user, password=password, timeout=10
                )

            self.shell_channel = self.ssh_client.invoke_shell(term='xterm', width=120, height=32)
            self.shell_channel.settimeout(0.0)
            self.reader_thread = SSHReaderThread(self.shell_channel)
            self.reader_thread.data_received.connect(self._on_data)
            self.reader_thread.closed.connect(self._on_closed)
            self.reader_thread.start()
            self.login_widget.status_label.setText(
                self.word_dict.get("ssh_command_widget_log_message_connected"))
            self.append_text(f"{self.word_dict.get('ssh_command_widget_log_message_connected')}"
                             f" {host}:{port} as {user}\n")
        except Exception as e:
            self.login_widget.status_label.setText(
                self.word_dict.get('ssh_command_widget_status_label_disconnected'))
            self.append_text(f"{self.word_dict.get('ssh_command_widget_log_message_error')} {e}\n")
            self._cleanup()

    def _on_data(self, data: bytes):
        try:
            text = data.decode("utf-8", errors="replace")
            clean_text = ANSI_ESCAPE_PATTERN.sub('', text)
            self.append_text(clean_text)
        except Exception as error:
            self.append_text(f"{self.word_dict.get('ssh_command_widget_error_message_decode_failed')}"
                             f" {error}\n")

    def _on_closed(self, msg: str):
        self.append_text(f"\n{self.word_dict.get('ssh_command_widget_log_message_channel_closed')}"
                         f" {msg}\n")
        self.login_widget.status_label.setText(self.word_dict.get(
            'ssh_command_widget_status_label_disconnected'
        ))

    def send_command(self):
        cmd = self.command_input_edit.text()
        if not cmd:
            return
        if self.shell_channel and not self.shell_channel.closed:
            try:
                self.shell_channel.send(cmd + "\n")
                self.command_input_edit.clear()
            except Exception as e:
                self.append_text(f"{self.word_dict.get('ssh_command_widget_error_message_send_failed')} {e}\n")
        else:
            QMessageBox.information(
                self,
                self.word_dict.get('ssh_command_widget_dialog_title_not_connected'),
                self.word_dict.get('ssh_command_widget_dialog_message_not_connected_shell'))

    def disconnect_ssh(self):
        self.append_text(f"{self.word_dict.get('ssh_command_widget_log_message_disconnect_in_progress')} \n")
        self._cleanup()
        self.login_widget.status_label.setText(
            self.word_dict.get('ssh_command_widget_status_label_disconnected'))

    def _cleanup(self):
        try:
            if self.reader_thread:
                self.reader_thread.stop()
                self.reader_thread.wait(1000)
        except Exception as error:
            pybreeze_logger.debug(f"SSH reader thread cleanup: {error}")
        self.reader_thread = None

        try:
            if self.shell_channel and not self.shell_channel.closed:
                self.shell_channel.close()
        except Exception as error:
            pybreeze_logger.debug(f"SSH channel cleanup: {error}")
        self.shell_channel = None

        try:
            if self.ssh_client:
                self.ssh_client.close()
        except Exception as error:
            pybreeze_logger.debug(f"SSH client cleanup: {error}")
        self.ssh_client = None

from __future__ import annotations

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

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_connect_thread import CONNECT_ERRORS, SshConnectThread
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_host_key_policy import (
    apply_host_key_policy, host_key_asker
)
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import load_private_key
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_login_widget import LoginWidget
from pybreeze.pybreeze_ui.thread_keeper import let_run_out
from pybreeze.utils.logging.logger import pybreeze_logger

ANSI_ESCAPE_PATTERN = re.compile(
    r'\x1B(?:'
    r'\][^\x07\x1B]*(?:\x07|\x1B\\)?'  # OSC; BEL/ST-terminated or implicitly ended by the next ESC / EOF
    r'|[@-Z\\-_]'                      # other two-character C1 Fe sequences
    r'|\[[0-?]*[ -/]*[@-~]'           # CSI (colours, cursor movement)
    r')'
)

# Bound the terminal scrollback so an endless stream (``tail -f``, ``yes``)
# cannot grow the document without limit; oldest lines drop once exceeded.
TERMINAL_MAX_BLOCKS = 10000

# Send a keepalive packet after this many idle seconds so an idle session is not
# dropped by the TCP stack, a NAT/firewall, or the SSH server (≈ OpenSSH's
# ServerAliveInterval).
SSH_KEEPALIVE_SECONDS = 30


class SSHReaderThread(QThread):
    data_received = Signal(bytes)
    closed = Signal(str)

    def __init__(self, chan: paramiko.Channel, parent=None):
        super().__init__(parent)
        self.chan = chan
        self._running = True
        self.word_dict = language_wrapper.language_word_dict

    def _pump_once(self) -> bool:
        """Forward any ready stdout/stderr; return False once the channel closes."""
        if self.chan.recv_ready():
            data = self.chan.recv(4096)
            if data:
                self.data_received.emit(data)
        if self.chan.recv_stderr_ready():
            err = self.chan.recv_stderr(4096)
            if err:
                self.data_received.emit(err)
        return not (self.chan.closed or self.chan.exit_status_ready())

    def run(self):
        error_msg = None
        try:
            while self._running and self._pump_once():
                self.msleep(10)
        except Exception as e:  # noqa: BLE001 — any reader failure must surface to the UI
            pybreeze_logger.debug("SSH reader thread error: %r", e)
            error_msg = f"{self.word_dict.get('ssh_command_widget_error_message_reader_failed')} {e}"
        finally:
            # Emit exactly once: the error when one occurred, otherwise the
            # normal close notice (previously the error path emitted twice).
            self.closed.emit(
                error_msg or self.word_dict.get("ssh_command_widget_log_message_reader_closed"))

    def stop(self):
        self._running = False


class SSHCommandWidget(QWidget):
    # Emitted when the session comes up or goes down, for the tab's status label
    state_changed = Signal()

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
        # The connect in progress, if any / 正在進行的連線
        self._connecting: SshConnectThread | None = None
        host_key_asker()  # built here, on the UI thread, for a connect to ask through

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
        self.terminal.setMaximumBlockCount(TERMINAL_MAX_BLOCKS)
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

        if self._connecting is not None and self._connecting.isRunning():
            return
        if use_key and not os.path.exists(key_path):
            QMessageBox.warning(
                self,
                self.word_dict.get("ssh_command_widget_dialog_title_key_error"),
                self.word_dict.get("ssh_command_widget_dialog_message_key_file_not_exist"))
            return

        # Tear down any prior session first: re-clicking Connect while already
        # connected would otherwise leak the old SSH client and orphan its
        # reader thread (which keeps appending to the terminal).
        self._cleanup()
        client = paramiko.SSHClient()
        self.ssh_client = client
        apply_host_key_policy(client, self)
        pybreeze_logger.info("SSH connecting to %s:%s", host, port)
        if use_key:
            def connect() -> None:
                self._connect_with_key(client, host, port, user, key_path, password)
        else:
            def connect() -> None:
                client.connect(
                    hostname=host, port=port, username=user, password=password, timeout=10)
        # The connect itself runs off the UI thread: an unreachable host used to
        # hold the IDE for the connect, banner and auth timeouts together.
        thread = SshConnectThread(connect)
        thread.connected.connect(lambda: self._on_connected(client, host, port, user))
        thread.failed.connect(lambda message: self._on_connect_failed(client, message))
        self._connecting = thread
        thread.start()

    def _connect_with_key(self, client: paramiko.SSHClient, host: str, port: int, user: str,
                          key_path: str, password: str) -> None:
        """Key-based auth, on the connecting thread. Raises what the connect raises."""
        try:
            pkey = load_private_key(key_path, password, context="SSH")
            if pkey is None:
                raise ValueError(
                    self.word_dict.get(
                        "ssh_command_widget_error_message_unsupported_private_key"
                    ))
            client.connect(hostname=host, port=port, username=user, pkey=pkey, timeout=10)
        except CONNECT_ERRORS as e:
            raise RuntimeError(
                f"{self.word_dict.get('ssh_command_widget_error_message_key_auth_failed')} {e}") from e

    def _on_connected(self, client: paramiko.SSHClient, host: str, port: int, user: str) -> None:
        """Open the shell once the connect has succeeded. UI thread."""
        if client is not self.ssh_client:
            client.close()  # disconnected, or reconnected, while it was connecting
            return
        try:
            self._start_shell(host, port, user)
        except CONNECT_ERRORS as error:
            self._on_connect_failed(client, str(error))
            return
        self.state_changed.emit()

    def _on_connect_failed(self, client: paramiko.SSHClient, message: str) -> None:
        """Say why the connect failed and drop the half-made session. UI thread."""
        if client is not self.ssh_client:
            return
        self.login_widget.status_label.setText(
            self.word_dict.get('ssh_command_widget_status_label_disconnected'))
        self.append_text(f"{self.word_dict.get('ssh_command_widget_log_message_error')} {message}\n")
        self._cleanup()
        self.state_changed.emit()

    def _start_shell(self, host: str, port: int, user: str) -> None:
        transport = self.ssh_client.get_transport()
        if transport is not None:
            transport.set_keepalive(SSH_KEEPALIVE_SECONDS)
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
        self.state_changed.emit()

    def is_connected(self) -> bool:
        """Whether a shell session is open here."""
        return self.shell_channel is not None and not self.shell_channel.closed

    def closeEvent(self, event) -> None:
        """End the session with the widget.

        The reader thread must not outlive it: Qt aborts the process when a
        running QThread is destroyed, and a queued signal from one lands in a
        widget that is already gone.
        """
        if self._connecting is not None and self._connecting.isRunning():
            let_run_out(self._connecting, self._connecting.connected, self._connecting.failed)
            # A connect that still succeeds after the tab has gone would leave its
            # session open: close it whatever way the thread ends. (After
            # let_run_out, which cuts off everything connected to ``finished``.)
            connecting_client = self.ssh_client
            if connecting_client is not None:
                self._connecting.finished.connect(connecting_client.close)
        self._cleanup()
        super().closeEvent(event)

    def _cleanup(self):
        try:
            if self.reader_thread:
                # Block the thread's signals before tearing down so a data/closed
                # signal emitted mid-shutdown can't land in a half-cleaned widget.
                self.reader_thread.blockSignals(True)
                self.reader_thread.stop()
                self.reader_thread.wait(1000)
        except Exception as error:
            pybreeze_logger.debug("SSH reader thread cleanup: %r", error)
        self.reader_thread = None

        try:
            if self.shell_channel and not self.shell_channel.closed:
                self.shell_channel.close()
        except Exception as error:
            pybreeze_logger.debug("SSH channel cleanup: %r", error)
        self.shell_channel = None

        try:
            if self.ssh_client:
                self.ssh_client.close()
        except Exception as error:
            pybreeze_logger.debug("SSH client cleanup: %r", error)
        self.ssh_client = None

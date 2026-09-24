from __future__ import annotations

import codecs
import os
import weakref

import paramiko
from PySide6.QtCore import QEvent, QThread, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QWidget, QLineEdit, QPushButton,
    QPlainTextEdit, QHBoxLayout, QVBoxLayout,
    QMessageBox
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_connect_thread import (
    CONNECT_ERRORS, SHA1_ALGORITHMS, SshConnectThread
)
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_host_key_policy import (
    apply_host_key_policy, host_key_asker
)
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import load_private_key, unloadable_key_reason
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_login_widget import LoginWidget
from pybreeze.pybreeze_ui.thread_keeper import if_alive, let_run_out
from pybreeze.pybreeze_ui.error_text import error_text
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.terminal_text import split_unfinished_end, strip_terminal_controls, take_leading_backspaces

# What closing a channel or a client can raise on a connection already broken
CLOSE_ERRORS = (OSError, EOFError, paramiko.SSHException)


class TerminalDecoder:
    """Turn what the shell sends into text to show, one read at a time.

    A read ends wherever the channel's buffer did, so it can stop inside a
    multi-byte UTF-8 character or inside an escape sequence. Decoding each read
    on its own showed the character as replacement marks and the escape's tail
    as text; this carries the unfinished part over to the next read.
    """

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._pending = ""

    def reset(self) -> None:
        """Forget anything carried over, for a new session."""
        self._decoder.reset()
        self._pending = ""

    def feed(self, data: bytes) -> str:
        """Return the text *data* completes, escape sequences removed.

        Backspaces it starts with are kept, for the view to take back what an
        earlier read showed; any others are applied here.
        """
        text, self._pending = split_unfinished_end(self._pending + self._decoder.decode(data))
        backspaces, text = take_leading_backspaces(text)
        return "\x08" * backspaces + strip_terminal_controls(text)


# Bound the terminal scrollback so an endless stream (``tail -f``, ``yes``)
# cannot grow the document without limit; oldest lines drop once exceeded.
TERMINAL_MAX_BLOCKS = 10000

# Send a keepalive packet after this many idle seconds so an idle session is not
# dropped by the TCP stack, a NAT/firewall, or the SSH server (≈ OpenSSH's
# ServerAliveInterval).
SSH_KEEPALIVE_SECONDS = 30


# What Ctrl+C sends in a terminal (ETX): the shell's line discipline turns it into SIGINT
INTERRUPT = b"\x03"

# Lines the command line remembers for Up and Down; the oldest go first
HISTORY_LIMIT = 500


class CommandHistory:
    """Lines sent from the command line, for Up and Down to bring back, as a shell does.

    Walking up from a line being typed keeps it: walking down past the newest
    line gives it back. A line sent twice in a row is remembered once.
    """

    def __init__(self, limit: int = HISTORY_LIMIT) -> None:
        self._lines: list[str] = []
        self._limit = limit
        self._index = 0  # len(self._lines): at the line being typed
        self._draft = ""

    def add(self, line: str) -> None:
        """Remember *line* (not an empty one) and go back to a new line."""
        if line and (not self._lines or self._lines[-1] != line):
            self._lines.append(line)
            del self._lines[:-self._limit]
        self._index = len(self._lines)
        self._draft = ""

    def older(self, current: str) -> str | None:
        """The line before the one shown, or ``None`` at the oldest. *current* is what is typed."""
        if self._index == 0:
            return None
        if self._index == len(self._lines):
            self._draft = current
        self._index -= 1
        return self._lines[self._index]

    def newer(self) -> str | None:
        """The line after the one shown, the draft after the newest, or ``None`` at the draft."""
        if self._index >= len(self._lines):
            return None
        self._index += 1
        return self._draft if self._index == len(self._lines) else self._lines[self._index]


# Longest a command waits for the server to take it (a full SSH window), on the UI thread
SEND_TIMEOUT_SECONDS = 5


def send_all(channel: paramiko.Channel, data: bytes) -> None:
    """Send every byte of *data*, waiting at most ``SEND_TIMEOUT_SECONDS`` for room.

    ``Channel.send`` sends what fits in one packet and the window and returns
    how much that was: a pasted command past about 32 KB lost its tail and its
    newline. A ``str`` was also counted in characters, not in the UTF-8 bytes
    that go out. The shell channel is otherwise non-blocking (its reader polls
    it), so it is blocking only for this send; a timeout raises ``OSError``.
    """
    channel.settimeout(SEND_TIMEOUT_SECONDS)
    try:
        channel.sendall(data)
    finally:
        channel.settimeout(0.0)


def open_shell_channel(client: paramiko.SSHClient) -> paramiko.Channel:
    """Open an interactive shell on *client*'s connection. Waits on the network: not the UI thread.

    The channel comes back non-blocking: its reader polls it.
    """
    transport = client.get_transport()
    if transport is not None:
        transport.set_keepalive(SSH_KEEPALIVE_SECONDS)
    channel = client.invoke_shell(term="xterm", width=120, height=32)
    channel.settimeout(0.0)
    return channel


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

    def _drain(self) -> None:
        """Forward what is still buffered once the shell has exited.

        The last output and the exit status can arrive together; stopping at
        the exit status dropped whatever did not fit in the final read.
        """
        while self._running and (self.chan.recv_ready() or self.chan.recv_stderr_ready()):
            self._pump_once()

    def run(self):
        error_msg = None
        try:
            while self._running and self._pump_once():
                self.msleep(10)
            self._drain()
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
        # What the shell sends, joined across reads / 跨次讀取的解碼狀態
        self._decoder = TerminalDecoder()
        # The connect in progress, if any / 正在進行的連線
        self._connecting: SshConnectThread | None = None
        # Lines sent, for Up and Down / 送出過的指令
        self._history = CommandHistory()
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
        self.interrupt_button = QPushButton(
            self.word_dict.get("ssh_command_widget_button_label_interrupt"))
        self.interrupt_button.setToolTip(self.word_dict.get("ssh_command_widget_tooltip_interrupt"))

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
        command_input_bar.addWidget(self.interrupt_button)

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
        self.interrupt_button.clicked.connect(self.send_interrupt)
        self.command_input_edit.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        """Keys the command line gives to the shell rather than to its own text."""
        if (watched is self.command_input_edit and event.type() == QEvent.Type.KeyPress
                and self._command_line_key(event.key(), event.modifiers())):
            return True
        return super().eventFilter(watched, event)

    def _command_line_key(self, key: int, modifiers) -> bool:
        """Act on *key* in the command line; return whether it was taken.

        Ctrl+C interrupts the shell, unless it copies a selection. Up and Down
        walk through the lines sent before.
        """
        if (key == Qt.Key.Key_C and modifiers == Qt.KeyboardModifier.ControlModifier
                and not self.command_input_edit.hasSelectedText()):
            self.send_interrupt()
            return True
        if modifiers & ~Qt.KeyboardModifier.KeypadModifier:
            return False
        if key == Qt.Key.Key_Up:
            line = self._history.older(self.command_input_edit.text())
        elif key == Qt.Key.Key_Down:
            line = self._history.newer()
        else:
            return False
        if line is not None:
            self.command_input_edit.setText(line)
        return True

    def append_text(self, text: str):
        """Add a notice of our own, starting on a line of its own."""
        end = QTextCursor(self.terminal.document())
        end.movePosition(QTextCursor.MoveOperation.End)
        self._insert_output(text if end.atBlockStart() else "\n" + text)

    def _insert_output(self, text: str) -> None:
        """Add *text* where the output ends, without starting a new line.

        ``appendPlainText`` starts a new paragraph on every call, so each read
        from the shell began on a line of its own, wherever the read happened
        to stop. The view follows the output only if it was already at the end.
        """
        scroll_bar = self.terminal.verticalScrollBar()
        following = scroll_bar.value() == scroll_bar.maximum()
        end = QTextCursor(self.terminal.document())
        end.movePosition(QTextCursor.MoveOperation.End)
        backspaces, text = take_leading_backspaces(text)
        if backspaces:
            # They take back what an earlier read showed, never past the line's start
            end.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor,
                             min(backspaces, end.positionInBlock()))
            end.removeSelectedText()
        end.insertText(text)
        if following:
            scroll_bar.setValue(scroll_bar.maximum())

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
        opened: dict = {}

        def connect() -> None:
            if use_key:
                self._connect_with_key(client, host, port, user, key_path, password)
            else:
                client.connect(
                    hostname=host, port=port, username=user, password=password, timeout=10,
                    disabled_algorithms=SHA1_ALGORITHMS)
            opened["channel"] = open_shell_channel(client)
        # The connect and the shell's channel are made off the UI thread: an
        # unreachable host used to hold the IDE for the connect, banner and auth
        # timeouts together, and a server gone quiet after auth held it while
        # the channel waited to open.
        thread = SshConnectThread(connect)
        # Weakly: this widget keeps the thread, so slots holding the widget
        # kept the closed and deleted widget alive with it
        me = weakref.ref(self)
        thread.connected.connect(lambda: if_alive(
            me, lambda widget: widget._on_connected(client, opened["channel"], host, port, user)))
        thread.failed.connect(lambda message: if_alive(
            me, lambda widget: widget._on_connect_failed(client, message)))
        self._connecting = thread
        thread.start()

    def _connect_with_key(self, client: paramiko.SSHClient, host: str, port: int, user: str,
                          key_path: str, password: str) -> None:
        """Key-based auth, on the connecting thread. Raises what the connect raises."""
        try:
            pkey = load_private_key(key_path, password, context="SSH")
            if pkey is None:
                raise ValueError(self.word_dict.get(unloadable_key_reason(key_path, password)))
            client.connect(hostname=host, port=port, username=user, pkey=pkey, timeout=10,
                           disabled_algorithms=SHA1_ALGORITHMS)
        except CONNECT_ERRORS as e:
            raise RuntimeError(
                f"{self.word_dict.get('ssh_command_widget_error_message_key_auth_failed')} {e}") from e

    def _on_connected(self, client: paramiko.SSHClient, channel: paramiko.Channel,
                      host: str, port: int, user: str) -> None:
        """Start reading the shell once it is open. UI thread."""
        if client is not self.ssh_client:
            client.close()  # disconnected, or reconnected, while it was connecting
            return
        self._start_shell(channel, host, port, user)
        self.state_changed.emit()

    def _on_connect_failed(self, client: paramiko.SSHClient, message: str) -> None:
        """Say why the connect failed and drop the half-made session. UI thread."""
        if client is not self.ssh_client:
            return
        self.login_widget.status_label.setText(
            self.word_dict.get('ssh_command_widget_status_label_disconnected'))
        self.append_text(f"{self.word_dict.get('ssh_command_widget_log_message_error')} {error_text(message)}\n")
        self._cleanup()
        self.state_changed.emit()

    def _start_shell(self, channel: paramiko.Channel, host: str, port: int, user: str) -> None:
        """Show *channel*'s output from now on. UI thread; nothing here waits on the network."""
        self.shell_channel = channel
        self._decoder.reset()
        self.reader_thread = SSHReaderThread(self.shell_channel)
        self.reader_thread.data_received.connect(self._on_data)
        self.reader_thread.closed.connect(self._on_closed)
        self.reader_thread.start()
        self.login_widget.status_label.setText(
            self.word_dict.get("ssh_command_widget_status_label_connected"))
        # An IPv6 address in brackets, or its port reads as one more group
        shown_host = f"[{host}]" if ":" in host else host
        self.append_text(self.word_dict.get("ssh_command_widget_log_message_connected").format(
            host=shown_host, port=port, user=user) + "\n")

    def _on_data(self, data: bytes):
        self._insert_output(self._decoder.feed(data))

    def _on_closed(self, msg: str):
        """The shell ended on the server's side (``exit``, a dropped link).

        The session goes with it, as for Disconnect: it used to stay open,
        sending keepalives, until the next Connect or the tab closing. And the
        status is reported through ``state_changed``, which the combined view
        turns into both halves' state; writing "disconnected" into the shared
        label hid a file tree that was still connected.
        """
        self.append_text(f"\n{self.word_dict.get('ssh_command_widget_log_message_channel_closed')}"
                         f" {msg}\n")
        self._cleanup()
        self.login_widget.status_label.setText(self.word_dict.get(
            'ssh_command_widget_status_label_disconnected'
        ))
        self.state_changed.emit()

    def send_command(self):
        """Send the typed line and a newline to the shell.

        An empty line is sent too, as Enter alone: a prompt's default
        (``[Y/n]``, "Press Enter to continue") is taken that way. Without a
        session it only asks to connect when something was typed.
        """
        cmd = self.command_input_edit.text()
        if self._has_shell():
            if self._send((cmd + "\n").encode("utf-8")):
                self._history.add(cmd)
                self.command_input_edit.clear()
        elif cmd:
            QMessageBox.information(
                self,
                self.word_dict.get('ssh_command_widget_dialog_title_not_connected'),
                self.word_dict.get('ssh_command_widget_dialog_message_not_connected_shell'))

    def send_interrupt(self) -> None:
        """Send Ctrl+C to the shell, which stops what runs in it (``ping``, ``tail -f``).

        What is typed in the command line stays. Without a session it does nothing.
        """
        if self._has_shell():
            self._send(INTERRUPT)

    def _has_shell(self) -> bool:
        return self.shell_channel is not None and not self.shell_channel.closed

    def _send(self, data: bytes) -> bool:
        """Send *data* to the shell; say so in the terminal and return False when it fails."""
        try:
            send_all(self.shell_channel, data)
        except (OSError, paramiko.SSHException) as e:
            self.append_text(f"{self.word_dict.get('ssh_command_widget_error_message_send_failed')} {e}\n")
            return False
        return True

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
        except RuntimeError as error:  # its C++ object already deleted
            pybreeze_logger.debug("SSH reader thread cleanup: %r", error)
        self.reader_thread = None

        try:
            if self.shell_channel and not self.shell_channel.closed:
                self.shell_channel.close()
        except CLOSE_ERRORS as error:
            pybreeze_logger.debug("SSH channel cleanup: %r", error)
        self.shell_channel = None

        try:
            if self.ssh_client:
                self.ssh_client.close()
        except CLOSE_ERRORS as error:
            pybreeze_logger.debug("SSH client cleanup: %r", error)
        self.ssh_client = None

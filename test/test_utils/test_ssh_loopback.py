"""The SFTP connect against a real SSH server on the loopback address.

The other SSH tests stub the network. ``requirements.txt`` does not pin
paramiko, so an install takes the latest (5.0 dropped SHA-1 and changed key
loading): this logs in the way the IDE does, with a password and with each kind
of key file, and lists a folder.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import socket
import stat
import threading

import paramiko
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_host_key_policy as policy_mod
from pybreeze.pybreeze_ui.connect_gui.ssh.sftp_session import SFTPClientWrapper

_USER = "tester"
_PASSWORD = "the password"
_PASSPHRASE = "the passphrase"
_ENTRY = "only_entry"
_OpenSSH = serialization.PrivateFormat.OpenSSH
_PKCS8 = serialization.PrivateFormat.PKCS8
_PEM = serialization.PrivateFormat.TraditionalOpenSSL

# What each key file is: (its private key, the format it is written in, whether it is encrypted)
_KEY_FILES = {
    "rsa_openssh_encrypted": (lambda: rsa.generate_private_key(65537, 2048), _OpenSSH, True),
    "ed25519_openssh": (ed25519.Ed25519PrivateKey.generate, _OpenSSH, False),
    "ecdsa_pem": (lambda: ec.generate_private_key(ec.SECP256R1()), _PEM, False),
    "rsa_pkcs8_encrypted": (lambda: rsa.generate_private_key(65537, 2048), _PKCS8, True),
}


def _echo_shell(channel: paramiko.Channel, events: list) -> None:
    """A shell that greets, answers each line with ``got: <line>``, and ends on ``exit``."""
    channel.sendall("welcome\r\n$ ".encode("utf-8"))
    received = b""
    while True:
        data = channel.recv(1024)
        if not data:
            return
        events.append(("received", data))
        received += data
        while b"\n" in received:
            line, received = received.split(b"\n", 1)
            text = line.decode("utf-8").replace("\x03", "")
            if text == "exit":
                channel.sendall(b"bye\r\n")
                channel.send_exit_status(0)
                channel.close()
                return
            channel.sendall(f"got: {text}\r\n$ ".encode("utf-8"))


class _Server(paramiko.ServerInterface):
    def __init__(self, public_keys: set[str], events: list | None = None) -> None:
        self.public_keys = public_keys
        self.events = events if events is not None else []

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        self.events.append(("pty", term, width, height))
        return True

    def check_channel_shell_request(self, channel):
        threading.Thread(target=_echo_shell, args=(channel, self.events), daemon=True).start()
        return True

    def check_channel_window_change_request(self, channel, width, height, pixelwidth, pixelheight):
        self.events.append(("resize", width, height))
        return True

    def check_auth_password(self, username, password):
        return paramiko.AUTH_SUCCESSFUL if (username, password) == (_USER, _PASSWORD) else paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        return paramiko.AUTH_SUCCESSFUL if key.get_base64() in self.public_keys else paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password,publickey"

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED


class _OneEntryFolder(paramiko.SFTPServerInterface):
    def list_folder(self, path):
        entry = paramiko.SFTPAttributes()
        entry.filename = _ENTRY
        entry.st_mode = stat.S_IFREG | 0o644
        entry.st_size = 0
        return [entry]


class _LoopbackServer:
    """Accepts SSH connections on 127.0.0.1 on its own thread until stopped."""

    def __init__(self, disabled_algorithms: dict | None = None) -> None:
        self.host_key = paramiko.RSAKey.generate(2048)
        self.public_keys: set[str] = set()
        self.events: list = []  # what the shells were asked: ("pty", ...), ("received", bytes), ("resize", ...)
        self._disabled_algorithms = disabled_algorithms
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        self._transports: list[paramiko.Transport] = []
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while True:
            try:
                connection, _address = self._listener.accept()
            except OSError:
                return  # stopped
            transport = paramiko.Transport(connection, disabled_algorithms=self._disabled_algorithms)
            transport.add_server_key(self.host_key)
            transport.set_subsystem_handler("sftp", paramiko.SFTPServer, _OneEntryFolder)
            self._transports.append(transport)
            try:
                transport.start_server(server=_Server(self.public_keys, self.events))
            except paramiko.SSHException:
                continue  # the client gave up on the handshake

    def stop(self) -> None:
        self._listener.close()
        self._thread.join(timeout=5)
        for transport in self._transports:
            transport.close()


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def asked(app, tmp_path, monkeypatch):
    """Accepts every unknown host key into a known hosts file under *tmp_path*, and counts the questions."""
    state = {"count": 0}

    class Asker:
        def ask(self, _parent, _title, _message) -> bool:
            state["count"] += 1
            return True

    monkeypatch.setattr(policy_mod, "pybreeze_data_dir", lambda: tmp_path)
    monkeypatch.setattr(policy_mod, "host_key_asker", Asker)
    monkeypatch.setattr(policy_mod, "_RECENT_DECLINES", {})
    return state


@pytest.fixture
def server():
    started = _LoopbackServer()
    yield started
    started.stop()


def _key_file(tmp_path, kind: str, server: _LoopbackServer) -> str:
    """Write a key file of *kind* the server accepts; its path."""
    make, private_format, encrypted = _KEY_FILES[kind]
    key = make()
    encryption = (serialization.BestAvailableEncryption(_PASSPHRASE.encode()) if encrypted
                  else serialization.NoEncryption())
    path = tmp_path / kind
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, private_format, encryption))
    public = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
    server.public_keys.add(public.split()[1].decode("ascii"))
    return str(path)


def _listing(client: SFTPClientWrapper) -> list[str]:
    return [entry.filename for entry in client.list_dir(".")]


def test_a_password_logs_in_and_lists_the_folder(asked, server):
    client = SFTPClientWrapper()
    try:
        client.connect("127.0.0.1", server.port, _USER, _PASSWORD)
        listed = _listing(client)
        host_key_type = client._ssh.get_transport().host_key_type
    finally:
        client.close()

    assert listed == [_ENTRY]
    assert host_key_type in ("rsa-sha2-256", "rsa-sha2-512")  # never "ssh-rsa", RSA signed with SHA-1


@pytest.mark.parametrize("kind", sorted(_KEY_FILES))
def test_each_kind_of_key_file_logs_in(asked, server, tmp_path, kind):
    key_path = _key_file(tmp_path, kind, server)
    client = SFTPClientWrapper()
    try:
        # With a key the password field holds its passphrase; a key that is not encrypted ignores it
        client.connect("127.0.0.1", server.port, _USER, _PASSPHRASE, use_key=True, key_path=key_path)
        listed = _listing(client)
    finally:
        client.close()

    assert listed == [_ENTRY]


def test_the_host_key_is_asked_about_once_and_kept(asked, server):
    for _ in range(2):
        client = SFTPClientWrapper()
        client.connect("127.0.0.1", server.port, _USER, _PASSWORD)
        client.close()

    assert asked["count"] == 1
    known = paramiko.HostKeys(str(policy_mod._known_hosts_path()))
    assert known.lookup(f"[127.0.0.1]:{server.port}") is not None


def test_a_wrong_password_is_refused_and_leaves_no_session(asked, server):
    client = SFTPClientWrapper()

    with pytest.raises(paramiko.AuthenticationException):
        client.connect("127.0.0.1", server.port, _USER, "not the password")

    assert not client.connected


def test_a_server_that_signs_only_with_sha1_is_refused(asked):
    # Its RSA host key offered as "ssh-rsa" alone: paramiko 4 would take it
    # without SHA1_ALGORITHMS; paramiko 5 has no such signature to offer.
    sha1_only = _LoopbackServer(disabled_algorithms={"keys": ("rsa-sha2-256", "rsa-sha2-512")})
    client = SFTPClientWrapper()
    try:
        with pytest.raises(paramiko.SSHException):
            client.connect("127.0.0.1", sha1_only.port, _USER, _PASSWORD)
    finally:
        sha1_only.stop()

    assert not client.connected
    assert asked["count"] == 0


def _wait_until(app, condition, seconds: float = 20) -> None:
    """Process events until *condition* holds; fail after *seconds*."""
    import time

    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > deadline:
            pytest.fail("timed out waiting")
        app.processEvents()
        time.sleep(0.02)


@pytest.fixture
def terminal(app, asked, server):
    """The SSH terminal logged in to the loopback server's shell with a password."""
    from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import SSHCommandWidget

    widget = SSHCommandWidget()
    widget.resize(800, 500)
    widget.login_widget.host_edit.setText("127.0.0.1")
    widget.login_widget.port_spin.setValue(server.port)
    widget.login_widget.user_edit.setText(_USER)
    widget.login_widget.pass_edit.setText(_PASSWORD)
    widget.connect_ssh()
    _wait_until(app, lambda: "welcome" in widget.terminal.toPlainText())
    yield widget
    widget.close()
    widget.deleteLater()


class TestTheTerminal:
    """The shell tab against a real shell channel: the other terminal tests stub the channel."""

    def test_it_opens_a_shell_with_a_pty_the_size_it_measured(self, app, terminal, server):
        (pty,) = [event for event in server.events if event[0] == "pty"]
        assert pty[1] in (b"xterm", "xterm")  # bytes from paramiko 4's server side
        assert terminal.is_connected()
        # The last size the server was told is the one the widget holds (terminal_size: at least 20 by 5)
        _wait_until(app, lambda: terminal._pty_size in [
            (event[-2], event[-1]) for event in server.events if event[0] in ("pty", "resize")][-1:])
        assert terminal._pty_size[0] >= 20
        assert terminal._pty_size[1] >= 5

    def test_a_command_is_sent_and_its_output_shown(self, app, terminal):
        terminal.command_input_edit.setText("echo 中文")
        terminal.send_command()

        _wait_until(app, lambda: "got: echo 中文" in terminal.terminal.toPlainText())
        assert terminal.command_input_edit.text() == ""

    def test_interrupt_sends_ctrl_c(self, app, terminal, server):
        terminal.send_interrupt()

        _wait_until(app, lambda: ("received", b"\x03") in server.events)

    def test_a_shell_the_server_ends_ends_the_session(self, app, terminal):
        terminal.command_input_edit.setText("exit")
        terminal.send_command()

        _wait_until(app, lambda: not terminal.is_connected() and terminal.ssh_client is None)
        assert "bye" in terminal.terminal.toPlainText()

    def test_disconnect_closes_the_shell(self, app, terminal):
        terminal.disconnect_ssh()

        assert not terminal.is_connected()
        assert terminal.ssh_client is None

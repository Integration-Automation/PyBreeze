"""The SFTP connect against a real SSH server on the loopback address.

The other SSH tests stub the network. ``requirements.txt`` does not pin
paramiko, so an install takes the latest (5.0 dropped SHA-1 and changed key
loading): this logs in the way the IDE does, with a password and with each kind
of key file, and lists a folder.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paramiko
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_host_key_policy as policy_mod
from pybreeze.pybreeze_ui.connect_gui.ssh.sftp_session import SFTPClientWrapper
from test_utils.ssh_loopback_server import (
    ONE_ENTRY, PASSWORD, USER, LoopbackServer, accept_every_host_key, wait_until,
)

_PASSPHRASE = "the passphrase"
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


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def asked(app, tmp_path, monkeypatch):
    """Accepts every unknown host key into a known hosts file under *tmp_path*, and counts the questions."""
    return accept_every_host_key(monkeypatch, tmp_path)


@pytest.fixture
def server():
    started = LoopbackServer()
    yield started
    started.stop()


def _key_file(tmp_path, kind: str, server: LoopbackServer) -> str:
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
        client.connect("127.0.0.1", server.port, USER, PASSWORD)
        listed = _listing(client)
        host_key_type = client._ssh.get_transport().host_key_type
    finally:
        client.close()

    assert listed == [ONE_ENTRY]
    assert host_key_type in ("rsa-sha2-256", "rsa-sha2-512")  # never "ssh-rsa", RSA signed with SHA-1


@pytest.mark.parametrize("kind", sorted(_KEY_FILES))
def test_each_kind_of_key_file_logs_in(asked, server, tmp_path, kind):
    key_path = _key_file(tmp_path, kind, server)
    client = SFTPClientWrapper()
    try:
        # With a key the password field holds its passphrase; a key that is not encrypted ignores it
        client.connect("127.0.0.1", server.port, USER, _PASSPHRASE, use_key=True, key_path=key_path)
        listed = _listing(client)
    finally:
        client.close()

    assert listed == [ONE_ENTRY]


def test_the_host_key_is_asked_about_once_and_kept(asked, server):
    for _ in range(2):
        client = SFTPClientWrapper()
        client.connect("127.0.0.1", server.port, USER, PASSWORD)
        client.close()

    assert asked["count"] == 1
    known = paramiko.HostKeys(str(policy_mod._known_hosts_path()))
    assert known.lookup(f"[127.0.0.1]:{server.port}") is not None


def test_a_key_file_that_cannot_be_loaded_says_why_before_connecting(asked, server, tmp_path):
    from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import UNSUPPORTED_KEY

    not_a_key = tmp_path / "notes.txt"
    not_a_key.write_text("these are notes, not a key", encoding="utf-8")
    client = SFTPClientWrapper()

    with pytest.raises(ValueError) as refused:
        client.connect("127.0.0.1", server.port, USER, "", use_key=True, key_path=str(not_a_key))

    assert str(refused.value) == client.word_dict.get(UNSUPPORTED_KEY)
    assert not client.connected


def test_a_wrong_password_is_refused_and_leaves_no_session(asked, server):
    client = SFTPClientWrapper()

    with pytest.raises(paramiko.AuthenticationException):
        client.connect("127.0.0.1", server.port, USER, "not the password")

    assert not client.connected


def test_a_server_that_signs_only_with_sha1_is_refused(asked):
    # Its RSA host key offered as "ssh-rsa" alone: paramiko 4 would take it
    # without SHA1_ALGORITHMS; paramiko 5 has no such signature to offer.
    sha1_only = LoopbackServer(disabled_algorithms={"keys": ("rsa-sha2-256", "rsa-sha2-512")})
    client = SFTPClientWrapper()
    try:
        with pytest.raises(paramiko.SSHException):
            client.connect("127.0.0.1", sha1_only.port, USER, PASSWORD)
    finally:
        sha1_only.stop()

    assert not client.connected
    assert asked["count"] == 0


@pytest.fixture
def terminal(app, asked, server):
    """The SSH terminal logged in to the loopback server's shell with a password."""
    from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import SSHCommandWidget

    widget = SSHCommandWidget()
    widget.resize(800, 500)
    widget.login_widget.host_edit.setText("127.0.0.1")
    widget.login_widget.port_spin.setValue(server.port)
    widget.login_widget.user_edit.setText(USER)
    widget.login_widget.pass_edit.setText(PASSWORD)
    widget.connect_ssh()
    wait_until(app, lambda: "welcome" in widget.terminal.toPlainText())
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
        wait_until(app, lambda: terminal._pty_size in [
            (event[-2], event[-1]) for event in server.events if event[0] in ("pty", "resize")][-1:])
        assert terminal._pty_size[0] >= 20
        assert terminal._pty_size[1] >= 5

    def test_a_command_is_sent_and_its_output_shown(self, app, terminal):
        terminal.command_input_edit.setText("echo 中文")
        terminal.send_command()

        wait_until(app, lambda: "got: echo 中文" in terminal.terminal.toPlainText())
        assert terminal.command_input_edit.text() == ""

    def test_interrupt_sends_ctrl_c(self, app, terminal, server):
        terminal.send_interrupt()

        wait_until(app, lambda: ("received", b"\x03") in server.events)

    def test_a_shell_the_server_ends_ends_the_session(self, app, terminal):
        terminal.command_input_edit.setText("exit")
        terminal.send_command()

        wait_until(app, lambda: not terminal.is_connected() and terminal.ssh_client is None)
        assert "bye" in terminal.terminal.toPlainText()

    def test_disconnect_closes_the_shell(self, app, terminal):
        terminal.disconnect_ssh()

        assert not terminal.is_connected()
        assert terminal.ssh_client is None

"""An SSH server on the loopback address, for tests that log in the way the IDE does.

It accepts a password or the public keys it is given, runs a small shell on each
shell channel, and serves SFTP: a folder with one entry, or a real folder on
disk. What the shells are asked is recorded in ``LoopbackServer.events``.
"""
from __future__ import annotations

import os
import socket
import stat
import threading
from pathlib import Path

import paramiko

USER = "tester"
PASSWORD = "the password"
ONE_ENTRY = "only_entry"


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
    def __init__(self, public_keys: set[str], events: list) -> None:
        self.public_keys = public_keys
        self.events = events

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
        return paramiko.AUTH_SUCCESSFUL if (username, password) == (USER, PASSWORD) else paramiko.AUTH_FAILED

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
        entry.filename = ONE_ENTRY
        entry.st_mode = stat.S_IFREG | 0o644
        entry.st_size = 0
        return [entry]


def _refused(error: OSError) -> int:
    return paramiko.SFTPServer.convert_errno(error.errno)


class _OpenFile(paramiko.SFTPHandle):
    def stat(self):
        try:
            return paramiko.SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))
        except OSError as error:
            return _refused(error)

    def chattr(self, attr):
        return paramiko.SFTP_OK


class _FolderOnDisk(paramiko.SFTPServerInterface):
    """SFTP over the folder *root*: the server's ``/`` is that folder."""

    def __init__(self, server, root: Path, *args, **kwargs) -> None:
        super().__init__(server, *args, **kwargs)
        self._root = root

    def _local(self, path: str) -> str:
        return str(self._root / self.canonicalize(path).lstrip("/"))

    def list_folder(self, path):
        try:
            folder = self._local(path)
            entries = []
            for name in os.listdir(folder):
                entry = paramiko.SFTPAttributes.from_stat(os.lstat(os.path.join(folder, name)))
                entry.filename = name
                entries.append(entry)
            return entries
        except OSError as error:
            return _refused(error)

    def stat(self, path):
        try:
            return paramiko.SFTPAttributes.from_stat(os.stat(self._local(path)))
        except OSError as error:
            return _refused(error)

    def lstat(self, path):
        try:
            return paramiko.SFTPAttributes.from_stat(os.lstat(self._local(path)))
        except OSError as error:
            return _refused(error)

    def open(self, path, flags, attr):
        try:
            descriptor = os.open(self._local(path), flags | getattr(os, "O_BINARY", 0), 0o666)
        except OSError as error:
            return _refused(error)
        if flags & os.O_WRONLY:
            mode = "ab" if flags & os.O_APPEND else "wb"
        elif flags & os.O_RDWR:
            mode = "a+b" if flags & os.O_APPEND else "r+b"
        else:
            mode = "rb"
        handle = _OpenFile(flags)
        handle.readfile = handle.writefile = os.fdopen(descriptor, mode)
        return handle

    def _do(self, action, *paths: str) -> int:
        try:
            action(*(self._local(path) for path in paths))
        except OSError as error:
            return _refused(error)
        return paramiko.SFTP_OK

    def remove(self, path):
        return self._do(os.remove, path)

    def rename(self, oldpath, newpath):
        return self._do(os.rename, oldpath, newpath)

    def posix_rename(self, oldpath, newpath):
        return self._do(os.replace, oldpath, newpath)

    def mkdir(self, path, attr):
        return self._do(os.mkdir, path)

    def rmdir(self, path):
        return self._do(os.rmdir, path)

    def chattr(self, path, attr):
        return paramiko.SFTP_OK


def accept_every_host_key(monkeypatch, data_dir: Path) -> dict:
    """Answer yes to every unknown host key, keep known hosts under *data_dir*; the questions are counted.

    :return: ``{"count": <questions asked>}``, updated as they are asked
    """
    from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_host_key_policy as policy_mod

    state = {"count": 0}

    class Asker:
        def ask(self, _parent, _title, _message) -> bool:
            state["count"] += 1
            return True

    monkeypatch.setattr(policy_mod, "pybreeze_data_dir", lambda: data_dir)
    monkeypatch.setattr(policy_mod, "host_key_asker", Asker)
    monkeypatch.setattr(policy_mod, "_RECENT_DECLINES", {})
    return state


def wait_until(app, condition, seconds: float = 20) -> None:
    """Process *app*'s events until *condition* holds; ``AssertionError`` after *seconds*."""
    import time

    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting")
        app.processEvents()
        time.sleep(0.02)


class LoopbackServer:
    """Accepts SSH connections on 127.0.0.1 on its own thread until stopped.

    :param disabled_algorithms: what the server's transports refuse, as paramiko takes it
    :param sftp_root: a folder SFTP serves as ``/``; without one, SFTP lists one entry
    """

    def __init__(self, disabled_algorithms: dict | None = None, sftp_root: Path | None = None) -> None:
        self.host_key = paramiko.RSAKey.generate(2048)
        self.public_keys: set[str] = set()
        self.events: list = []  # what the shells were asked: ("pty", ...), ("received", bytes), ("resize", ...)
        self._disabled_algorithms = disabled_algorithms
        self._sftp = (_FolderOnDisk, sftp_root) if sftp_root is not None else (_OneEntryFolder,)
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
            transport.set_subsystem_handler("sftp", paramiko.SFTPServer, *self._sftp)
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

"""Run one blocking SSH connect off the UI thread.

``SSHClient.connect()`` blocks for as long as the host takes: the TCP connect
(10 s here), then paramiko's banner (15 s) and auth (30 s) timeouts, and an
unreachable host used to freeze the IDE for all of it. The shell and the file
tree hand their connect to this thread and pick up on its signals. An unknown
host key is still asked about on the UI thread, through
``ssh_host_key_policy.HostKeyAsker``.
"""
from __future__ import annotations

from collections.abc import Callable

import paramiko
from PySide6.QtCore import QThread, Signal

from pybreeze.utils.logging.logger import pybreeze_logger

# What a connect can raise: paramiko's own errors (a rejected host key or
# failed auth included), the socket's, a key file that cannot be read, and an
# EOF from a server that hangs up during the handshake.
CONNECT_ERRORS = (paramiko.SSHException, OSError, ValueError, RuntimeError, EOFError)

# SHA-1 in SSH, refused on every connect: RSA signatures made with SHA-1
# ("ssh-rsa" and its certificate) and the SHA-1 key exchanges. paramiko 5
# removed them (CVE-2026-44405); a paramiko 4 install still offers all of
# them, and refusing them here keeps it from falling back to one. OpenSSH has
# refused "ssh-rsa" signatures by default since 8.8; RSA keys still work
# through rsa-sha2-256/512.
SHA1_ALGORITHMS = {
    "pubkeys": ("ssh-rsa", "ssh-rsa-cert-v01@openssh.com"),
    "keys": ("ssh-rsa", "ssh-rsa-cert-v01@openssh.com"),
    "kex": (
        "diffie-hellman-group1-sha1",
        "diffie-hellman-group14-sha1",
        "diffie-hellman-group-exchange-sha1",
    ),
}


class SshConnectThread(QThread):
    """Call *connect* on this thread; report ``connected`` or ``failed(message)``."""

    connected = Signal()
    failed = Signal(str)

    def __init__(self, connect: Callable[[], None]) -> None:
        super().__init__()
        self._connect = connect

    def run(self) -> None:
        try:
            self._connect()
        except CONNECT_ERRORS as error:
            # Its text, not the exception: a handler that keeps records kept the
            # traceback, and through its frames the panel that connected
            pybreeze_logger.info("SSH connect failed: %s", repr(error))
            self.failed.emit(str(error))
        else:
            self.connected.emit()

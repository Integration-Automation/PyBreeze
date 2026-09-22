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
            pybreeze_logger.info("SSH connect failed: %r", error)
            self.failed.emit(str(error))
        else:
            self.connected.emit()

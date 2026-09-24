"""The SFTP session behind the file tree, and the threads that use it.

``SFTPClientWrapper`` holds one SSH connection and its SFTP client and lets one
request at a time through. ``SftpListThread``, ``SftpTransferThread`` and
``SftpCallThread`` run listings, transfers and the context menu's requests off
the UI thread; the tree (``ssh_file_viewer_widget.py``) only reacts to their
signals. The path helpers here are pure: remote paths are always POSIX.
"""
from __future__ import annotations

import os
import posixpath
import re
import stat
import tempfile
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress

import paramiko
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_connect_thread import SHA1_ALGORITHMS
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_host_key_policy import apply_host_key_policy
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import load_private_key, unloadable_key_reason
from pybreeze.utils.logging.logger import pybreeze_logger


# Keepalive interval (seconds) so an idle SFTP session is not dropped by the
# TCP stack, a NAT/firewall, or the SSH server (≈ OpenSSH ServerAliveInterval).
SSH_KEEPALIVE_SECONDS = 30
# How long a menu action waits for the session before saying it is busy:
# long enough for a listing, and a transfer can hold it for minutes
UI_WAIT_SECONDS = 1.0


def natural_key(name: str) -> list:
    """Sort key giving natural (human) order, e.g. ``img2`` before ``img10``.

    Embedded digit runs compare as integers and text compares case-insensitively,
    matching how Windows Explorer and most file managers order file listings.
    """
    # isdecimal (not isdigit): a part like "²³" or "①" is isdigit() but int()
    # rejects it, which would crash sorting a file named with such characters.
    return [
        int(part) if part.isdecimal() else part.lower()
        for part in re.split(r"(\d+)", name)
    ]


def sort_entries(entries) -> list:
    """Return ``[(name, entry)]`` with directories first, each in natural order."""
    dirs: list = []
    files: list = []
    for entry in entries:
        bucket = dirs if stat.S_ISDIR(entry.st_mode) else files
        bucket.append((entry.filename, entry))
    dirs.sort(key=lambda item: natural_key(item[0]))
    files.sort(key=lambda item: natural_key(item[0]))
    return dirs + files


def remote_join(directory: str, name: str) -> str:
    """Join *name* under a remote POSIX *directory* into an absolute path.

    Remote SFTP paths are always POSIX: ``os.path.join`` would emit ``\\`` on a
    Windows client and break navigation/transfers on the server. The result
    always uses ``/`` separators and has a leading slash.
    """
    base = "" if directory == "/" else directory
    joined = posixpath.join(base, name)
    return joined if joined.startswith("/") else f"/{joined}"


def plain_remote_name(text: str) -> str | None:
    """*text* stripped, when it names one entry in a folder; ``None`` otherwise.

    A ``/`` in a new name moved the entry into another folder (or, leading,
    dropped the folder it was in), and ``.`` or ``..`` named the folder itself
    or its parent.
    """
    name = text.strip()
    if not name or "/" in name or "\x00" in name or name in (".", ".."):
        return None
    return name


class SftpBusy(RuntimeError):
    """Another request holds the SFTP session (a transfer, a listing); try again after it."""


class ConnectAbandoned(RuntimeError):
    """The session came up after the connect was given up on, and was closed."""


class SFTPClientWrapper:
    """
    Lightweight wrapper around Paramiko SFTP client.
    輕量級封裝 Paramiko SFTP 客戶端，提供基本操作。
    """

    def __init__(self):
        self.word_dict = language_wrapper.language_word_dict
        self._ssh: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None
        self.root_path: str = "/"
        # One request at a time on the session: paramiko's SFTP client throws
        # away a reply read by the wrong thread, and the thread that sent that
        # request then waits for it forever. Listings, a transfer and the menu's
        # own calls used to share it freely.
        self._in_use = threading.Lock()

    def connect(self, host: str, port: int, username: str, password: str,
                use_key: bool = False, key_path: str = "",
                parent_widget: QWidget | None = None):
        """
        Establish SSH + SFTP connection.
        建立 SSH + SFTP 連線。

        Runs on the connect thread while ``close()`` may run on the UI thread
        (Disconnect, or the tab closing). The session is kept only if it is
        still this connect's when it is up; otherwise it is closed and
        ``ConnectAbandoned`` raised. Closing during the TCP connect cannot stop
        it, and the session it went on to log in used to stay open, unseen,
        until the IDE exited.
        """
        self.close()
        ssh = paramiko.SSHClient()
        self._ssh = ssh
        apply_host_key_policy(ssh, parent_widget)
        pybreeze_logger.info("SFTP connecting to %s:%s", host, port)
        try:
            self._log_in(ssh, host, port, username, password, use_key, key_path)
            transport = ssh.get_transport()
            if transport is not None:
                transport.set_keepalive(SSH_KEEPALIVE_SECONDS)
            sftp = ssh.open_sftp()
            if self._ssh is not ssh:
                raise ConnectAbandoned("SFTP connect abandoned")
            self._sftp = sftp
        except Exception:
            # A failure partway (auth, keepalive, or open_sftp) must not leak the
            # half-open SSH transport: tear it down so connect() is all-or-nothing.
            # Only this connect's own: a newer one may be under way by now.
            ssh.close()
            if self._ssh is ssh:
                self._ssh = None
            raise

    def _log_in(self, ssh: paramiko.SSHClient, host: str, port: int, username: str,
                password: str, use_key: bool, key_path: str) -> None:
        """Connect *ssh* with the key file, or the password when no key is used."""
        if not (use_key and key_path):
            ssh.connect(hostname=host, port=port, username=username, password=password,
                        timeout=10, disabled_algorithms=SHA1_ALGORITHMS)
            return
        pkey = load_private_key(key_path, password, context="SFTP")
        if pkey is None:
            raise ValueError(self.word_dict.get(unloadable_key_reason(key_path, password)))
        ssh.connect(hostname=host, port=port, username=username, pkey=pkey, timeout=10,
                    disabled_algorithms=SHA1_ALGORITHMS)

    def close(self):
        """
        Close SFTP and SSH safely.
        安全關閉 SFTP 與 SSH。
        """
        try:
            if self._sftp:
                self._sftp.close()
        finally:
            self._sftp = None
        try:
            if self._ssh:
                self._ssh.close()
        finally:
            self._ssh = None

    @property
    def connected(self) -> bool:
        """
        Check connection state.
        檢查連線狀態。
        """
        return self._ssh is not None and self._sftp is not None

    def _require_connection(self) -> None:
        """Raise unless a session is open.

        Every call below goes through this: without it an operation on a stale
        tree (a dropped session, a closed connection) reaches ``None`` and the
        tree's error box shows the user an ``AttributeError`` about ``NoneType``.
        """
        if not self.connected:
            raise RuntimeError(
                self.word_dict.get("ssh_command_widget_dialog_title_not_connected")
            )

    @contextmanager
    def _session(self, wait: float | None = None) -> Iterator[paramiko.SFTPClient]:
        """Hold the session for one request and yield it, open.

        :param wait: seconds to wait for a request already running; ``None``
            waits as long as it takes (worker threads). The menu's calls run on
            the UI thread and wait briefly: a transfer can hold the session for
            minutes, and they are refused with ``SftpBusy`` instead.
        """
        acquired = self._in_use.acquire() if wait is None else self._in_use.acquire(timeout=wait)
        if not acquired:
            raise SftpBusy(self.word_dict.get("ssh_file_viewer_message_session_busy"))
        try:
            self._require_connection()
            sftp = self._sftp
            if sftp is None:  # closed from the UI thread since the check
                self._require_connection()
            yield sftp
        finally:
            self._in_use.release()

    def list_dir(self, path: str):
        """
        List directory entries with stat attributes. Worker thread.
        列出目錄項目（含屬性）。
        """
        with self._session() as sftp:
            return sftp.listdir_attr(path)

    def mkdir(self, path: str):
        """
        Create directory.
        建立目錄。
        """
        with self._session(UI_WAIT_SECONDS) as sftp:
            sftp.mkdir(path)

    def remove_file(self, path: str):
        """
        Remove file.
        刪除檔案。
        """
        with self._session(UI_WAIT_SECONDS) as sftp:
            sftp.remove(path)

    def remove_dir(self, path: str):
        """
        Remove empty directory.
        刪除空目錄。
        """
        with self._session(UI_WAIT_SECONDS) as sftp:
            sftp.rmdir(path)

    def rename(self, old_path: str, new_path: str):
        """
        Rename file/folder.
        重新命名檔案/資料夾。
        """
        with self._session(UI_WAIT_SECONDS) as sftp:
            sftp.rename(old_path, new_path)

    def download(self, remote_path: str, local_path: str):
        """
        Download remote to local. Worker thread.
        下載遠端檔案至本地。

        The file arrives beside *local_path* under a temporary name and takes
        its place only when complete: ``get`` empties its target before the
        first byte, so a dropped link or a Disconnect used to leave the file
        the user chose to replace cut short.
        """
        self._require_connection()
        folder = os.path.dirname(os.path.abspath(local_path))
        handle, partial = tempfile.mkstemp(
            prefix=f".{os.path.basename(local_path)}.", suffix=".part", dir=folder)
        os.close(handle)
        complete = False
        try:
            with self._session() as sftp:
                sftp.get(remote_path, partial)
            os.replace(partial, local_path)
            complete = True
        finally:
            if not complete:
                with suppress(OSError):
                    os.remove(partial)

    def upload(self, local_path: str, remote_path: str, replace: bool = False) -> bool:
        """
        Upload local to remote. Worker thread.
        上傳本地檔案至遠端。

        Uploads nothing and returns ``False`` when *remote_path* exists and
        *replace* is false: it used to be replaced without a word. The file
        arrives beside it under a temporary name and takes its place only when
        complete, as a download does: ``put`` empties its target before the
        first byte, so a dropped link used to leave the server's copy cut short.
        """
        folder, name = posixpath.split(remote_path)
        partial = remote_join(folder or "/", f".{name}.{uuid.uuid4().hex[:8]}.part")
        with self._session() as sftp:
            if not replace and _remote_exists(sftp, remote_path):
                return False
            complete = False
            try:
                sftp.put(local_path, partial)
                _move_into_place(sftp, partial, remote_path)
                complete = True
            finally:
                if not complete:
                    with suppress(OSError, EOFError, paramiko.SSHException):
                        sftp.remove(partial)
        return True


def _remote_exists(sftp: paramiko.SFTPClient, path: str) -> bool:
    """Whether *path* exists on the server."""
    try:
        sftp.stat(path)
    except FileNotFoundError:
        return False
    return True


def _move_into_place(sftp: paramiko.SFTPClient, partial: str, target: str) -> None:
    """Rename *partial* to *target*, replacing it.

    ``posix_rename`` (an OpenSSH extension) replaces in one step. A server
    without it gets the plain SFTP rename, which refuses an existing target,
    so the target is removed first.
    """
    try:
        sftp.posix_rename(partial, target)
        return
    except OSError as error:
        pybreeze_logger.debug("SFTP posix_rename unavailable, renaming plainly: %r", error)
    with suppress(FileNotFoundError):
        sftp.remove(target)
    sftp.rename(partial, target)


class SftpTransferThread(QThread):
    """One SFTP transfer, off the UI thread.

    A transfer has no timeout of its own, and a file can be any size: run in the
    button's slot, a download over a stalled link holds every tab, every run
    window and the editor itself until it finishes. Only the two signals reach
    the UI, and only one transfer runs at a time -- a paramiko SFTP session is
    not meant to be used from two places at once.
    """

    done = Signal(str)
    failed = Signal(str)
    # An upload whose target exists, not replaced: nothing was sent
    exists = Signal(str)

    def __init__(self, client: "SFTPClientWrapper", downloading: bool,
                 remote_path: str, local_path: str, replace: bool = False) -> None:
        super().__init__()
        self._client = client
        self._downloading = downloading
        self._remote_path = remote_path
        self._local_path = local_path
        self._replace = replace

    def run(self) -> None:
        try:
            if self._downloading:
                self._client.download(self._remote_path, self._local_path)
            elif not self._client.upload(self._local_path, self._remote_path, self._replace):
                self.exists.emit(self._remote_path)
                return
        except (OSError, RuntimeError, EOFError, paramiko.SSHException) as error:
            self.failed.emit(str(error))
        else:
            self.done.emit(self._local_path if self._downloading else self._remote_path)


class SftpListThread(QThread):
    """List one remote directory off the UI thread, sorted for the tree.

    ``listdir_attr()`` has no timeout of its own and returns every entry at
    once, so a stalled server or a directory of tens of thousands of files
    used to hold the IDE until it answered.
    """

    listed = Signal(object)  # [(name, SFTPAttributes)], directories first
    failed = Signal(str)

    def __init__(self, client: "SFTPClientWrapper", path: str) -> None:
        super().__init__()
        self._client = client
        self._path = path

    def run(self) -> None:
        try:
            entries = self._client.list_dir(self._path)
        except (OSError, RuntimeError, EOFError, paramiko.SSHException) as error:
            self.failed.emit(str(error))
        else:
            self.listed.emit(sort_entries(entries))


class SftpCallThread(QThread):
    """One of the context menu's requests (create folder, rename, delete), off the UI thread.

    An SFTP reply has no timeout: on a stalled link the request waited in the
    menu's slot and the IDE froze until TCP gave up.
    """

    done = Signal()
    failed = Signal(str)

    def __init__(self, call: Callable[[], None]) -> None:
        super().__init__()
        self._call = call

    def run(self) -> None:
        try:
            self._call()
        except (OSError, RuntimeError, EOFError, paramiko.SSHException) as error:
            self.failed.emit(str(error))
        else:
            self.done.emit()

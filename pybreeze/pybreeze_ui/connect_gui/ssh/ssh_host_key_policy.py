"""Interactive SSH host key policy with persistent trust-on-first-use (TOFU).

Replaces the MITM-prone ``paramiko.AutoAddPolicy`` / ``paramiko.WarningPolicy``:
unknown host keys are shown to the user via a Qt dialog with their SHA256
fingerprint, and only accepted on explicit confirmation. Confirmed hosts are
persisted to ``~/.pybreeze/ssh_known_hosts`` so subsequent connections verify
automatically.
"""
from __future__ import annotations

import base64
import hashlib
import threading
import time
import weakref
from pathlib import Path
from typing import TYPE_CHECKING

import paramiko
import shiboken6
from je_editor import language_wrapper
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from pybreeze.utils.app_dirs import pybreeze_data_dir
from pybreeze.utils.file_process.replace_file import replace_written
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.pybreeze_ui.plain_text import as_text

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def _known_hosts_path() -> Path:
    """Return the PyBreeze-managed known_hosts file path, ensuring the parent dir exists."""
    return pybreeze_data_dir() / "ssh_known_hosts"


def _fingerprint_sha256(key: paramiko.PKey) -> str:
    """Return an OpenSSH-style SHA256 fingerprint (``SHA256:base64`` without padding)."""
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).rstrip(b"=").decode("ascii")


# Held while a host key is looked up, asked about and stored. Only connect
# threads take it (both SSH widgets connect off the UI thread), so the UI
# thread that shows the question never waits on it.
_DECISION_LOCK = threading.Lock()
# (host, fingerprint) -> when the user said no: the other half of the same
# Connect is refused without a second question.
_RECENT_DECLINES: dict[tuple[str, str], float] = {}
_DECLINE_REMEMBERED_SECONDS = 10.0


def _declined_just_now(hostname: str, fingerprint: str) -> bool:
    declined_at = _RECENT_DECLINES.get((hostname, fingerprint))
    return declined_at is not None and time.monotonic() - declined_at < _DECLINE_REMEMBERED_SECONDS


def _read_known_hosts() -> paramiko.HostKeys:
    """The known hosts file as it is now; empty when it is missing or unreadable."""
    known = paramiko.HostKeys()
    path = _known_hosts_path()
    if path.is_file():
        try:
            known.load(str(path))
        except OSError as err:
            pybreeze_logger.warning("Failed to load PyBreeze known_hosts: %s", err)
    return known


def _is_trusted_on_disk(hostname: str, key: paramiko.PKey) -> bool:
    """Whether *key* was accepted for *hostname* since this connect read the file."""
    entry = _read_known_hosts().lookup(hostname)
    return entry is not None and entry.get(key.get_name()) == key


def _store(hostname: str, key_type: str, key: paramiko.PKey) -> None:
    """Add the key to the file as it is now.

    Not ``client.save_host_keys``: that writes the client's own copy, read at
    its Connect, over hosts another tab accepted since.
    """
    known = _read_known_hosts()
    known.add(hostname, key_type, key)
    try:
        # Replaced in one step: HostKeys.save opens the file for writing, which
        # empties it, and a failure part-way lost every host trusted so far
        replace_written(_known_hosts_path(), lambda target: known.save(str(target)))
    except OSError as err:
        pybreeze_logger.warning(
            "Failed to persist SSH host key for %s: %s", hostname, err
        )


class InteractiveHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Policy that prompts the user to verify unknown host keys.

    Accepted keys are persisted so later connections pass through ``RejectPolicy``-like
    strictness automatically. Declined keys abort the connection with ``SSHException``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__()
        # Weakly: the client holding this policy is held by the connect's slots
        # through Qt, so a strong parent kept the closed SSH panel alive
        self._parent = weakref.ref(parent) if parent is not None else None
        self._word_dict = language_wrapper.language_word_dict

    def _asked(self, title: str, message: str) -> bool:
        """Whether the user trusts the key; No when the panel that asked has gone."""
        if self._parent is None:
            return host_key_asker().ask(None, title, message)
        parent = self._parent()
        return parent is not None and host_key_asker().ask(parent, title, message)

    def missing_host_key(
        self,
        client: paramiko.SSHClient,
        hostname: str,
        key: paramiko.PKey,
    ) -> None:
        fingerprint = _fingerprint_sha256(key)
        key_type = key.get_name()

        title = self._word_dict.get(
            "ssh_host_key_policy_dialog_title_verify_host",
            "Verify SSH host key",
        )
        message_template = self._word_dict.get(
            "ssh_host_key_policy_dialog_message_verify_host",
            "The authenticity of host '{host}' cannot be established.\n"
            "{key_type} key fingerprint is {fingerprint}.\n\n"
            "Do you want to trust this host and continue connecting?",
        )
        message = message_template.format(
            host=hostname, key_type=key_type, fingerprint=fingerprint
        )

        # One Connect starts two connects (shell and file tree), each with the
        # file as it was at the click: one at a time, and each looks at the
        # file again first, so the user is asked once.
        with _DECISION_LOCK:
            if _is_trusted_on_disk(hostname, key):
                client.get_host_keys().add(hostname, key_type, key)
                return
            if _declined_just_now(hostname, fingerprint) or not self._asked(title, message):
                _RECENT_DECLINES[(hostname, fingerprint)] = time.monotonic()
                pybreeze_logger.warning(
                    "SSH host key for %s rejected by user (%s)", hostname, fingerprint
                )
                raise paramiko.SSHException(
                    f"Host key for {hostname} rejected by user."
                )
            client.get_host_keys().add(hostname, key_type, key)
            _store(hostname, key_type, key)
        pybreeze_logger.info(
            "SSH host key for %s accepted and stored (%s)", hostname, fingerprint
        )


class HostKeyAsker(QObject):
    """Asks the user about an unknown host key, on the UI thread, from any thread.

    ``SSHClient.connect()`` calls the host-key policy from whichever thread is
    connecting. To connect off the UI thread and still ask, the question travels
    to this object -- which lives on the UI thread -- over a blocking queued
    signal: the connecting thread waits for the answer, the UI does not.
    """

    _asked = Signal(object, str, str)

    def __init__(self) -> None:
        super().__init__()
        self._answer = False
        self._asked.connect(self._show, Qt.ConnectionType.BlockingQueuedConnection)

    def ask(self, parent: QWidget | None, title: str, message: str) -> bool:
        """Show the question and return whether the user trusts the key.

        Every question starts from No: a question that could not be shown
        returned the previous one's answer, and a Yes given to one host trusted
        the next host unasked.
        """
        self._answer = False
        if QThread.currentThread() is self.thread():
            # Already on the UI thread: a blocking queued signal to ourselves
            # would wait for itself forever.
            self._show(parent, title, message)
        else:
            self._asked.emit(parent, title, message)
        return self._answer

    @Slot(object, str, str)
    def _show(self, parent: QWidget | None, title: str, message: str) -> None:
        if parent is not None and not shiboken6.isValid(parent):
            # The panel that connected was closed while it connected (a dock
            # is deleted on close): nobody is there to answer, so it is No
            pybreeze_logger.warning("SSH host key question dropped: its panel was closed")
            return
        box = QMessageBox(parent)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(as_text(message))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        self._answer = box.exec() == QMessageBox.StandardButton.Yes


_ASKER: HostKeyAsker | None = None


def host_key_asker() -> HostKeyAsker:
    """The asker, created on first use -- which has to be on the UI thread.

    The SSH widgets call this when they are built, so a connection started later
    on a worker thread finds it already living where dialogs can be shown.
    """
    global _ASKER
    if _ASKER is None:
        _ASKER = HostKeyAsker()
    return _ASKER


def apply_host_key_policy(client: paramiko.SSHClient, parent: QWidget | None) -> None:
    """Load known hosts and attach the interactive TOFU policy to *client*."""
    client.load_system_host_keys()
    known_hosts = _known_hosts_path()
    if known_hosts.is_file():
        try:
            client.load_host_keys(str(known_hosts))
        except OSError as err:
            pybreeze_logger.warning("Failed to load PyBreeze known_hosts: %s", err)
    client.set_missing_host_key_policy(InteractiveHostKeyPolicy(parent))

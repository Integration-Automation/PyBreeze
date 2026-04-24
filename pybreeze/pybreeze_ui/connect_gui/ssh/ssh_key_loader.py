"""Shared private-key loader for SSH widgets.

Both the interactive shell widget and the SFTP file-viewer need to pick the
right paramiko key class for an arbitrary private-key file. Centralising the
loop here keeps the widgets lean and avoids duplicated fallback logic.
"""
from __future__ import annotations

import paramiko

from pybreeze.utils.logging.logger import pybreeze_logger

_KEY_CLASSES: tuple[type[paramiko.PKey], ...] = (
    paramiko.RSAKey,
    paramiko.Ed25519Key,
    paramiko.ECDSAKey,
)


def load_private_key(key_path: str, password: str, *, context: str = "SSH") -> paramiko.PKey | None:
    """Try each supported key type against *key_path*; return the first that parses.

    ``password`` is treated as the passphrase (empty string → no passphrase).
    ``context`` is included in debug logs so SFTP vs shell failures are distinguishable.
    """
    passphrase = password if password else None
    for key_cls in _KEY_CLASSES:
        try:
            return key_cls.from_private_key_file(key_path, passphrase)
        except (paramiko.SSHException, ValueError, OSError) as error:
            pybreeze_logger.debug("%s key type %s rejected: %s", context, key_cls.__name__, error)
    return None

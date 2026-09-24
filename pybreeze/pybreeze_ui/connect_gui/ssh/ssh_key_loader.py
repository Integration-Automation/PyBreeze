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

# Word-dict keys for why a key file could not be loaded
UNSUPPORTED_KEY = "ssh_command_widget_error_message_unsupported_private_key"
PASSPHRASE_NEEDED = "ssh_key_error_passphrase_needed"
PASSPHRASE_WRONG = "ssh_key_error_passphrase_wrong"


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


def unloadable_key_reason(key_path: str, password: str) -> str:
    """The word-dict key saying why :func:`load_private_key` gave ``None`` for *key_path*.

    A key file that is encrypted is one some key class asks a passphrase for
    when given none; then the passphrase was missing or wrong, not the key
    unsupported, which is all the message used to say.
    """
    for key_cls in _KEY_CLASSES:
        try:
            key_cls.from_private_key_file(key_path, None)
        except paramiko.PasswordRequiredException:
            return PASSPHRASE_WRONG if password else PASSPHRASE_NEEDED
        except (paramiko.SSHException, ValueError, OSError) as error:
            pybreeze_logger.debug("Key type %s rejected: %s", key_cls.__name__, error)
    return UNSUPPORTED_KEY

"""Shared private-key loader for SSH widgets.

Both the interactive shell widget and the SFTP file-viewer need to pick the
right paramiko key class for an arbitrary private-key file. Centralising the
loop here keeps the widgets lean and avoids duplicated fallback logic.
"""
from __future__ import annotations

import io
import warnings
from pathlib import Path

import paramiko
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.utils import CryptographyDeprecationWarning

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
PUTTY_KEY = "ssh_key_error_putty_key"

# A PuTTY key file (.ppk), which neither paramiko nor cryptography reads
_PUTTY_HEADER = b"PuTTY-User-Key-File-"

# PKCS#8, which paramiko does not read (openssl genpkey, ssh-keygen -m PKCS8)
_PKCS8_PLAIN = b"-----BEGIN PRIVATE KEY-----"  # nosemgrep  # gitleaks:allow — a format marker, not a key
_PKCS8_ENCRYPTED = b"-----BEGIN ENCRYPTED PRIVATE KEY-----"


def load_private_key(key_path: str, password: str, *, context: str = "SSH") -> paramiko.PKey | None:
    """Try each supported key type against *key_path*; return the first that parses.

    A PKCS#8 file, which none of them reads, goes through :func:`_load_pkcs8`.

    ``password`` is treated as the passphrase (empty string → no passphrase).
    ``context`` is included in debug logs so SFTP vs shell failures are distinguishable.
    """
    passphrase = password if password else None
    for key_cls in _KEY_CLASSES:
        try:
            return key_cls.from_private_key_file(key_path, passphrase)
        except (paramiko.SSHException, ValueError, OSError) as error:
            pybreeze_logger.debug("%s key type %s rejected: %s", context, key_cls.__name__, error)
    return _load_pkcs8(key_path, passphrase, context)


def _key_file_data(key_path: str, *headers: bytes) -> bytes | None:
    """The contents of *key_path* if it starts with one of *headers*, else ``None``."""
    try:
        data = Path(key_path).read_bytes().lstrip()
    except OSError:
        return None
    return data if data.startswith(headers) else None


def _load_pkcs8(key_path: str, passphrase: str | None, context: str) -> paramiko.PKey | None:
    """A PKCS#8 key file as a paramiko key, or ``None``.

    cryptography reads it and writes it again in OpenSSH's format, in memory
    only, for paramiko to load. A passphrase is used only for an encrypted
    file: paramiko ignores one given for a plain key, and so does this.
    """
    data = _key_file_data(key_path, _PKCS8_PLAIN, _PKCS8_ENCRYPTED)
    if data is None:
        return None
    password = passphrase.encode("utf-8") if passphrase and data.startswith(_PKCS8_ENCRYPTED) else None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", CryptographyDeprecationWarning)  # a DSA key
            key = serialization.load_pem_private_key(data, password)
            openssh = key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption())
    except (ValueError, TypeError, UnsupportedAlgorithm) as error:
        pybreeze_logger.debug("%s PKCS#8 key not read: %s", context, type(error).__name__)
        return None
    for key_cls in _KEY_CLASSES:
        try:
            return key_cls.from_private_key(io.StringIO(openssh.decode("ascii")))
        except (paramiko.SSHException, ValueError) as error:
            pybreeze_logger.debug("%s PKCS#8 key type %s rejected: %s", context, key_cls.__name__, error)
    return None


def unloadable_key_reason(key_path: str, password: str) -> str:
    """The word-dict key saying why :func:`load_private_key` gave ``None`` for *key_path*.

    A key file that is encrypted is one some key class asks a passphrase for
    when given none; then the passphrase was missing or wrong, not the key
    unsupported, which is all the message used to say. A passphrase given is
    wrong only when it does not decrypt the file: an encrypted key of a type
    paramiko cannot load (DSA, a FIDO key) asks for one too, and with the
    right one it is still unsupported. An encrypted PKCS#8 file says so in
    its first line, which paramiko does not read. A PuTTY key is to be
    exported as an OpenSSH one.
    """
    if _key_file_data(key_path, _PUTTY_HEADER) is not None:
        return PUTTY_KEY
    if _key_file_data(key_path, _PKCS8_ENCRYPTED) is not None or _asks_for_passphrase(key_path):
        return _encrypted_key_reason(key_path, password)
    return UNSUPPORTED_KEY


def _asks_for_passphrase(key_path: str) -> bool:
    """Whether some key class asks for a passphrase to load *key_path*: the file is encrypted."""
    for key_cls in _KEY_CLASSES:
        try:
            key_cls.from_private_key_file(key_path, None)
        except paramiko.PasswordRequiredException:
            return True
        except (paramiko.SSHException, ValueError, OSError) as error:
            pybreeze_logger.debug("Key type %s rejected: %s", key_cls.__name__, error)
    return False


def _encrypted_key_reason(key_path: str, password: str) -> str:
    """Why an encrypted key file did not load: no passphrase, a wrong one, or a type paramiko cannot use."""
    if not password:
        return PASSPHRASE_NEEDED
    return UNSUPPORTED_KEY if _decrypts(key_path, password) else PASSPHRASE_WRONG


def _decrypts(key_path: str, password: str) -> bool:
    """Whether *password* decrypts the private key file at *key_path*, whatever its key type."""
    try:
        data = Path(key_path).read_bytes()
    except OSError:
        return False
    with warnings.catch_warnings():
        # A DSA key is deprecated in cryptography, which is what is being found out
        warnings.simplefilter("ignore", CryptographyDeprecationWarning)
        for loader in (serialization.load_ssh_private_key, serialization.load_pem_private_key):
            try:
                loader(data, password.encode("utf-8"))
                return True
            except UnsupportedAlgorithm:
                return True  # decrypted far enough to see a type it does not take
            except (ValueError, TypeError) as error:
                pybreeze_logger.debug("Key not decrypted by %s: %s", loader.__name__, type(error).__name__)
    return False

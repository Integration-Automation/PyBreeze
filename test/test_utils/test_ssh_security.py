from __future__ import annotations

import base64
import hashlib

import paramiko
import pytest

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_connect_thread import SHA1_ALGORITHMS
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_host_key_policy import _fingerprint_sha256
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import load_private_key


class TestFingerprint:
    def test_format_and_value(self):
        key = paramiko.RSAKey.generate(2048)
        fp = _fingerprint_sha256(key)
        assert fp.startswith("SHA256:")
        assert "=" not in fp  # OpenSSH style strips base64 padding
        expected = "SHA256:" + base64.b64encode(
            hashlib.sha256(key.asbytes()).digest()
        ).rstrip(b"=").decode("ascii")
        assert fp == expected

    def test_distinct_keys_have_distinct_fingerprints(self):
        fp1 = _fingerprint_sha256(paramiko.RSAKey.generate(2048))
        fp2 = _fingerprint_sha256(paramiko.RSAKey.generate(2048))
        assert fp1 != fp2


class TestLoadPrivateKey:
    def test_missing_file_returns_none(self, tmp_path):
        assert load_private_key(str(tmp_path / "nope"), "") is None

    def test_rsa_round_trip(self, tmp_path):
        path = tmp_path / "id_rsa"
        paramiko.RSAKey.generate(2048).write_private_key_file(str(path))
        loaded = load_private_key(str(path), "")
        assert isinstance(loaded, paramiko.RSAKey)

    def test_ecdsa_loads_via_fallback(self, tmp_path):
        # ECDSA is the third key class tried, so this exercises the fallback loop.
        path = tmp_path / "id_ecdsa"
        paramiko.ECDSAKey.generate().write_private_key_file(str(path))
        loaded = load_private_key(str(path), "")
        assert isinstance(loaded, paramiko.ECDSAKey)

    def test_encrypted_key_requires_correct_passphrase(self, tmp_path):
        path = tmp_path / "id_rsa_enc"
        paramiko.RSAKey.generate(2048).write_private_key_file(str(path), password="secret")
        assert load_private_key(str(path), "wrong") is None
        assert isinstance(load_private_key(str(path), "secret"), paramiko.RSAKey)


def _encrypted_key_file(tmp_path, kind: str):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

    key, key_format = {
        "rsa-openssh": (rsa.generate_private_key(65537, 2048), serialization.PrivateFormat.OpenSSH),
        "ed25519-openssh": (ed25519.Ed25519PrivateKey.generate(), serialization.PrivateFormat.OpenSSH),
        "rsa-pem": (rsa.generate_private_key(65537, 2048), serialization.PrivateFormat.TraditionalOpenSSL),
        "ecdsa-pem": (ec.generate_private_key(ec.SECP256R1()), serialization.PrivateFormat.TraditionalOpenSSL),
    }[kind]
    path = tmp_path / kind
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, key_format, serialization.BestAvailableEncryption(b"right")))
    return str(path)


class TestWhyAKeyDidNotLoad:
    """A wrong or missing passphrase was reported as an unsupported key."""

    @pytest.mark.parametrize("kind", ["rsa-openssh", "ed25519-openssh", "rsa-pem", "ecdsa-pem"])
    def test_the_passphrase_is_named(self, tmp_path, kind):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import (
            PASSPHRASE_NEEDED, PASSPHRASE_WRONG, unloadable_key_reason
        )

        path = _encrypted_key_file(tmp_path, kind)

        assert load_private_key(path, "right") is not None
        assert load_private_key(path, "wrong") is None
        assert unloadable_key_reason(path, "wrong") == PASSPHRASE_WRONG
        assert load_private_key(path, "") is None
        assert unloadable_key_reason(path, "") == PASSPHRASE_NEEDED

    def test_an_encrypted_key_paramiko_cannot_load_is_unsupported_with_the_right_passphrase(self, tmp_path):
        # A DSA key in OpenSSH format asks for a passphrase too: the right one
        # was reported as wrong
        import warnings

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import dsa

        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import (
            PASSPHRASE_WRONG, UNSUPPORTED_KEY, unloadable_key_reason
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # cryptography deprecates DSA
            data = dsa.generate_private_key(1024).private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
                serialization.BestAvailableEncryption(b"right"))
        path = tmp_path / "id_dsa"
        path.write_bytes(data)

        assert load_private_key(str(path), "right") is None
        assert unloadable_key_reason(str(path), "right") == UNSUPPORTED_KEY
        assert unloadable_key_reason(str(path), "wrong") == PASSPHRASE_WRONG

    def test_a_file_that_is_no_key_is_unsupported(self, tmp_path):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import UNSUPPORTED_KEY, unloadable_key_reason

        path = tmp_path / "not_a_key"
        path.write_text("hello", encoding="utf-8")

        assert unloadable_key_reason(str(path), "anything") == UNSUPPORTED_KEY
        assert unloadable_key_reason(str(tmp_path / "missing"), "") == UNSUPPORTED_KEY

    def test_each_reason_has_a_message(self):
        from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict as english_word_dict
        from pybreeze.extend_multi_language.extend_traditional_chinese import (
            pybreeze_traditional_chinese_word_dict as traditional_chinese_word_dict,
        )
        from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_key_loader

        for key in (ssh_key_loader.UNSUPPORTED_KEY, ssh_key_loader.PASSPHRASE_NEEDED, ssh_key_loader.PASSPHRASE_WRONG):
            assert english_word_dict.get(key) and traditional_chinese_word_dict.get(key)


class TestSha1Algorithms:
    def test_a_transport_given_them_offers_no_sha1(self):
        import socket

        ours, theirs = socket.socketpair()
        transport = paramiko.Transport(ours, disabled_algorithms=SHA1_ALGORITHMS)
        try:
            offered = (*transport.preferred_keys, *transport.preferred_kex, *transport.preferred_pubkeys)
        finally:
            transport.close()
            theirs.close()

        assert [name for name in offered if "sha1" in name or name.startswith("ssh-rsa")] == []
        # RSA keys still work, signed with SHA-2
        assert "rsa-sha2-256" in transport.preferred_pubkeys

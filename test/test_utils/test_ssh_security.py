from __future__ import annotations

import base64
import hashlib

import paramiko

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

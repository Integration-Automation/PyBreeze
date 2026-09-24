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

        for key in (ssh_key_loader.UNSUPPORTED_KEY, ssh_key_loader.PASSPHRASE_NEEDED, ssh_key_loader.PASSPHRASE_WRONG,
                    ssh_key_loader.PUTTY_KEY):
            assert english_word_dict.get(key) and traditional_chinese_word_dict.get(key)


def _pkcs8_key_file(tmp_path, kind: str, passphrase: bytes | None):
    """A PKCS#8 key file (BEGIN PRIVATE KEY / BEGIN ENCRYPTED PRIVATE KEY) and its public key."""
    import warnings

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, rsa

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # cryptography deprecates DSA
        key = {
            "rsa": lambda: rsa.generate_private_key(65537, 2048),
            "ed25519": ed25519.Ed25519PrivateKey.generate,
            "ecdsa": lambda: ec.generate_private_key(ec.SECP256R1()),
            "dsa": lambda: dsa.generate_private_key(1024),
        }[kind]()
        public = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
    encryption = (serialization.BestAvailableEncryption(passphrase) if passphrase
                  else serialization.NoEncryption())
    path = tmp_path / f"{kind}.pem"
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, encryption))
    return str(path), public.split()[1].decode("ascii")


class TestPkcs8Keys:
    """openssl genpkey and ssh-keygen -m PKCS8 write PKCS#8, which paramiko does not read."""

    @pytest.mark.parametrize("kind", ["rsa", "ed25519", "ecdsa"])
    @pytest.mark.parametrize("passphrase", [None, b"right"], ids=["plain", "encrypted"])
    def test_the_key_loads(self, tmp_path, kind, passphrase):
        path, public = _pkcs8_key_file(tmp_path, kind, passphrase)
        loaded = load_private_key(path, passphrase.decode() if passphrase else "")
        assert loaded is not None
        assert loaded.get_base64() == public

    def test_a_passphrase_given_for_a_plain_key_is_ignored(self, tmp_path):
        # as paramiko ignores it for a plain OpenSSH key
        path, public = _pkcs8_key_file(tmp_path, "rsa", None)
        assert load_private_key(path, "typed anyway").get_base64() == public

    def test_the_passphrase_is_named(self, tmp_path):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import (
            PASSPHRASE_NEEDED, PASSPHRASE_WRONG, unloadable_key_reason
        )

        path, _public = _pkcs8_key_file(tmp_path, "ed25519", b"right")
        assert load_private_key(path, "wrong") is None
        assert unloadable_key_reason(path, "wrong") == PASSPHRASE_WRONG
        assert load_private_key(path, "") is None
        assert unloadable_key_reason(path, "") == PASSPHRASE_NEEDED

    @pytest.mark.parametrize("passphrase", [None, b"right"], ids=["plain", "encrypted"])
    def test_a_type_paramiko_cannot_use_is_still_unsupported(self, tmp_path, passphrase):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import UNSUPPORTED_KEY, unloadable_key_reason

        path, _public = _pkcs8_key_file(tmp_path, "dsa", passphrase)
        typed = passphrase.decode() if passphrase else ""
        assert load_private_key(path, typed) is None
        assert unloadable_key_reason(path, typed) == UNSUPPORTED_KEY


class TestPuttyKeys:
    """paramiko reads no PuTTY key; the login form offered .ppk and then called it invalid."""

    _PPK = ("PuTTY-User-Key-File-3: ssh-ed25519\nEncryption: none\nComment: laptop\n"
            "Public-Lines: 1\nAAAAC3NzaC1lZDI1NTE5AAAAIA==\nPrivate-Lines: 1\nAAAAIA==\n"
            "Private-MAC: 00\n")

    @pytest.mark.parametrize("typed", ["", "a passphrase"])
    def test_the_user_is_told_to_export_it_as_openssh(self, tmp_path, typed):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_key_loader import PUTTY_KEY, unloadable_key_reason

        path = tmp_path / "laptop.ppk"
        path.write_text(self._PPK, encoding="ascii")
        assert load_private_key(str(path), typed) is None
        assert unloadable_key_reason(str(path), typed) == PUTTY_KEY

    def test_the_login_form_does_not_offer_it(self):
        from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict
        from pybreeze.extend_multi_language.extend_traditional_chinese import (
            pybreeze_traditional_chinese_word_dict,
        )

        for words in (pybreeze_english_word_dict, pybreeze_traditional_chinese_word_dict):
            assert ".ppk" not in words["ssh_login_widget_placeholder_private_key"]


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

from __future__ import annotations

import stat
from unittest.mock import MagicMock

import pytest

from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as sftp_mod
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_file_viewer_widget import (
    SSHFileTreeManager,
    SSH_KEEPALIVE_SECONDS,
    SFTPClientWrapper,
    format_size,
    natural_key,
    remote_join,
)


class TestKeepalive:
    def test_connect_enables_keepalive(self, monkeypatch):
        wrapper = SFTPClientWrapper.__new__(SFTPClientWrapper)
        wrapper._ssh = None
        wrapper._sftp = None

        transport = MagicMock()
        fake_ssh = MagicMock()
        fake_ssh.get_transport.return_value = transport
        monkeypatch.setattr(sftp_mod.paramiko, "SSHClient", lambda: fake_ssh)
        monkeypatch.setattr(sftp_mod, "apply_host_key_policy", lambda client, parent: None)

        wrapper.connect("host", 22, "user", "pw")

        transport.set_keepalive.assert_called_once_with(SSH_KEEPALIVE_SECONDS)


class _Entry:
    def __init__(self, filename: str, is_dir: bool):
        self.filename = filename
        self.st_mode = (stat.S_IFDIR if is_dir else stat.S_IFREG) | 0o644


class TestNaturalKey:
    def test_numbers_compare_as_integers(self):
        names = ["img10.png", "img2.png", "img1.png", "img100.png"]
        assert sorted(names, key=natural_key) == [
            "img1.png", "img2.png", "img10.png", "img100.png",
        ]

    def test_case_insensitive(self):
        assert sorted(["beta", "Alpha", "gamma"], key=natural_key) == ["Alpha", "beta", "gamma"]

    @pytest.mark.parametrize("name", ["²³", "①②", "file².txt"])
    def test_non_decimal_digit_chars_do_not_crash(self, name):
        # Regression (found by fuzzing): superscript/circled "digits" are
        # str.isdigit() but int() rejects them; natural_key must not crash.
        assert isinstance(natural_key(name), list)


class TestFormatSize:
    @pytest.mark.parametrize("num_bytes,expected", [
        (0, "0 B"),
        (512, "512 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1048576, "1.0 MB"),
        (1073741824, "1.0 GB"),
        (1099511627776, "1.0 TB"),
    ])
    def test_human_readable(self, num_bytes, expected):
        assert format_size(num_bytes) == expected

    def test_negative_is_blank(self):
        assert format_size(-1) == ""


class TestSortEntries:
    def test_directories_first_then_natural_order(self):
        entries = [
            _Entry("file10.txt", is_dir=False),
            _Entry("zeta_dir", is_dir=True),
            _Entry("file2.txt", is_dir=False),
            _Entry("alpha_dir", is_dir=True),
        ]
        ordered = [name for name, _ in SSHFileTreeManager._sort_entries(entries)]
        # directories first (natural/case-insensitive), then files (natural)
        assert ordered == ["alpha_dir", "zeta_dir", "file2.txt", "file10.txt"]


class TestRemoteJoin:
    @pytest.mark.parametrize("directory,name,expected", [
        ("/", "home", "/home"),
        ("/home/user", "file.txt", "/home/user/file.txt"),
        ("", "x", "/x"),
        ("/a/b", "c", "/a/b/c"),
        ("/dir", "name with spaces.txt", "/dir/name with spaces.txt"),
    ])
    def test_joins_with_posix_separators(self, directory, name, expected):
        assert remote_join(directory, name) == expected

    def test_never_emits_backslash(self):
        # Regression: os.path.join produced '\\' on Windows and broke remote nav.
        result = remote_join("/home/user", "sub")
        assert "\\" not in result
        assert result == "/home/user/sub"

    def test_result_is_always_absolute(self):
        assert remote_join("relative/dir", "f").startswith("/")


class TestConnectIsAtomic:
    def test_open_sftp_failure_tears_down_ssh(self, monkeypatch):
        # If open_sftp() fails after the SSH transport is up, connect() must not
        # leak the half-open transport: it should close it and re-raise.
        wrapper = SFTPClientWrapper.__new__(SFTPClientWrapper)
        wrapper.word_dict = {}
        wrapper._ssh = None
        wrapper._sftp = None
        wrapper.root_path = "/"

        closed = {"ssh": False}

        class _SSH:
            def connect(self, **kwargs):
                pass

            def get_transport(self):
                return MagicMock()

            def open_sftp(self):
                raise OSError("sftp subsystem disabled")

            def close(self):
                closed["ssh"] = True

        monkeypatch.setattr(sftp_mod.paramiko, "SSHClient", _SSH)
        monkeypatch.setattr(sftp_mod, "apply_host_key_policy", lambda client, parent: None)

        with pytest.raises(OSError):
            wrapper.connect("host", 22, "user", "pw")

        assert closed["ssh"] is True
        assert wrapper._ssh is None

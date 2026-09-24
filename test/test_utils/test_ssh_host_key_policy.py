"""An unknown SSH host key: asked about once per Connect, and never written away."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading

import paramiko
import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_host_key_policy as policy_mod


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture(scope="module")
def keys():
    return paramiko.RSAKey.generate(1024), paramiko.RSAKey.generate(1024)


@pytest.fixture()
def asked(app, tmp_path, monkeypatch):
    """Answers every question with ``asked["answer"]`` and counts them."""
    state = {"answer": True, "count": 0}

    class Asker:
        def ask(self, _parent, _title, _message) -> bool:
            state["count"] += 1
            return state["answer"]

    monkeypatch.setattr(policy_mod, "pybreeze_data_dir", lambda: tmp_path)
    monkeypatch.setattr(policy_mod, "host_key_asker", Asker)
    monkeypatch.setattr(policy_mod, "_RECENT_DECLINES", {})
    return state


def _meet(hostname: str, key) -> paramiko.SSHClient:
    """What a connect does on meeting *key*: the client read the file at its Connect."""
    client = paramiko.SSHClient()
    policy_mod.InteractiveHostKeyPolicy().missing_host_key(client, hostname, key)
    return client


def test_both_halves_of_one_connect_ask_once(asked, keys):
    # The shell and the file tree each met the unknown key; there used to be
    # two identical questions, one on top of the other.
    _meet("host.example", keys[0])
    second = _meet("host.example", keys[0])

    assert asked["count"] == 1
    assert second.get_host_keys().lookup("host.example")


def test_a_no_is_not_asked_again_by_the_other_half(asked, keys):
    asked["answer"] = False

    for _ in range(2):
        with pytest.raises(paramiko.SSHException):
            _meet("host.example", keys[0])

    assert asked["count"] == 1


def test_two_tabs_accepting_two_hosts_keep_both(asked, keys):
    # Each client saved its own copy of the file, read at its Connect, so the
    # last one to save wrote the other host away.
    first, second = paramiko.SSHClient(), paramiko.SSHClient()
    policy = policy_mod.InteractiveHostKeyPolicy()
    policy.missing_host_key(first, "one.example", keys[0])
    policy.missing_host_key(second, "two.example", keys[1])

    known = paramiko.HostKeys(str(policy_mod._known_hosts_path()))
    assert known.lookup("one.example") and known.lookup("two.example")


def test_another_key_for_a_known_host_is_still_asked_about(asked, keys):
    _meet("host.example", keys[0])

    _meet("host.example", keys[1])

    assert asked["count"] == 2


def test_the_questions_come_one_at_a_time(asked, keys, monkeypatch):
    inside = threading.Event()
    release = threading.Event()
    overlapping: list = []

    class SlowAsker:
        def ask(self, *_args) -> bool:
            overlapping.append(inside.is_set())
            inside.set()
            release.wait(5)
            inside.clear()
            return True

    monkeypatch.setattr(policy_mod, "host_key_asker", SlowAsker)
    workers = [threading.Thread(target=_meet, args=(name, keys[0]))
               for name in ("one.example", "two.example")]
    for worker in workers:
        worker.start()
    inside.wait(5)
    release.set()
    for worker in workers:
        worker.join(5)

    assert overlapping == [False, False]


class TestAQuestionNobodyCanAnswer:
    """A closed panel's question is a No, never the previous question's answer."""

    def _closed_panel(self):
        import shiboken6
        from PySide6.QtWidgets import QWidget

        panel = QWidget()
        shiboken6.delete(panel)
        return panel

    def test_on_the_ui_thread(self, app):
        # The previous Yes used to come back, and the key was stored for good
        asker = policy_mod.HostKeyAsker()
        asker._answer = True

        assert asker.ask(self._closed_panel(), "title", "message") is False

    def test_from_the_connecting_thread(self, app):
        import time

        asker = policy_mod.HostKeyAsker()
        asker._answer = True
        panel = self._closed_panel()
        answers: list = []
        worker = threading.Thread(target=lambda: answers.append(asker.ask(panel, "title", "message")))
        worker.start()
        deadline = time.monotonic() + 10
        while worker.is_alive() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        worker.join(1)

        assert answers == [False]


def test_a_store_that_fails_keeps_the_hosts_already_trusted(asked, keys, tmp_path, monkeypatch):
    # HostKeys.save emptied the file first: a failure part-way lost every host
    from pybreeze.utils.file_process import replace_file

    _meet("first.example", keys[0])
    before = (tmp_path / "ssh_known_hosts").read_text(encoding="utf-8")

    def refuse(*_args):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(replace_file.os, "replace", refuse)
    _meet("second.example", keys[1])

    assert (tmp_path / "ssh_known_hosts").read_text(encoding="utf-8") == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["ssh_known_hosts"]


# A line whose key is not base64: HostKeys.load raised InvalidHostKey, no SSHException
_BAD_LINE = "badhost ssh-ed25519 abc"
# A line paramiko 4 no longer reads (it dropped DSA), which is still someone's host
_DSA_LINE = "old.example ssh-dss AAAAB3NzaC1kc3MAAACBAP=="


def test_a_bad_line_skips_that_line_and_the_rest_still_load(asked, keys, tmp_path):
    good = paramiko.hostkeys.HostKeyEntry(["good.example"], keys[0]).to_line().strip()
    (tmp_path / "ssh_known_hosts").write_text(f"{_BAD_LINE}\n{good}\n", encoding="utf-8")
    client = paramiko.SSHClient()

    policy_mod.apply_host_key_policy(client, None)

    assert client.get_host_keys().lookup("good.example")["ssh-rsa"] == keys[0]
    assert client.get_host_keys().lookup("badhost") is None


def test_accepting_a_host_keeps_the_lines_paramiko_could_not_read(asked, keys, tmp_path):
    (tmp_path / "ssh_known_hosts").write_text(f"{_BAD_LINE}\n{_DSA_LINE}\n", encoding="utf-8")

    _meet("new.example", keys[0])

    lines = (tmp_path / "ssh_known_hosts").read_text(encoding="utf-8").splitlines()
    assert lines[:2] == [_BAD_LINE, _DSA_LINE]
    assert policy_mod._read_known_hosts().lookup("new.example")["ssh-rsa"] == keys[0]


def test_accepting_a_host_keeps_bytes_that_are_not_utf8(asked, keys, tmp_path):
    # The file was decoded with replacement and written back: \xe9 became U+FFFD
    (tmp_path / "ssh_known_hosts").write_bytes(b"# caf\xe9\n")

    _meet("new.example", keys[0])

    assert (tmp_path / "ssh_known_hosts").read_bytes().startswith(b"# caf\xe9\n")


def test_a_file_that_cannot_be_read_is_not_written_over(asked, keys, tmp_path, monkeypatch):
    # Read as empty, it was replaced by the one new line: every host trusted so far gone
    from pathlib import Path

    known = tmp_path / "ssh_known_hosts"
    known.write_bytes(b"trusted.example ssh-ed25519 AAAA\n")
    real_read = Path.read_bytes

    def locked(self):
        if self == known:
            raise PermissionError(13, "locked")
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", locked)
    _meet("new.example", keys[0])
    monkeypatch.setattr(Path, "read_bytes", real_read)

    assert known.read_bytes() == b"trusted.example ssh-ed25519 AAAA\n"

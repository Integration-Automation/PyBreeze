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


@pytest.fixture
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
    assert known.lookup("one.example")
    assert known.lookup("two.example")


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


def test_there_is_one_asker_made_on_first_use(app, monkeypatch):
    # The SSH panels call it as they are built, on the UI thread, so a connect
    # thread asking later finds it living where a box can be shown
    monkeypatch.setattr(policy_mod, "_ASKER", None)

    first = policy_mod.host_key_asker()

    assert isinstance(first, policy_mod.HostKeyAsker)
    assert policy_mod.host_key_asker() is first
    assert first.thread() is app.thread()


class TestTheQuestionBoxItself:
    """The other tests stand in for the asker; here its message box is only kept from showing."""

    @pytest.mark.parametrize(("pressed", "trusted"), [("Yes", True), ("No", False)])
    def test_only_yes_trusts_the_key(self, app, monkeypatch, pressed, trusted):
        from PySide6.QtWidgets import QMessageBox

        seen: list = []

        def answer(box):
            buttons = box.standardButtons()
            no_is_the_default = box.defaultButton() is box.button(QMessageBox.StandardButton.No)
            seen.append((box.windowTitle(), box.text(), buttons, no_is_the_default))
            return getattr(QMessageBox.StandardButton, pressed)

        monkeypatch.setattr(policy_mod.QMessageBox, "exec", answer)

        from pybreeze.pybreeze_ui.plain_text import as_text

        message = "fingerprint <b>SHA256:x</b>"
        assert policy_mod.HostKeyAsker().ask(None, "Unknown host", message) is trusted
        # Yes and No only, the focus starting on No, the message shown as text, not markup
        yes_or_no = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        assert seen == [("Unknown host", as_text(message), yes_or_no, True)]

    def test_the_panel_that_asked_gets_the_box(self, app, monkeypatch):
        # Only a panel that has been closed goes without; an open one is asked on
        from PySide6.QtWidgets import QMessageBox, QWidget

        owners: list = []

        def answer(box):
            owners.append(box.parent())
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(policy_mod.QMessageBox, "exec", answer)
        panel = QWidget()

        assert policy_mod.HostKeyAsker().ask(panel, "Unknown host", "message") is True
        assert owners == [panel]
        panel.deleteLater()


@pytest.mark.parametrize("start", [5.0, 1000.0])
def test_a_no_is_remembered_for_ten_seconds_and_then_forgotten(asked, keys, monkeypatch, start):
    # From 5 as well: 1010.5 % 1000 is 10.5 too, so from 1000 alone a remainder passed for the difference
    now = [start]
    monkeypatch.setattr(policy_mod.time, "monotonic", lambda: now[0])
    asked["answer"] = False

    with pytest.raises(paramiko.SSHException):
        _meet("host.example", keys[0])
    now[0] += 9.5
    with pytest.raises(paramiko.SSHException):
        _meet("host.example", keys[0])
    assert asked["count"] == 1  # still the same Connect's other half: not asked
    now[0] += 1.0
    with pytest.raises(paramiko.SSHException):
        _meet("host.example", keys[0])

    assert asked["count"] == 2  # asked again: a later Connect is a new question


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


def test_a_bad_line_skips_that_line_and_the_rest_still_load(asked, keys, tmp_path, caplog):
    good = paramiko.hostkeys.HostKeyEntry(["good.example"], keys[0]).to_line().strip()
    (tmp_path / "ssh_known_hosts").write_text(f"# trusted hosts\n{_BAD_LINE}\n{good}\n", encoding="utf-8")
    client = paramiko.SSHClient()

    with caplog.at_level("WARNING", logger="Pybreeze"):
        policy_mod.apply_host_key_policy(client, None)

    assert client.get_host_keys().lookup("good.example")["ssh-rsa"] == keys[0]
    assert client.get_host_keys().lookup("badhost") is None
    # The log names the line as an editor numbers it, and only that line
    skipped = [record.getMessage() for record in caplog.records if "of ssh_known_hosts" in record.getMessage()]
    assert skipped == ["Skipping line 2 of ssh_known_hosts: InvalidHostKey"]


def test_the_first_host_trusted_is_the_file_s_first_line(asked, keys, tmp_path):
    _meet("host.example", keys[0])

    assert (tmp_path / "ssh_known_hosts").read_bytes().startswith(b"host.example ")


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


def test_a_file_without_a_last_newline_keeps_its_last_host(asked, keys):
    # Written straight after it, the new key would join the last line and spoil both
    _meet("first.example", keys[0])
    path = policy_mod._known_hosts_path()
    path.write_bytes(path.read_bytes().rstrip(b"\n"))

    _meet("second.example", keys[1])

    known = policy_mod._read_known_hosts()
    assert known.lookup("first.example")["ssh-rsa"] == keys[0]
    assert known.lookup("second.example")["ssh-rsa"] == keys[1]


class TestAKeyOtherThanTheTrustedOne:
    """paramiko refuses it on its own; the message says what it may mean and where the trust is kept."""

    def test_trusted_here_names_pybreeze_s_file(self, asked, keys):
        _meet("host.example", keys[0])

        message = policy_mod.changed_host_key_message(
            paramiko.BadHostKeyException("host.example", keys[1], keys[0]))

        assert message == policy_mod.host_key_changed_error.format(
            hostname="host.example", fingerprint=policy_mod._fingerprint_sha256(keys[1]),
            trusted=policy_mod._fingerprint_sha256(keys[0]), known_hosts=policy_mod._known_hosts_path())
        assert "AAAA" not in message  # no key in base64, as paramiko gave them

    def test_trusted_on_another_port_names_pybreeze_s_file(self, asked, keys):
        _meet("[host.example]:2222", keys[0])

        message = policy_mod.changed_host_key_message(
            paramiko.BadHostKeyException("host.example", keys[1], keys[0]))

        assert message.endswith(f"remove its line from {policy_mod._known_hosts_path()} and connect again.")

    @pytest.mark.parametrize("trusted_here", [
        [],  # PyBreeze's file holds nothing for the host
        [("host.example.org", 0)],  # the same key, but for another name
        [("host.example", 1)],  # another key for the host (an older one, not the one it failed)
    ])
    def test_trusted_elsewhere_names_the_system_file(self, asked, keys, trusted_here):
        from pathlib import Path

        for name, key in trusted_here:
            _meet(name, keys[key])

        message = policy_mod.changed_host_key_message(
            paramiko.BadHostKeyException("host.example", keys[1], keys[0]))

        assert message.endswith(f"remove its line from {Path.home() / '.ssh' / 'known_hosts'} and connect again.")


class TestThePanelThatAsked:
    def test_its_question_carries_the_panel(self, asked, keys, monkeypatch):
        from PySide6.QtWidgets import QWidget

        parents: list = []

        class Asker:
            def ask(self, parent, _title, _message) -> bool:
                parents.append(parent)
                return False

        monkeypatch.setattr(policy_mod, "host_key_asker", Asker)
        panel = QWidget()
        policy = policy_mod.InteractiveHostKeyPolicy(panel)
        client = paramiko.SSHClient()
        with pytest.raises(paramiko.SSHException):  # the answer was No
            policy.missing_host_key(client, "host.example", keys[0])

        assert parents == [panel]
        panel.deleteLater()

    def test_a_panel_closed_before_the_question_is_a_no(self, asked, keys):
        import gc

        from PySide6.QtWidgets import QWidget

        panel = QWidget()
        policy = policy_mod.InteractiveHostKeyPolicy(panel)
        del panel
        gc.collect()

        client = paramiko.SSHClient()
        with pytest.raises(paramiko.SSHException):
            policy.missing_host_key(client, "host.example", keys[0])
        assert asked["count"] == 0  # nobody was asked on its behalf

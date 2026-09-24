"""What the shell sends, shown as it was sent: reads may stop anywhere."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paramiko
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_command_widget
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import (
    SSHCommandWidget,
    SSHReaderThread,
    TerminalDecoder,
)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class TestTerminalDecoder:
    @pytest.mark.parametrize("cut", range(1, 6))
    def test_a_character_cut_between_reads_is_joined(self, cut):
        data = "中文".encode("utf-8")  # six bytes, two characters
        decoder = TerminalDecoder()

        assert decoder.feed(data[:cut]) + decoder.feed(data[cut:]) == "中文"

    @pytest.mark.parametrize("cut", range(1, 5))
    def test_an_escape_cut_between_reads_is_still_removed(self, cut):
        data = b"\x1b[31mred"
        decoder = TerminalDecoder()

        assert decoder.feed(data[:cut]) + decoder.feed(data[cut:]) == "red"

    @pytest.mark.parametrize("data", [b"\x1b(Bok", b"\x1b]0;title\x1b\\ok", b"\x1bP1$r0m\x1b\\ok"])
    def test_a_character_set_or_string_escape_cut_anywhere_is_removed(self, data):
        # A read ending between the ESC and the backslash of ST showed "\ok"
        for cut in range(1, len(data) - 2):
            decoder = TerminalDecoder()

            assert decoder.feed(data[:cut]) + decoder.feed(data[cut:]) == "ok", cut

    def test_text_before_an_unfinished_escape_is_shown_now(self):
        decoder = TerminalDecoder()

        assert decoder.feed(b"ready \x1b[") == "ready "
        assert decoder.feed(b"0mgo") == "go"

    def test_a_very_long_unterminated_sequence_is_not_held_forever(self):
        decoder = TerminalDecoder()
        title = b"\x1b]0;" + b"t" * 400

        decoder.feed(title)

        assert decoder._pending == ""

    def test_reset_forgets_what_was_carried_over(self):
        decoder = TerminalDecoder()
        decoder.feed("中".encode("utf-8")[:2])
        decoder.feed(b"\x1b[")

        decoder.reset()

        assert decoder.feed(b"plain") == "plain"


class TestTheTerminal:
    def _widget(self):
        return SSHCommandWidget()

    def test_reads_continue_the_line_they_belong_to(self, app):
        widget = self._widget()

        for chunk in (b"ab", b"cd\r\n", b"ef"):
            widget._on_data(chunk)

        assert widget.terminal.toPlainText() == "abcd\nef"
        widget.close()

    def test_a_backspace_takes_back_what_an_earlier_read_showed(self, app):
        # A spinner's frames in separate reads showed "|/-done"
        widget = self._widget()

        for chunk in (b"line\r\n", b"|", b"\x08/", b"\x08\x1b[1m-", b"\x08\x08\x08done\r\n"):
            widget._on_data(chunk)

        assert widget.terminal.toPlainText() == "line\ndone\n"
        widget.close()

    def test_a_line_ending_cut_between_reads_is_one_line_break(self, app):
        # "\r" at the end of one read and "\n" at the start of the next were
        # two paragraph breaks: a blank line in long output
        widget = self._widget()

        for chunk in (b"line1\r", b"\nline2\r\n"):
            widget._on_data(chunk)

        assert widget.terminal.toPlainText() == "line1\nline2\n"
        widget.close()

    def test_a_notice_starts_on_a_line_of_its_own(self, app):
        widget = self._widget()
        widget._on_data(b"$ ")

        widget.append_text("Disconnecting\n")

        assert widget.terminal.toPlainText() == "$ \nDisconnecting\n"
        widget.close()

    def test_a_notice_after_a_finished_line_adds_no_blank_line(self, app):
        widget = self._widget()
        widget._on_data(b"done\r\n")

        widget.append_text("Disconnecting\n")

        assert widget.terminal.toPlainText() == "done\nDisconnecting\n"
        widget.close()


class FakeChannel:
    """A channel whose shell has exited with output still buffered."""

    closed = False

    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    def recv_ready(self) -> bool:
        return bool(self.chunks)

    def recv(self, _size: int) -> bytes:
        return self.chunks.pop(0)

    def recv_stderr_ready(self) -> bool:
        return False

    def exit_status_ready(self) -> bool:
        return True


class TestTheReader:
    def test_output_buffered_when_the_shell_exits_is_not_lost(self, app):
        reader = SSHReaderThread(FakeChannel([b"last ", b"words"]))
        received: list[bytes] = []
        reader.data_received.connect(received.append)

        reader.run()  # on this thread: direct connections

        assert b"".join(received) == b"last words"


class PartialSendChannel:
    """Takes at most one packet per send, as paramiko's Channel.send does."""

    closed = False
    sendall = paramiko.Channel.sendall

    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.timeouts: list = []

    def send(self, data) -> int:
        chunk = bytes(data[:32704])
        self.sent.append(chunk)
        return len(chunk)

    def settimeout(self, timeout) -> None:
        self.timeouts.append(timeout)


class TestSendingACommand:
    def test_a_long_command_arrives_whole_as_utf8(self, app):
        # Past one packet the rest and the newline were dropped, and a str was
        # counted in characters, not the bytes that go out
        widget = SSHCommandWidget()
        channel = PartialSendChannel()
        widget.shell_channel = channel
        # 20,005 characters (within QLineEdit's 32,767), 60,006 bytes: two packets
        command = "echo " + "中文" * 10000
        widget.command_input_edit.setText(command)

        widget.send_command()

        assert b"".join(channel.sent) == (command + "\n").encode("utf-8")
        assert channel.timeouts == [5, 0.0]
        assert widget.command_input_edit.text() == ""
        widget.shell_channel = None
        widget.close()

    def test_an_empty_line_sends_enter(self, app):
        # It sent nothing, so a prompt's default ("[Y/n]", "Press Enter to
        # continue") could not be taken
        widget = SSHCommandWidget()
        channel = PartialSendChannel()
        widget.shell_channel = channel

        widget.send_command()

        assert channel.sent == [b"\n"]
        widget.shell_channel = None
        widget.close()

    def test_interrupt_sends_ctrl_c_and_keeps_the_line(self, app):
        # A ping or tail -f could only be stopped by disconnecting
        widget = SSHCommandWidget()
        channel = PartialSendChannel()
        widget.shell_channel = channel
        widget.command_input_edit.setText("half typed")

        widget.interrupt_button.click()

        assert channel.sent == [b"\x03"]
        assert widget.command_input_edit.text() == "half typed"
        widget.shell_channel = None
        widget.close()

    def test_ctrl_c_in_the_command_line_interrupts(self, app):
        widget = SSHCommandWidget()
        channel = PartialSendChannel()
        widget.shell_channel = channel
        widget.command_input_edit.setText("ping example.com")

        QTest.keyClick(widget.command_input_edit, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)

        assert channel.sent == [b"\x03"]
        widget.shell_channel = None
        widget.close()

    def test_ctrl_c_on_a_selection_copies_it(self, app):
        widget = SSHCommandWidget()
        channel = PartialSendChannel()
        widget.shell_channel = channel
        widget.command_input_edit.setText("copy me")
        widget.command_input_edit.selectAll()

        QTest.keyClick(widget.command_input_edit, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)

        assert channel.sent == []
        assert QApplication.clipboard().text() == "copy me"
        widget.shell_channel = None
        widget.close()

    def test_interrupt_without_a_session_does_nothing(self, app, monkeypatch):
        widget = SSHCommandWidget()
        asked: list = []
        monkeypatch.setattr(ssh_command_widget.QMessageBox, "information", lambda *args: asked.append(args))

        widget.interrupt_button.click()

        assert asked == []
        widget.close()

    def test_an_empty_line_without_a_session_asks_nothing(self, app, monkeypatch):
        widget = SSHCommandWidget()
        asked: list = []
        monkeypatch.setattr(ssh_command_widget.QMessageBox, "information", lambda *args: asked.append(args))

        widget.send_command()

        assert asked == []
        widget.close()


class _IdleReader:
    """A reader that is never started: the connect message is all that is looked at."""

    def __init__(self, _channel) -> None:
        self.data_received = self.closed = self

    def connect(self, _slot) -> None:
        """No signal is ever sent."""

    def start(self) -> None:
        """Nothing to read."""


class TestTheConnectMessage:
    """It read "Connected to host:22 as user" with " as " in English, and the status "Connected to"."""

    @pytest.mark.parametrize(("host", "shown"), [("example.org", "example.org:22"), ("::1", "[::1]:22")])
    def test_names_the_session_in_the_ide_language(self, app, monkeypatch, host, shown):
        from pybreeze.extend_multi_language.extend_traditional_chinese import (
            pybreeze_traditional_chinese_word_dict as word,
        )
        from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_command_widget as shell_mod
        monkeypatch.setattr(shell_mod, "SSHReaderThread", _IdleReader)
        widget = SSHCommandWidget()
        widget.word_dict = word

        widget._start_shell(object(), host, 22, "alice")

        assert widget.terminal.toPlainText().endswith(f"已以 alice 身分連線至 {shown}\n")
        assert widget.login_widget.status_label.text() == "已連線"
        widget.shell_channel = widget.reader_thread = None
        widget.close()

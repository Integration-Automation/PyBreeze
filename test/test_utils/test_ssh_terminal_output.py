"""What the shell sends, shown as it was sent: reads may stop anywhere."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paramiko
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_command_widget
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import (
    CommandHistory,
    SSHCommandWidget,
    SSHReaderThread,
    TerminalDecoder,
)
from pybreeze.pybreeze_ui.terminal_view import terminal_size
from pybreeze.utils.terminal_style import PLAIN


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _text(output) -> str:
    """What the decoder's output shows, its styles left out."""
    return "".join(text for _style, text in output.pieces)


class TestTerminalDecoder:
    @pytest.mark.parametrize("cut", range(1, 6))
    def test_a_character_cut_between_reads_is_joined(self, cut):
        data = "中文".encode("utf-8")  # six bytes, two characters
        decoder = TerminalDecoder()

        assert _text(decoder.feed(data[:cut])) + _text(decoder.feed(data[cut:])) == "中文"

    @pytest.mark.parametrize("cut", range(1, 5))
    def test_an_escape_cut_between_reads_is_still_removed(self, cut):
        data = b"\x1b[31mred"
        decoder = TerminalDecoder()

        assert _text(decoder.feed(data[:cut])) + _text(decoder.feed(data[cut:])) == "red"

    @pytest.mark.parametrize("data", [b"\x1b(Bok", b"\x1b]0;title\x1b\\ok", b"\x1bP1$r0m\x1b\\ok"])
    def test_a_character_set_or_string_escape_cut_anywhere_is_removed(self, data):
        # A read ending between the ESC and the backslash of ST showed "\ok"
        for cut in range(1, len(data) - 2):
            decoder = TerminalDecoder()

            assert _text(decoder.feed(data[:cut])) + _text(decoder.feed(data[cut:])) == "ok", cut

    def test_text_before_an_unfinished_escape_is_shown_now(self):
        decoder = TerminalDecoder()

        assert _text(decoder.feed(b"ready \x1b[")) == "ready "
        assert _text(decoder.feed(b"0mgo")) == "go"

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

        assert _text(decoder.feed(b"plain")) == "plain"


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

    def test_a_progress_bar_redraws_its_line(self, app):
        # Each "\r" was a line break: one line per step of pip's or wget's bar
        widget = self._widget()

        for chunk in (b"start\r\n", b" 10%\r", b" 20%\r", b"100%\r\n", b"done\r\n"):
            widget._on_data(chunk)

        assert widget.terminal.toPlainText() == "start\n100%\ndone\n"
        widget.close()

    def test_a_rewind_and_its_text_in_one_read_redraw_the_line(self, app):
        widget = self._widget()

        widget._on_data(b"a 10%\r a 20%\r\x1b[Ka100%\r\ndone\r\n")

        assert widget.terminal.toPlainText() == "a100%\ndone\n"
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

    def test_a_read_that_fails_is_said_once_as_the_close(self, app):
        from je_editor import language_wrapper

        class Broken(FakeChannel):
            def recv_ready(self) -> bool:
                raise OSError("socket is closed")

        reader = SSHReaderThread(Broken([]))
        closes: list[str] = []
        reader.closed.connect(closes.append)

        reader.run()

        failed = language_wrapper.language_word_dict.get("ssh_command_widget_error_message_reader_failed")
        assert closes == [f"{failed} socket is closed"]

    def test_a_shell_that_ends_is_said_once_as_the_close(self, app):
        from je_editor import language_wrapper

        reader = SSHReaderThread(FakeChannel([]))
        closes: list[str] = []
        reader.closed.connect(closes.append)

        reader.run()

        assert closes == [language_wrapper.language_word_dict.get("ssh_command_widget_log_message_reader_closed")]


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

    def test_without_a_session_a_typed_command_asks_to_connect(self, app, monkeypatch):
        from je_editor import language_wrapper

        shown: list = []
        monkeypatch.setattr(ssh_command_widget.QMessageBox, "information", lambda *args: shown.append(args[1:]))
        widget = SSHCommandWidget()

        widget.send_command()  # nothing typed: nothing said
        widget.command_input_edit.setText("ls")
        widget.send_command()

        word = language_wrapper.language_word_dict
        assert shown == [(word.get("ssh_command_widget_dialog_title_not_connected"),
                          word.get("ssh_command_widget_dialog_message_not_connected_shell"))]
        assert widget.command_input_edit.text() == "ls"  # kept for when it is connected
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

    def test_up_and_down_bring_back_what_was_sent(self, app):
        widget = SSHCommandWidget()
        widget.shell_channel = PartialSendChannel()
        line = widget.command_input_edit
        for command in ("ls", "pwd"):
            line.setText(command)
            widget.send_command()
        line.setText("half")

        QTest.keyClick(line, Qt.Key.Key_Up)
        assert line.text() == "pwd"
        QTest.keyClick(line, Qt.Key.Key_Up)
        assert line.text() == "ls"
        QTest.keyClick(line, Qt.Key.Key_Down)
        QTest.keyClick(line, Qt.Key.Key_Down)
        assert line.text() == "half"
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

        widget._start_shell(ResizableChannel(), host, 22, "alice")

        assert widget.terminal.toPlainText().endswith(f"已以 alice 身分連線至 {shown}\n")
        assert widget.login_widget.status_label.text() == "已連線"
        widget.shell_channel = widget.reader_thread = None
        widget.close()


class TestCommandHistory:
    def _history(self, *lines: str) -> CommandHistory:
        history = CommandHistory(limit=3)
        for line in lines:
            history.add(line)
        return history

    def test_up_goes_back_and_stops_at_the_oldest(self):
        history = self._history("a", "b")

        assert history.older("") == "b"
        assert history.older("") == "a"
        assert history.older("") is None

    def test_down_past_the_newest_gives_back_what_was_typed(self):
        history = self._history("a", "b")
        history.older("typing")

        assert history.newer() == "typing"
        assert history.newer() is None

    def test_nothing_sent_leaves_nothing_to_walk(self):
        history = self._history()

        assert history.older("x") is None
        assert history.newer() is None

    def test_empty_lines_and_a_repeat_are_not_remembered(self):
        history = self._history("a", "", "a")

        assert history.older("") == "a"
        assert history.older("") is None

    def test_only_the_newest_lines_are_kept(self):
        history = self._history("1", "2", "3", "4")

        assert [history.older(""), history.older(""), history.older(""), history.older("")] == ["4", "3", "2", None]

    def test_sending_goes_back_to_a_new_line(self):
        history = self._history("a", "b")
        history.older("")
        history.older("")

        history.add("a")  # sent again from the history

        assert history.older("") == "a"
        assert history.older("") == "b"


class ResizableChannel:
    """Records the pty sizes it is given."""

    closed = False

    def __init__(self, error: Exception | None = None) -> None:
        self.sizes: list[tuple[int, int]] = []
        self.error = error

    def resize_pty(self, width: int, height: int) -> None:
        if self.error is not None:
            raise self.error
        self.sizes.append((width, height))


class TestThePtySize:
    @staticmethod
    def _shown(app, channel) -> SSHCommandWidget:
        widget = SSHCommandWidget()
        widget.resize(900, 600)
        widget.show()
        QApplication.processEvents()
        widget.shell_channel = channel
        return widget

    @staticmethod
    def _resize(widget: SSHCommandWidget, width: int) -> None:
        widget.resize(width, 600)
        QApplication.processEvents()

    def test_the_pty_follows_the_view(self, app):
        # It stayed at 120 columns whatever the view's width
        channel = ResizableChannel()
        widget = self._shown(app, channel)

        self._resize(widget, 500)

        assert channel.sizes[-1] == terminal_size(widget.terminal)
        assert channel.sizes[-1][0] < 120 - 40
        widget.shell_channel = None
        widget.close()

    def test_a_resize_within_a_column_sends_nothing(self, app):
        channel = ResizableChannel()
        widget = self._shown(app, channel)
        self._resize(widget, 500)
        sent = len(channel.sizes)

        self._resize(widget, 501)

        assert len(channel.sizes) == sent
        widget.shell_channel = None
        widget.close()

    def test_without_a_session_nothing_is_sent(self, app):
        widget = self._shown(app, None)

        self._resize(widget, 500)  # no channel to give it to: nothing raised

        widget.close()

    def test_a_resize_the_server_refuses_is_not_raised(self, app):
        widget = self._shown(app, ResizableChannel(OSError("link down")))

        self._resize(widget, 500)

        assert widget._pty_size != terminal_size(widget.terminal)  # tried again next time
        widget.shell_channel = None
        widget.close()

    def test_the_shell_opens_at_the_view_size(self, app):
        options = {}

        class Client:
            @staticmethod
            def get_transport():
                return None

            @staticmethod
            def invoke_shell(**given):
                options.update(given)
                return paramiko.Channel(0)

        ssh_command_widget.open_shell_channel(Client(), (77, 21))

        assert (options["width"], options["height"]) == (77, 21)


def _colour_at(widget: SSHCommandWidget, position: int):
    cursor = widget.terminal.textCursor()
    cursor.setPosition(position + 1)  # the format of the character before the cursor
    return cursor.charFormat().foreground().color()


class TestColours:
    def test_output_shows_the_colours_it_asks_for(self, app):
        # They were removed: ls --color, git and grep came out all one colour
        widget = SSHCommandWidget()

        widget._on_data(b"\x1b[31mred\x1b[0m plain")

        assert widget.terminal.toPlainText() == "red plain"
        assert _colour_at(widget, 0) == QColor(205, 49, 49)
        assert _colour_at(widget, 4) != QColor(205, 49, 49)
        widget.close()

    def test_a_colour_carries_over_to_the_next_read(self, app):
        widget = SSHCommandWidget()

        widget._on_data(b"\x1b[31mr")
        widget._on_data(b"ed")

        assert _colour_at(widget, 2) == QColor(205, 49, 49)  # the same on any background
        widget.close()

    def test_a_new_session_starts_without_the_last_one_colour(self, app):
        decoder = TerminalDecoder()
        decoder.feed(b"\x1b[31m")

        decoder.reset()

        assert decoder.feed(b"plain").pieces == [(PLAIN, "plain")]

    @pytest.mark.parametrize("chunks", [
        [b"50%\r\x1b[32m60%"],
        [b"50%\r\x1b[32m", b"60%"],
    ])
    def test_a_bar_that_changes_colour_still_redraws_its_line(self, app, chunks):
        widget = SSHCommandWidget()

        for chunk in chunks:
            widget._on_data(chunk)

        assert widget.terminal.toPlainText() == "60%"
        widget.close()

    def test_a_line_ending_around_a_colour_reset_is_one_line_break(self, app):
        widget = SSHCommandWidget()

        widget._on_data(b"a\r\x1b[0m\nb")

        assert widget.terminal.toPlainText() == "a\nb"
        widget.close()


class TestWhatTheOtherPathsDo:
    """The reader's error stream, a send that fails, Disconnect, and the shell being opened."""

    def test_the_error_stream_reaches_the_terminal_too(self, app):
        class ErrorsOnly(FakeChannel):
            def __init__(self) -> None:
                super().__init__([])
                self.errors = [b"ls: cannot access 'x'"]

            def recv_stderr_ready(self) -> bool:
                return bool(self.errors)

            def recv_stderr(self, _size: int) -> bytes:
                return self.errors.pop(0)

        reader = SSHReaderThread(ErrorsOnly())
        received: list[bytes] = []
        reader.data_received.connect(received.append)

        reader.run()

        assert received == [b"ls: cannot access 'x'"]

    def test_a_send_that_fails_says_so_and_keeps_the_line(self, app):
        class Dropped(PartialSendChannel):
            def send(self, data) -> int:
                raise OSError("Socket is closed")

        widget = SSHCommandWidget()
        widget.shell_channel = Dropped()
        widget.command_input_edit.setText("uptime")

        widget.send_command()

        assert "Socket is closed" in widget.terminal.toPlainText()
        assert widget.command_input_edit.text() == "uptime"
        widget.shell_channel = None
        widget.close()

    def test_disconnect_closes_the_session_and_says_so(self, app):
        class Closing:
            closed = False

            def close(self) -> None:
                self.closed = True

        widget = SSHCommandWidget()
        channel, client = Closing(), Closing()
        widget.shell_channel, widget.ssh_client = channel, client
        changes: list = []
        widget.state_changed.connect(lambda: changes.append(True))

        widget.disconnect_ssh()

        assert channel.closed
        assert client.closed
        assert widget.shell_channel is None
        assert widget.ssh_client is None
        assert widget.login_widget.status_label.text() == widget.word_dict.get(
            "ssh_command_widget_status_label_disconnected")
        assert changes == [True]
        widget.close()

    def test_the_shell_is_opened_with_keepalive_its_size_and_no_blocking(self):
        calls: list = []

        class Transport:
            def set_keepalive(self, seconds) -> None:
                calls.append(("keepalive", seconds))

        class Channel:
            def settimeout(self, timeout) -> None:
                calls.append(("timeout", timeout))

        class Client:
            def get_transport(self):
                return Transport()

            def invoke_shell(self, **options):
                calls.append(("shell", options))
                return Channel()

        ssh_command_widget.open_shell_channel(Client(), (132, 40))

        assert calls == [
            ("keepalive", ssh_command_widget.SSH_KEEPALIVE_SECONDS),
            ("shell", {"term": "xterm", "width": 132, "height": 40}),
            ("timeout", 0.0),
        ]

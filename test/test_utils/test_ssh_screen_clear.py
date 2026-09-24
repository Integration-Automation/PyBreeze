"""`clear` and `reset` wipe the SSH terminal, as they do a terminal's screen."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import SSHCommandWidget, TerminalDecoder
from pybreeze.utils.terminal_style import PLAIN, TextStyle
from pybreeze.utils.terminal_text import split_at_screen_clear

# What `clear` sends with TERM=xterm: home, erase the screen, erase the scrollback
CLEAR = b"\x1b[H\x1b[2J\x1b[3J"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


class TestSplitAtScreenClear:
    @pytest.mark.parametrize("sequence", ["\x1b[2J", "\x1b[3J", "\x1bc"])
    def test_what_follows_the_last_clear_is_what_is_left(self, sequence):
        assert split_at_screen_clear(f"old{sequence}mid\x1b[2Jnew") == (f"old{sequence}mid", "\x1b[2J", "new")
        assert split_at_screen_clear(f"old{sequence}new") == ("old", sequence, "new")

    @pytest.mark.parametrize("text", ["plain", "\x1b[J prompt redrawn", "\x1b[0J", "\x1b[1J", "\x1b[2K line"])
    def test_erasing_less_than_the_screen_is_not_a_clear(self, text):
        # Shells send ESC [ J to redraw a prompt: that must not wipe the view
        assert split_at_screen_clear(text) is None


class TestTheDecoder:
    def test_a_clear_is_reported_with_only_what_follows_it(self):
        output = TerminalDecoder().feed(b"old output\r\n" + CLEAR + b"$ ")

        assert output.clears_screen
        assert output.pieces == [(PLAIN, "$ ")]

    def test_a_clear_cut_between_reads_is_still_one(self):
        decoder = TerminalDecoder()

        first = decoder.feed(b"old\r\n\x1b[H\x1b[2")
        second = decoder.feed(b"J\x1b[3J$ ")

        assert not first.clears_screen
        assert second.clears_screen
        assert "".join(text for _style, text in second.pieces) == "$ "

    def test_a_colour_set_before_the_clear_carries_on(self):
        output = TerminalDecoder().feed(b"\x1b[31mred" + CLEAR + b"still red")

        assert output.pieces == [(TextStyle(foreground=1), "still red")]

    def test_a_full_reset_drops_the_colour(self):
        output = TerminalDecoder().feed(b"\x1b[31mred\x1bcplain")

        assert output.clears_screen
        assert output.pieces == [(PLAIN, "plain")]


class TestTheTerminal:
    def test_clear_wipes_the_view(self, app):
        # The sequences were removed and nothing else happened: `clear` left
        # everything on the screen
        widget = SSHCommandWidget()
        widget._on_data(b"line 1\r\nline 2\r\n$ clear\r\n")

        widget._on_data(CLEAR + b"$ ")

        assert widget.terminal.toPlainText() == "$ "
        widget.close()

    def test_a_rewind_left_before_the_clear_is_forgotten(self, app):
        widget = SSHCommandWidget()
        widget._on_data(b"50%\r\x1b[32m")  # ends on a rewind still to be applied

        widget._on_data(CLEAR + b"$ ")

        assert widget.terminal.toPlainText() == "$ "
        assert not widget._rewind_pending
        widget.close()

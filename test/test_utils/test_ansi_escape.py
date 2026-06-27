from __future__ import annotations

import pytest

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import ANSI_ESCAPE_PATTERN


def _strip(text: str) -> str:
    return ANSI_ESCAPE_PATTERN.sub("", text)


class TestAnsiEscapeStripping:
    @pytest.mark.parametrize("raw,expected", [
        ("\x1b[31mred\x1b[0m", "red"),                      # SGR colour
        ("\x1b[2J\x1b[H clear", " clear"),                  # cursor / erase
        ("\x1b[1mbold\x1b[22m", "bold"),                    # bold on/off
        ("a\x1bMb", "ab"),                                  # two-char C1 (reverse index)
        ("no escapes here", "no escapes here"),             # plain text untouched
    ])
    def test_csi_and_fe(self, raw, expected):
        assert _strip(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        # OSC terminal-title sequence (BEL terminated) — common in shell prompts.
        ("\x1b]0;user@host:~\x07ls output", "ls output"),
        # OSC hyperlink (ST terminated, ESC backslash).
        ("\x1b]8;;http://example.com\x1b\\link\x1b]8;;\x1b\\ done", "link done"),
        # OSC mixed with colour.
        ("\x1b]0;title\x07\x1b[32mok\x1b[0m", "ok"),
        # Unterminated OSC ended by the next ESC (a CSI), not BEL/ST: the body
        # used to leak as "8;;https://..." text; it must be consumed whole.
        ("\x1b]8;;https://api.github.com/repos\x1b[0mtext", "text"),
        # Unterminated OSC ended by end-of-stream.
        ("before\x1b]0;unterminated title", "before"),
    ])
    def test_osc_sequences_are_stripped(self, raw, expected):
        # Regression: OSC bodies (e.g. "0;title") used to leak through as garbage.
        assert _strip(raw) == expected

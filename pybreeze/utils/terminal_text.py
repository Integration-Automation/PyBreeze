"""Terminal output as text a view can show.

A program writing to a terminal colours its output and moves the cursor with
escape sequences, and rubs characters out with backspaces. A text view shows
them as ``\u2190[31m`` and boxes. Both the SSH terminal and the run window read
such output, in pieces that can end inside a sequence.
"""
from __future__ import annotations

import re

ANSI_ESCAPE_PATTERN = re.compile(
    r'\x1B(?:'
    # A control string -- OSC (titles, links), DCS, SOS, PM, APC -- ended by
    # BEL or ST, or implicitly by the next ESC / the end
    r'[\]PX^_][^\x07\x1B]*(?:\x07|\x1B\\)?'
    r'|\[[0-?]*[ -/]*[@-~]'           # CSI (colours, cursor movement)
    r'|[ -/]+[0-~]'                   # nF: character sets (ESC ( B, from tput sgr0), ESC # 8
    r'|[0-~]'                         # Fp, Fe, Fs: ESC 7 / ESC 8, ESC = / ESC >, ESC M, ESC c
    r')'
)

# Control characters the view cannot show, once the sequences are gone: BEL
# and the rest of C0 but tab, newline and carriage return, and DEL.
# Backspace is applied first (_BACKSPACED)
_CONTROL_CHARACTER = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
# A character and the backspace that takes it back (not across a line break)
_BACKSPACED = re.compile('[^\n\x08]\x08')

# The end of a read that stops inside an escape sequence: a lone ESC, a CSI
# still waiting for its final byte, a control string still waiting for its
# terminator (or the second byte of ST), or a character-set escape still
# waiting for its final byte
_INCOMPLETE_ESCAPE = re.compile(r'\x1B(?:\[[0-?]*[ -/]*|[\]PX^_][^\x07\x1B]*\x1B?|[ -/]+)?\Z')
# Longest such tail held back for the next read; anything longer is shown as is
_MAX_PENDING_ESCAPE = 256


def strip_terminal_controls(text: str) -> str:
    """*text* without escape sequences, with backspaces applied and other controls dropped."""
    text = ANSI_ESCAPE_PATTERN.sub('', text)
    while True:
        applied = _BACKSPACED.sub('', text)
        if applied == text:
            break
        text = applied
    return _CONTROL_CHARACTER.sub('', text)


def split_incomplete_escape(text: str) -> tuple[str, str]:
    """*text* as what can be shown now and the unfinished escape sequence at its end.

    A read ends wherever a buffer did, so it can stop inside a sequence;
    stripped on its own, the sequence's tail showed as text. The unfinished
    part, if any and no longer than ``_MAX_PENDING_ESCAPE``, is returned to be
    put in front of the next read.
    """
    tail = _INCOMPLETE_ESCAPE.search(text)
    if tail is not None and len(text) - tail.start() <= _MAX_PENDING_ESCAPE:
        return text[:tail.start()], text[tail.start():]
    return text, ""


def split_unfinished_end(text: str) -> tuple[str, str]:
    """*text* as what can be shown now and what must wait for the next read.

    That is an unfinished escape sequence (:func:`split_incomplete_escape`)
    and a carriage return just before it or at the very end: the ``\\n`` that
    makes it a line ending, or the text a lone one rewinds over, is still to
    come. Shown alone, a split ``\\r\\n`` made a blank line, and a ``\\r``
    before a cut ``\\x1b[K`` was dropped, so a progress bar was not rewound.
    """
    shown, held = split_incomplete_escape(text)
    if shown.endswith("\r"):
        return shown[:-1], "\r" + held
    return shown, held

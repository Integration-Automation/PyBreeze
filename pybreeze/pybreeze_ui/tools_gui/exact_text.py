"""Read a tool's input exactly as it was typed or pasted.

``toPlainText()`` is for display: it turns every non-breaking space (U+00A0)
into a plain space and a line separator (U+2028) into a newline. A tool that
hashes, diffs, matches or formats the text then works on something else than
the user gave it -- the Hash tool showed the digest of a different string, and
Diff called two texts that differ only there identical.
"""
from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit, QTextEdit

# How QTextDocument separates its blocks in the raw text; the user typed a newline
_BLOCK_SEPARATOR = " "


def exact_text(edit: QTextEdit | QPlainTextEdit) -> str:
    """The text in *edit*, every character as entered, lines ending in ``\\n``."""
    return edit.document().toRawText().replace(_BLOCK_SEPARATOR, "\n")

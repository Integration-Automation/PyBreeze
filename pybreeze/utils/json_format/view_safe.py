"""JSON written so that a Qt text view gives it back as it was.

A tool shows its JSON in a text box, and Copy, Save and Open in editor read it
back from there. Written with ``ensure_ascii=False``, a few characters did not
survive the trip:

- U+2029, U+FDD0 and U+FDD1 are paragraph and frame markers to Qt: they come
  back as a newline, and a newline inside a JSON string is not JSON;
- U+2028 comes back as a newline from ``toPlainText()``, which JEditor saves
  and runs a tab through, and U+0085 is a line break to ``str.splitlines()``;
- a lone surrogate (``"\\ud83d"`` in the input) is dropped.

Written as a ``\\uXXXX`` escape each one means the same character to JSON, and
to a Python string literal, and survives any view.
"""
from __future__ import annotations

import json
import re

# JSON holds none of them outside a string, so each one found is inside one
_NOT_KEPT_BY_A_VIEW = re.compile(
    "[" + "".join(chr(code) for code in (0x85, 0x2028, 0x2029, 0xFDD0, 0xFDD1))
    + chr(0xD800) + "-" + chr(0xDFFF) + "]")


def escape_for_view(json_text: str) -> str:
    """*json_text* with every character a text view would not give back written as its ``\\uXXXX`` escape.

    Only for JSON text, or Python string literals written as JSON, where the
    escape stands for the character itself.
    """
    return _NOT_KEPT_BY_A_VIEW.sub(lambda match: f"\\u{ord(match.group()):04x}", json_text)


def dumps_for_view(value: object, **kwargs) -> str:
    """``json.dumps(value, ensure_ascii=False, **kwargs)``, with :func:`escape_for_view` applied."""
    return escape_for_view(json.dumps(value, ensure_ascii=False, **kwargs))

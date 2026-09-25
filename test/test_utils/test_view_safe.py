"""JSON a tool shows comes back from its text box as the same JSON."""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPlainTextEdit  # noqa: E402 — the platform must be set first

from pybreeze.pybreeze_ui.exact_text import exact_text  # noqa: E402
from pybreeze.utils.json_format.view_safe import dumps_for_view, escape_for_view  # noqa: E402

# What a Qt text view does not give back: U+2029, U+FDD0 and U+FDD1 come back
# as newlines, a lone surrogate not at all; U+2028 turns into a newline in
# toPlainText(), which JEditor saves and runs a tab through; U+0085 is a line
# break to str.splitlines()
NOT_KEPT = "a" + "".join(chr(code) for code in (0x85, 0x2028, 0x2029, 0xFDD0, 0xFDD1, 0xD83D)) + "b"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _through_a_view(text: str) -> str:
    view = QPlainTextEdit()
    view.setPlainText(text)
    return exact_text(view)


def test_every_escaped_character_is_one_a_view_does_not_keep(app):
    # So the list holds nothing a view would have kept anyway; U+0085, which
    # Qt keeps, is escaped as the line break str.splitlines() takes it for
    for character in NOT_KEPT[1:-1].replace(chr(0x85), ""):
        view = QPlainTextEdit()
        view.setPlainText(f"x{character}y")
        assert (exact_text(view), view.toPlainText()) != (f"x{character}y",) * 2, hex(ord(character))


def test_escaped_json_survives_a_view_and_means_the_same(app):
    shown = dumps_for_view({"k": NOT_KEPT}, indent=4)

    assert json.loads(_through_a_view(shown)) == {"k": NOT_KEPT}


def test_other_text_is_left_as_it_is():
    assert escape_for_view('{"k": "café \U0001f600  "}') == '{"k": "café \U0001f600  "}'


def test_as_a_python_string_literal_it_means_the_same():
    assert eval(dumps_for_view(NOT_KEPT)) == NOT_KEPT  # noqa: S307 — the literal this test just wrote


# Each one a view does not keep, and both ends of the surrogate range
@pytest.mark.parametrize("code", [0x85, 0x2028, 0x2029, 0xFDD0, 0xFDD1, 0xD800, 0xDBFF, 0xDC00, 0xDFFF])
def test_each_character_a_view_does_not_keep_is_escaped(code):
    assert escape_for_view(f'"{chr(code)}"') == f'"\\u{code:04x}"'


# The characters just beside them, which a view keeps
@pytest.mark.parametrize("code", [0x84, 0x86, 0x2027, 0x202A, 0xD7FF, 0xE000, 0xFDCF, 0xFDD2])
def test_the_characters_beside_them_are_not(code):
    assert escape_for_view(f'"{chr(code)}"') == f'"{chr(code)}"'


def test_the_rest_is_written_as_it_is_not_escaped():
    assert dumps_for_view({"名稱": "中文 café"}) == '{"名稱": "中文 café"}'


@pytest.mark.parametrize("convert", ["reformat", "minify", "query", "url"])
def test_each_json_tool_output_survives_its_view(app, convert):
    from pybreeze.utils.json_format.json_process import minify_json, reformat_json
    from pybreeze.utils.query_tools.query_convert import query_to_json
    from pybreeze.utils.url_tools.url_convert import url_to_json

    text = NOT_KEPT.replace(chr(0xD83D), "")
    escaped = json.dumps({"k": text})
    output = {
        "reformat": lambda: reformat_json(escaped),
        "minify": lambda: minify_json(escaped),
        "query": lambda: query_to_json("k=" + "".join(f"%{byte:02X}" for byte in text.encode("utf-8"))),
        # The fragment is shown as it was written
        "url": lambda: url_to_json("http://h/p#" + text),
    }[convert]()

    loaded = json.loads(_through_a_view(output))
    assert (loaded["fragment"] if convert == "url" else loaded["k"]) == text

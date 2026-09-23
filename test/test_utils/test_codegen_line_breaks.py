"""A generated script stays the script it was, after a Qt editor has held it.

JEditor saves and runs a tab through ``toPlainText()``, which turns U+2028,
U+2029 and U+0085 into real line breaks. JSON leaves them as they are, so text
after one in a comment became a line of code: a curl command pasted from a page
could run anything in the script it generated.
"""
from __future__ import annotations

import ast
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from pybreeze.utils.curl_import.curl_parser import parse_curl
from pybreeze.utils.curl_import.request_codegen import python_string
from pybreeze.utils.curl_import.script_templates import generate_template
from pybreeze.utils.har_import.har_codegen import generate_har_script

_BREAKS = ["\u2028", "\u2029", "\x85"]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _through_an_editor(code: str) -> str:
    """*code* as JEditor saves or runs it: set in a text edit, read back with toPlainText()."""
    editor = QPlainTextEdit()
    editor.setPlainText(code)
    return editor.toPlainText()


def _raises(code: str) -> bool:
    return any(isinstance(node, ast.Raise) for node in ast.walk(ast.parse(code)))


@pytest.mark.parametrize("line_break", _BREAKS)
def test_a_string_keeps_the_break_as_an_escape(line_break):
    written = python_string(f"a{line_break}b")

    assert line_break not in written
    assert ast.literal_eval(written) == f"a{line_break}b"


@pytest.mark.parametrize("line_break", _BREAKS)
def test_a_cookie_file_name_cannot_add_code(app, line_break):
    request = parse_curl(f'curl https://x.example -b "s{line_break}raise SystemExit(1){line_break}#"')

    code = _through_an_editor(generate_template("requests", request))

    assert not _raises(code)


@pytest.mark.parametrize("line_break", _BREAKS)
def test_a_har_url_cannot_add_code(app, line_break):
    from pybreeze.utils.har_import.har_parser import parse_har

    har = ('{"log": {"entries": [{"request": {"method": "GET", "url": "https://x.example/a'
           + line_break.encode("unicode_escape").decode().replace("\\x85", "\\u0085")
           + 'raise SystemExit(1)", "headers": []}, "response": {"status": 200}}]}}')
    requests = [entry.request for entry in parse_har(har)]

    code = _through_an_editor(generate_har_script("requests", requests))

    assert not _raises(code)

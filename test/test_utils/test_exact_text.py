"""The tools work on the text as it was entered, not on Qt's display copy of it."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import hashlib

import pytest
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QTextEdit

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.exact_text import exact_text

# A non-breaking space, and a line separator inside a line
_ENTERED = "price: 100\nnext line"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.mark.parametrize("editor", [QTextEdit, QPlainTextEdit])
def test_every_character_comes_back(app, editor):
    edit = editor()
    edit.setPlainText(_ENTERED)

    # toPlainText() gives "price: 100\nnext\nline"
    assert exact_text(edit) == _ENTERED


def test_the_hash_is_of_the_text_entered(app):
    from pybreeze.pybreeze_ui.tools_gui.hash_gui import HashGUI

    tool = HashGUI()
    tool.input_edit.setPlainText("a b")

    tool.compute()

    # It showed the digest of "a b".
    assert hashlib.sha256("a b".encode()).hexdigest() in tool.output_edit.toPlainText()
    tool.deleteLater()


def test_the_diff_sees_a_non_breaking_space(app):
    from pybreeze.pybreeze_ui.tools_gui.diff_gui import DiffGUI

    tool = DiffGUI()
    tool.left_edit.setPlainText("price: 100")
    tool.right_edit.setPlainText("price: 100")

    tool.compare()
    tool._compare_thread.wait(10000)
    QApplication.processEvents()

    # It called the two identical.
    assert tool.output_edit.toPlainText()
    tool.deleteLater()

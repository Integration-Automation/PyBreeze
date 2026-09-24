"""A yes-or-no question names its default button, so Enter does not answer Yes by itself.

Given Yes and No and no default, Qt makes Yes the default: Enter, or a key press
meant for the window behind, deleted a file on the SFTP server or in the project,
or dropped the diagram being drawn.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pybreeze

# QMessageBox.question(parent, title, text, buttons, defaultButton)
_DEFAULT_BUTTON_POSITION = 4


def _questions_without_a_default() -> list[str]:
    found = []
    for path in Path(pybreeze.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "question" and ast.unparse(node.func.value) == "QMessageBox"):
                continue
            named = any(keyword.arg == "defaultButton" for keyword in node.keywords)
            if not named and len(node.args) <= _DEFAULT_BUTTON_POSITION:
                found.append(f"{path.name}:{node.lineno}")
    return found


def test_every_question_names_its_default_button():
    assert _questions_without_a_default() == []


def test_the_check_sees_the_questions():
    # Nine questions ask in the package; a check that saw none would pass on anything
    count = sum(
        1 for path in Path(pybreeze.__file__).parent.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "question")
    assert count >= 9

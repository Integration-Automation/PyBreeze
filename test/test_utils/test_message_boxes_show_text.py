"""A message box shows a file name, a path, a host or an error as text, never as markup.

Qt reads markup in a message box's text (``Qt::AutoText``) and loads an
``<img>`` in it. Text that comes from a server or a file -- a reason phrase, a
file name, an ``OSError``'s message -- reached the boxes as it was.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pybreeze

_STATIC_BOXES = {"warning", "critical", "information", "question", "about"}
_BOX_TEXT_SETTERS = {"setText", "setInformativeText", "setDetailedText"}


def _is_plain(node: ast.AST) -> bool:
    """A literal, a word-dict entry as it is, or text already passed through ``as_text``."""
    if isinstance(node, ast.Constant):
        return True
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in ("as_text", "_lang")
    return isinstance(func, ast.Attribute) and func.attr == "get"


def _box_names(tree: ast.AST) -> set[str]:
    """What a ``QMessageBox(...)`` is assigned to: ``msg`` was not seen as a box."""
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == "QMessageBox"):
            names.update(ast.unparse(target) for target in node.targets)
    return names


def _box_texts(tree: ast.AST):
    boxes = _box_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        func = node.func
        receiver = ast.unparse(func.value)
        if (func.attr in _STATIC_BOXES and isinstance(func.value, ast.Name)
                and func.value.id == "QMessageBox" and len(node.args) >= 3):
            yield node.args[2]
        elif func.attr in _BOX_TEXT_SETTERS and node.args and (receiver in boxes or "box" in receiver.lower()):
            yield node.args[0]


def test_a_box_held_by_any_name_is_checked():
    tree = ast.parse("msg = QMessageBox(parent)\nmsg.setText(reason)\n")

    assert [ast.unparse(text) for text in _box_texts(tree)] == ["reason"]


def test_every_message_box_text_is_plain_or_goes_through_as_text():
    unsafe = []
    for path in Path(pybreeze.__file__).parent.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        unsafe += [f"{path.name}:{text.lineno}: {ast.unparse(text)[:80]}"
                   for text in _box_texts(tree) if not _is_plain(text)]
    assert not unsafe, "Message box text not passed through as_text():\n" + "\n".join(unsafe)

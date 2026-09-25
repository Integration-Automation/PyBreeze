"""No PyBreeze Qt class sets an instance attribute that hides a member of its Qt base.

Thirteen tool tabs kept their output buttons in ``self.actions`` and three panels
their worker in ``self.thread``: ``widget.actions()`` and ``widget.thread()``
then gave back that object, not what Qt's own methods return, to anything that
asked -- a plugin, a later helper, JEditor collecting a widget's actions.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

_PACKAGE = Path(__file__).resolve().parents[2] / "pybreeze"


def _self_attributes(node: ast.ClassDef) -> set[str]:
    return {target.attr for sub in ast.walk(node) if isinstance(sub, ast.Assign)
            for target in sub.targets
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
            and target.value.id == "self"}


def _shadowing(module_name: str, node: ast.ClassDef) -> list[str]:
    cls = getattr(importlib.import_module(module_name), node.name, None)
    if not inspect.isclass(cls) or not issubclass(cls, QObject):
        return []
    qt_bases = [base for base in cls.__mro__ if base.__module__.startswith(("PySide6", "Shiboken"))]
    found = []
    for name in sorted(_self_attributes(node)):
        owner = next((base for base in qt_bases if name in vars(base)), None)
        if owner is not None:
            found.append(f"{module_name}.{node.name}: self.{name} hides {owner.__name__}.{name}")
    return found


def test_no_instance_attribute_hides_a_qt_member():
    QApplication.instance() or QApplication([])
    found = []
    for path in sorted(_PACKAGE.rglob("*.py")):
        classes = [node for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                   if isinstance(node, ast.ClassDef)]
        if not classes:
            continue
        module_name = ".".join(path.relative_to(_PACKAGE.parent).with_suffix("").parts)
        for node in classes:
            found += _shadowing(module_name, node)

    assert found == []

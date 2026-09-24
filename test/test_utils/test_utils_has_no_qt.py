"""`pybreeze/utils/` is pure logic: nothing in it imports Qt or JEditor."""
from __future__ import annotations

import ast
from pathlib import Path

import pybreeze.utils

_UTILS = Path(pybreeze.utils.__file__).parent
_UI_PACKAGES = ("PySide6", "je_editor")


def _imported_roots(source: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_module_in_utils_imports_a_ui_package():
    offenders = [
        str(source.relative_to(_UTILS)) for source in sorted(_UTILS.rglob("*.py"))
        if _imported_roots(source) & set(_UI_PACKAGES)
    ]

    # A folder dialog lived here once; dialogs belong with their callers.
    assert offenders == []

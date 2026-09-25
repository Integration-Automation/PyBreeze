"""PyBreeze's public names, imported the first time one is used.

Importing ``pybreeze`` used to import the whole IDE up front -- PySide6, JEditor,
every menu builder -- so ``import pybreeze.utils.<anything>`` took about four
seconds, and so did every process that only needed a utility: a test run, or the
regex tester's worker process, which paid it on each run. The names are the same
and resolve to the same objects; they are just looked up on first use.
"""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from je_editor import (
        load_external_plugins,
        register_natural_language,
        register_programming_language,
    )

    from pybreeze.pybreeze_ui.editor_main.main_ui import (
        EDITOR_EXTEND_TAB,
        PyBreezeMainWindow,
        start_editor,
    )

_MAIN_UI = "pybreeze.pybreeze_ui.editor_main.main_ui"
_JEDITOR = "je_editor"

# Where each public name lives; JEditor's plugin API is re-exported for convenience
_HOMES = {
    "EDITOR_EXTEND_TAB": _MAIN_UI,
    "PyBreezeMainWindow": _MAIN_UI,
    "start_editor": _MAIN_UI,
    "load_external_plugins": _JEDITOR,
    "register_natural_language": _JEDITOR,
    "register_programming_language": _JEDITOR,
}

__all__ = [
    "EDITOR_EXTEND_TAB",
    "PyBreezeMainWindow",
    "load_external_plugins",
    "register_natural_language",
    "register_programming_language",
    "start_editor",
]


def __getattr__(name: str) -> Any:
    """Import a public name from its home the first time it is asked for."""
    home = _HOMES.get(name)
    if home is None:
        raise AttributeError(f"module 'pybreeze' has no attribute {name!r}")
    value = getattr(importlib.import_module(home), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

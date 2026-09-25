"""The package facade: the public names, and what importing a utility costs.

Importing ``pybreeze`` used to import the whole IDE, so ``pybreeze.utils`` came
with PySide6 and JEditor attached. The facade looks its names up on first use.
Each check runs in a fresh interpreter, since this one has long imported the IDE.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_TIMEOUT_SECONDS = 120


def _run(code: str) -> dict:
    environment = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(_REPOSITORY_ROOT), os.environ.get("PYTHONPATH")])),
    }
    completed = subprocess.run(  # noqa: S603 — fixed argv: this interpreter and a literal script
        [sys.executable, "-c", code], env=environment, capture_output=True,
        timeout=_TIMEOUT_SECONDS, check=False, shell=False)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")[-2000:]
    return json.loads(completed.stdout.decode("utf-8").splitlines()[-1])


def test_a_utility_imports_without_the_ide():
    seen = _run(
        "import json, sys\n"
        "import pybreeze.utils.regex_tools.regex_tester\n"
        "print(json.dumps({'loaded': [m for m in ('PySide6', 'je_editor', "
        "'pybreeze.pybreeze_ui.editor_main.main_ui') if m in sys.modules]}))\n")

    assert seen["loaded"] == []


def test_the_public_names_are_the_ide_s_own_objects():
    seen = _run(
        "import json\n"
        "import pybreeze\n"
        "from pybreeze import EDITOR_EXTEND_TAB, PyBreezeMainWindow, start_editor\n"
        "from pybreeze import load_external_plugins, register_natural_language, "
        "register_programming_language\n"
        "from pybreeze.pybreeze_ui.editor_main import main_ui\n"
        "import je_editor\n"
        "print(json.dumps({\n"
        "    'same_registry': EDITOR_EXTEND_TAB is main_ui.EDITOR_EXTEND_TAB,\n"
        "    'same_window': PyBreezeMainWindow is main_ui.PyBreezeMainWindow,\n"
        "    'same_start': start_editor is main_ui.start_editor,\n"
        "    'same_plugins': load_external_plugins is je_editor.load_external_plugins,\n"
        "    'all_resolve': all(hasattr(pybreeze, name) for name in pybreeze.__all__),\n"
        "}))\n")

    assert all(seen.values()), seen


def test_an_unknown_name_is_an_attribute_error():
    seen = _run(
        "import json\n"
        "import pybreeze\n"
        "try:\n"
        "    pybreeze.no_such_name\n"
        "except AttributeError:\n"
        "    print(json.dumps({'raised': True}))\n")

    assert seen["raised"]


def test_dir_lists_every_public_name():
    import pybreeze

    assert set(pybreeze.__all__) <= set(dir(pybreeze))


def test_python_m_pybreeze_starts_the_editor_and_importing_it_does_not(monkeypatch):
    # Imported (a spawned regex worker re-runs the main module), it must not open an IDE
    import runpy

    import pybreeze

    started: list = []
    monkeypatch.setattr(pybreeze, "start_editor", lambda: started.append("started"))

    runpy.run_module("pybreeze.__main__", run_name="pybreeze.__main__")
    assert started == []
    runpy.run_module("pybreeze.__main__", run_name="__main__")
    assert started == ["started"]

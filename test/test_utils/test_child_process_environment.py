"""Every process the IDE starts is given its environment, never the IDE's own as it is.

CLAUDE.md: a process gets ``child_environment()`` or ``utf8_subprocess_env()``
(``utils/subprocess_util.py``), which leave out what the IDE set for itself alone
(``LOCUST_SKIP_MONKEY_PATCH``, which a load test must not inherit). A call with
no ``env`` inherits ``os.environ`` whole; five did.
"""
from __future__ import annotations

import ast
from pathlib import Path

_PACKAGE = Path(__file__).resolve().parents[2] / "pybreeze"
_STARTS = {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call",
           "subprocess.check_output"}


def _calls_without_env() -> list[str]:
    missing = []
    for path in sorted(_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and ast.unparse(node.func) in _STARTS
                    and not any(keyword.arg == "env" for keyword in node.keywords)):
                missing.append(f"{path.relative_to(_PACKAGE.parent)}:{node.lineno}")
    return missing


def test_every_process_started_is_given_an_environment():
    assert _calls_without_env() == []


def test_the_check_finds_the_calls_it_is_about():
    # Guard against a scan that finds nothing: the run executors start processes
    tree = ast.parse((_PACKAGE / "extend" / "process_executor" / "python_task_process_manager.py")
                     .read_text(encoding="utf-8"))
    assert any(isinstance(node, ast.Call) and ast.unparse(node.func) in _STARTS for node in ast.walk(tree))

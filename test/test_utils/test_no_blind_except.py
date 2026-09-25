"""``except Exception`` only to log and re-raise, or with a reason on the line.

CLAUDE.md, Code quality gates: a blind catch hides the error it was not written
for. The few places that must survive anything (a third-party tab, a run's
done-hook, an export) say why with ``# noqa: BLE001 — <reason>``.
"""
from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / "pybreeze"


def _catches_everything(handler: ast.ExceptHandler) -> bool:
    caught = handler.type
    if caught is None:
        return True
    names = caught.elts if isinstance(caught, ast.Tuple) else [caught]
    return any(isinstance(name, ast.Name) and name.id in ("Exception", "BaseException") for name in names)


def _re_raises(handler: ast.ExceptHandler) -> bool:
    return any(isinstance(node, ast.Raise) for node in ast.walk(handler))


def _has_reason(line: str) -> bool:
    _, _, comment = line.partition("# noqa: BLE001")
    return bool(comment.strip(" —-:"))


def test_every_blind_catch_re_raises_or_says_why():
    offenders = []
    for path in sorted(PACKAGE.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source, filename=str(path))):
            if not isinstance(node, ast.ExceptHandler) or not _catches_everything(node):
                continue
            if _re_raises(node) or _has_reason(lines[node.lineno - 1]):
                continue
            offenders.append(f"{path.relative_to(PACKAGE.parent)}:{node.lineno}")
    assert offenders == []


def test_no_noqa_reason_has_a_comma():
    # SonarCloud reads what follows a comma in "# noqa: CODE — reason" as more
    # rule codes, and reports the comment as a malformed suppression (S7632)
    offenders = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            _, marker, rest = line.partition("# noqa:")
            if marker and "," in rest.partition("—")[2]:
                offenders.append(f"{path.relative_to(PACKAGE)}:{number}")
    assert not offenders, offenders

"""What the published package needs from the source tree to hold everything the IDE imports and reads.

``pyproject.toml`` finds packages with ``namespaces = false``: a folder of modules
without an ``__init__.py`` is left out of the wheel, and the installed IDE fails
to import it. A file that is not Python goes in only as package data: the
window's icon was read from the working folder, and never shipped.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE = _ROOT / "pybreeze"


def _package_files() -> list[Path]:
    """The files under ``pybreeze/`` that are the package's: tracked ones, when git can say.

    A log a tool wrote there, or an editor's backup, is not the package's.
    """
    try:
        listed = subprocess.run(  # noqa: S603 - fixed argv
            ["git", "ls-files", "pybreeze"], cwd=_ROOT, capture_output=True, text=True,
            encoding="utf-8", timeout=60, check=True, shell=False).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return [path for path in _PACKAGE.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    return [_ROOT / name for name in listed]


def _package_data(config: str) -> dict[str, list[str]]:
    """The ``[tool.setuptools.package-data]`` table of *config*, package -> file names."""
    text = (_ROOT / config).read_text(encoding="utf-8")
    table = text.split("[tool.setuptools.package-data]", 1)[1].split("\n[", 1)[0]
    return {package: re.findall(r'"([^"]+)"', names)
            for package, names in re.findall(r'^"([\w.]+)"\s*=\s*\[([^\]]*)\]', table, re.M)}


def test_every_folder_of_modules_is_a_package():
    # Every module found, tracked or not: a folder added a moment ago counts too
    folders = sorted({path.parent for path in _PACKAGE.rglob("*.py") if "__pycache__" not in path.parts})
    assert [str(folder.relative_to(_ROOT)) for folder in folders if not (folder / "__init__.py").is_file()] == []


def test_every_file_that_is_not_python_is_package_data():
    others = [path for path in _package_files() if path.suffix != ".py"]
    assert others, "the window's icon, at least, is package data"
    for config in ("pyproject.toml", "dev.toml"):
        listed = _package_data(config)
        for path in others:
            package = ".".join(path.parent.relative_to(_ROOT).parts)
            assert path.name in listed.get(package, []), f"{path.name} is not package data in {config}"

"""What the published package needs from the source tree to hold everything the IDE imports and reads.

``pyproject.toml`` finds packages with ``namespaces = false``: a folder of modules
without an ``__init__.py`` is left out of the wheel, and the installed IDE fails
to import it. A file that is not Python goes in only as package data: the
window's icon was read from the working folder, and never shipped.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE = _ROOT / "pybreeze"


def _source_folders() -> list[Path]:
    return sorted({path.parent for path in _PACKAGE.rglob("*.py") if "__pycache__" not in path.parts})


def test_every_folder_of_modules_is_a_package():
    assert [str(folder.relative_to(_ROOT)) for folder in _source_folders()
            if not (folder / "__init__.py").is_file()] == []


def test_every_file_that_is_not_python_is_package_data():
    others = [path for path in _PACKAGE.rglob("*")
              if path.is_file() and path.suffix not in {".py", ".pyc"} and "__pycache__" not in path.parts]
    assert others, "the window's icon, at least, is package data"
    for config in ("pyproject.toml", "dev.toml"):
        text = (_ROOT / config).read_text(encoding="utf-8")
        for path in others:
            package = ".".join(path.parent.relative_to(_ROOT).parts)
            assert f'"{package}" = ["{path.name}"]' in text, f"{path.name} is not package data in {config}"

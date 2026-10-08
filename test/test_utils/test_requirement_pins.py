"""``requirements.txt``, ``pyproject.toml`` and ``dev.toml`` ask for the same packages.

``pyproject.toml`` is what users install, ``dev.toml`` describes ``pybreeze_dev``
with the same dependencies, and ``requirements.txt`` (read by
``dev_requirements.txt``) is what CI and a working copy install. Each says it is
kept in step with the others, and nothing checked it: a pin moved in one (as
PySide6 did to 6.11.2) would leave CI testing another Qt than the release ships.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")  # stdlib from 3.11; CI also runs 3.10

_ROOT = Path(__file__).resolve().parents[2]
_REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*([^#;]*)")


def _normalised(requirement: str) -> tuple[str, str]:
    """``(PEP 503 name, version specifier without spaces)``: ``je_editor >= 1.0`` is ``je-editor>=1.0``."""
    match = _REQUIREMENT.match(requirement)
    assert match, requirement
    return re.sub(r"[-_.]+", "-", match.group(1)).lower(), match.group(2).replace(" ", "")


def _toml_dependencies(name: str) -> set[tuple[str, str]]:
    with (_ROOT / name).open("rb") as handle:
        return {_normalised(line) for line in tomllib.load(handle)["project"]["dependencies"]}


def _requirements_file(name: str) -> set[tuple[str, str]]:
    lines = (_ROOT / name).read_text(encoding="utf-8").splitlines()
    return {_normalised(line) for line in lines if line.strip() and not line.lstrip().startswith(("#", "-"))}


def test_dev_toml_depends_on_what_pyproject_does():
    assert _toml_dependencies("dev.toml") == _toml_dependencies("pyproject.toml")


def test_requirements_txt_installs_what_the_package_depends_on():
    assert _requirements_file("requirements.txt") == _toml_dependencies("pyproject.toml")


def test_dev_requirements_pin_nothing_the_package_pins_differently():
    package = dict(_toml_dependencies("pyproject.toml"))
    development = dict(_requirements_file("dev_requirements.txt"))
    assert {name: (development[name], package[name]) for name in development.keys() & package.keys()
            if development[name] != package[name]} == {}


def test_names_are_compared_as_pip_compares_them():
    assert _normalised("je_editor >= 1.0.27") == _normalised("je-editor>=1.0.27")
    assert _normalised("PySide6==6.11.2  # the Qt the release ships") == ("pyside6", "==6.11.2")

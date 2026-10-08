"""``dev.toml`` builds the same package as ``pyproject.toml``, under another name.

CI publishes ``pybreeze_dev`` by writing ``dev.toml`` to ``pyproject.toml``
(``scripts/dev_release.py``), while the tests ran against the working tree that
``pyproject.toml`` describes. Whatever decides what the wheel holds or what it
can be installed on has to say the same in both, or the dev channel ships
something the tests never saw. The dependencies are compared in
``test_requirement_pins.py``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")  # stdlib from 3.11; CI also runs 3.10

_ROOT = Path(__file__).resolve().parents[2]
_ENTRY_POINT_TABLES = ("scripts", "gui-scripts", "entry-points")


def _load(name: str) -> dict:
    with (_ROOT / name).open("rb") as handle:
        return tomllib.load(handle)


_STABLE = _load("pyproject.toml")
_DEV = _load("dev.toml")


def test_the_two_packages_have_their_own_names():
    assert _STABLE["project"]["name"] == "pybreeze"
    assert _DEV["project"]["name"] == "pybreeze_dev"


def test_both_install_on_the_same_pythons():
    assert _DEV["project"]["requires-python"] == _STABLE["project"]["requires-python"]


def test_both_offer_the_same_extras():
    assert _DEV["project"].get("optional-dependencies", {}) == _STABLE["project"].get("optional-dependencies", {})


@pytest.mark.parametrize("table", _ENTRY_POINT_TABLES)
def test_both_declare_the_same_entry_points(table):
    assert _DEV["project"].get(table, {}) == _STABLE["project"].get(table, {})


def test_both_ship_the_same_files():
    # Package discovery and package data decide which files reach the wheel (the window's icon among them)
    assert _DEV["tool"]["setuptools"] == _STABLE["tool"]["setuptools"]


def test_both_are_built_by_the_same_backend():
    assert _DEV["build-system"] == _STABLE["build-system"]

"""What the IDE remembers about its own panels from one run to the next."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from pybreeze.utils import ui_state
from pybreeze.utils.ui_state import read_ui_state, remember


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def _file(home: Path) -> Path:
    return home / ".pybreeze" / "ui_state.json"


def test_nothing_is_remembered_at_first_and_reading_leaves_no_file(home):
    assert read_ui_state() == {}
    assert not (home / ".pybreeze").exists()


def test_what_is_remembered_is_read_back(home):
    remember("navigation_visible", False)

    assert read_ui_state() == {"navigation_visible": False}
    assert json.loads(_file(home).read_text(encoding="utf-8")) == {"navigation_visible": False}


def test_one_thing_remembered_keeps_the_others(home):
    remember("a", 1)
    remember("b", "二")

    assert read_ui_state() == {"a": 1, "b": "二"}


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '"text"', ""], ids=["damaged", "a-list", "a-string", "empty"])
def test_a_file_that_is_not_what_was_written_remembers_nothing(home, content):
    _file(home).parent.mkdir()
    _file(home).write_text(content, encoding="utf-8")

    assert read_ui_state() == {}


def test_a_file_that_is_not_utf8_remembers_nothing(home):
    _file(home).parent.mkdir()
    _file(home).write_bytes(b"\xff\xfe\x00")

    assert read_ui_state() == {}


def test_a_damaged_file_is_replaced_by_the_next_thing_remembered(home):
    _file(home).parent.mkdir()
    _file(home).write_text("{not json", encoding="utf-8")

    remember("a", 1)

    assert read_ui_state() == {"a": 1}


def test_a_file_that_cannot_be_written_is_logged_and_nothing_more(home, monkeypatch, caplog):
    def refuse(_path, _text, **_options):
        raise PermissionError("read-only")

    monkeypatch.setattr(ui_state, "replace_text", refuse)

    with caplog.at_level(logging.ERROR):
        remember("a", 1)

    assert "could not be written" in caplog.text
    assert read_ui_state() == {}

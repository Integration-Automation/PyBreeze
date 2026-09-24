"""Tool output lines in the IDE's language, punctuation included.

In the Traditional Chinese IDE the regex tester wrote ``group 1: 'GET'`` and the
timestamp converter ``Epoch（秒）: 1754208900``: an English word, and a
half-width colon after a Chinese label.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.utils.regex_tools.regex_tester import MatchResult
from pybreeze.utils.timestamp_tools.timestamp_converter import convert_timestamp

_MATCH = MatchResult(matched_text="GET /a", start=0, end=6, groups=["GET", "/a"], named_groups={"m": "GET"})


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def chinese(app, monkeypatch):
    from je_editor import language_wrapper

    from pybreeze.extend_multi_language.extend_traditional_chinese import pybreeze_traditional_chinese_word_dict
    monkeypatch.setattr(language_wrapper, "language_word_dict", pybreeze_traditional_chinese_word_dict)


@pytest.fixture()
def english(app, monkeypatch):
    from je_editor import language_wrapper

    from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict
    monkeypatch.setattr(language_wrapper, "language_word_dict", pybreeze_english_word_dict)


def _regex_lines() -> list[str]:
    from pybreeze.pybreeze_ui.tools_gui.regex_gui import build_matches_text
    return build_matches_text([_MATCH], "none").splitlines()[3:]


def _timestamp_lines() -> list[str]:
    from pybreeze.pybreeze_ui.tools_gui.timestamp_gui import build_result_text
    return build_result_text(convert_timestamp("1754208900")).splitlines()


def test_the_regex_groups_in_chinese(chinese):
    assert _regex_lines() == ["    群組 1：'GET'", "    群組 2：'/a'", "    m：'GET'"]


def test_the_regex_groups_in_english(english):
    assert _regex_lines() == ["    group 1: 'GET'", "    group 2: '/a'", "    m: 'GET'"]


def test_the_timestamp_lines_in_chinese(chinese):
    assert _timestamp_lines() == [
        "Epoch（秒）：1754208900", "Epoch（毫秒）：1754208900000", "ISO-8601（UTC）：2025-08-03T08:15:00+00:00"]


def test_the_timestamp_lines_in_english(english):
    assert _timestamp_lines() == [
        "Epoch (seconds): 1754208900", "Epoch (milliseconds): 1754208900000",
        "ISO-8601 (UTC): 2025-08-03T08:15:00+00:00"]

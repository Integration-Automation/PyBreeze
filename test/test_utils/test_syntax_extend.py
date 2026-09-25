"""Automation keyword highlighting is registered for every suffix the IDE runs."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from je_editor.plugins import get_programming_language_plugin

from pybreeze.pybreeze_ui.syntax.syntax_extend import syntax_extend_package
from pybreeze.pybreeze_ui.syntax.syntax_keyword import TEST_PIONEER_SUFFIXES, package_keyword_list


class _Tabs:
    @staticmethod
    def currentWidget():
        return None


class _MainWindow:
    tab_widget = _Tabs()


@pytest.fixture(scope="module")
def registered():
    syntax_extend_package(_MainWindow())


@pytest.mark.parametrize("suffix", [".yml", ".yaml"])
def test_a_test_pioneer_script_is_highlighted_under_either_yaml_suffix(registered, suffix):
    # ".yaml" scripts ran from the TestPioneer menu but were shown plain
    plugin = get_programming_language_plugin(suffix)

    assert plugin is not None
    assert plugin["syntax_words"]["test_pioneer"]["words"] == set(package_keyword_list["test_pioneer"])


def test_the_menu_runs_exactly_the_highlighted_suffixes():
    from pybreeze.pybreeze_ui.menu.automation_menu.test_pioneer_menu import build_test_pioneer_menu as menu

    assert menu._YAML_FILTER == "YAML (*.yml *.yaml)"
    assert TEST_PIONEER_SUFFIXES == (".yml", ".yaml")


def test_every_automation_package_gets_json_keywords(registered):
    from pybreeze.utils.manager.package_manager.package_manager_class import package_manager

    groups = get_programming_language_plugin(".json")["syntax_words"]

    assert set(groups) == set(package_manager.syntax_check_list)


class _File:
    def __init__(self, name: str) -> None:
        self.current_file = name


def _keyword_colour(suffix: str, keyword: str):
    from je_editor.pyside_ui.code.syntax.python_syntax import PythonHighlighter
    from PySide6.QtCore import QRegularExpression
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    highlighter = PythonHighlighter(main_window=_File(f"script{suffix}"))
    pattern = QRegularExpression(rf"\b{keyword}\b").pattern()
    return next(fmt.foreground().color() for rule, fmt in highlighter.highlight_rules if rule.pattern() == pattern)


@pytest.mark.parametrize(("suffix", "package", "key"), [
    (".json", "je_auto_control", "warning_output_color"),
    (".yaml", "test_pioneer", "diff_modified_marker_color"),
])
def test_keywords_take_the_theme_colour_and_follow_a_light_theme(registered, suffix, package, key):
    # Fixed pure yellow keywords could not be read on a light theme
    from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import (
        actually_color_dict, apply_theme_colors,
    )

    keyword = sorted(package_keyword_list[package])[0]
    try:
        apply_theme_colors("dark_amber.xml")
        on_dark = _keyword_colour(suffix, keyword)
        apply_theme_colors("light_blue.xml")
        on_light = _keyword_colour(suffix, keyword)
        assert on_light == actually_color_dict[key]
    finally:
        apply_theme_colors("dark_amber.xml")

    assert on_dark != on_light

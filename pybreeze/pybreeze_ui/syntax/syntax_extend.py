from __future__ import annotations

from typing import TYPE_CHECKING

from je_editor import EditorWidget, register_programming_language

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

from pybreeze.pybreeze_ui.syntax.syntax_keyword import TEST_PIONEER_SUFFIXES, package_keyword_list
from pybreeze.utils.manager.package_manager.package_manager_class import package_manager

# Keyword colours as keys into JEditor's theme colours, which have a dark and a
# light set: fixed yellow (255, 255, 0) keywords could not be read on a light
# theme. The highlighter looks the key up each time it is built, so the
# colours follow a theme change.
JSON_KEYWORD_COLOUR = "warning_output_color"         # yellow; dark yellow on light
YAML_KEYWORD_COLOUR = "diff_modified_marker_color"   # orange


def syntax_extend_package(main_window: PyBreezeMainWindow) -> None:
    # Register JSON syntax keywords for each automation package
    json_syntax_words = {}
    for package in package_manager.syntax_check_list:
        # Default to an empty list so a package without a keyword list registers
        # no words instead of crashing syntax setup with set(None).
        json_syntax_words[package] = {
            "words": set(package_keyword_list.get(package, [])),
            "color": JSON_KEYWORD_COLOUR,
        }
    register_programming_language(".json", json_syntax_words)

    # Register YAML syntax keywords for test_pioneer, under every suffix the
    # TestPioneer menu runs (".yaml" files were run but not highlighted)
    yml_syntax_words = {
        "test_pioneer": {
            "words": set(package_keyword_list.get("test_pioneer", [])),
            "color": YAML_KEYWORD_COLOUR,
        }
    }
    for suffix in TEST_PIONEER_SUFFIXES:
        register_programming_language(suffix, yml_syntax_words)

    widget = main_window.tab_widget.currentWidget()
    if isinstance(widget, EditorWidget):
        widget.code_edit.reset_highlighter()

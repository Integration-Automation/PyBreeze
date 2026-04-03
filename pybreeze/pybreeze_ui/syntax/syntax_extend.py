from __future__ import annotations

from typing import TYPE_CHECKING

from je_editor import EditorWidget, register_programming_language

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow
from PySide6.QtGui import QColor

from pybreeze.pybreeze_ui.syntax.syntax_keyword import \
    package_keyword_list
from pybreeze.utils.manager.package_manager.package_manager_class import package_manager


def syntax_extend_package(main_window: PyBreezeMainWindow) -> None:
    # Register JSON syntax keywords for each automation package
    json_syntax_words = {}
    for package in package_manager.syntax_check_list:
        json_syntax_words[package] = {
            "words": set(package_keyword_list.get(package)),
            "color": QColor(255, 255, 0),
        }
    register_programming_language(".json", json_syntax_words)

    # Register YAML syntax keywords for test_pioneer
    yml_syntax_words = {
        "test_pioneer": {
            "words": set(package_keyword_list.get("test_pioneer")),
            "color": QColor(255, 153, 0),
        }
    }
    register_programming_language(".yml", yml_syntax_words)

    widget = main_window.tab_widget.currentWidget()
    if isinstance(widget, EditorWidget):
        widget.code_edit.reset_highlighter()

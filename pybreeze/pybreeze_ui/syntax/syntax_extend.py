from __future__ import annotations

from typing import TYPE_CHECKING

from je_editor import EditorWidget

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow
from PySide6.QtGui import QColor

from pybreeze.pybreeze_ui.syntax.syntax_keyword import \
    package_keyword_list
from pybreeze.utils.manager.package_manager.package_manager_class import package_manager

from je_editor import syntax_extend_setting_dict


def syntax_extend_package(main_window: PyBreezeMainWindow) -> None:
    syntax_extend_setting_dict.update({".json": {}})
    for package in package_manager.syntax_check_list:
        syntax_extend_setting_dict.get(".json").update(
            {
                package: {
                    "words": set(package_keyword_list.get(package)),
                    "color": QColor(255, 255, 0)
                }
            }
        )
    syntax_extend_setting_dict.update({".yml": {}})
    syntax_extend_setting_dict.get(".yml").update(
        {
            "test_pioneer": {
                "words": set(package_keyword_list.get("test_pioneer")),
                "color": QColor(255, 153, 0)
            }
        }
    )
    widget = main_window.tab_widget.currentWidget()
    if isinstance(widget, EditorWidget):
        widget.code_edit.reset_highlighter()

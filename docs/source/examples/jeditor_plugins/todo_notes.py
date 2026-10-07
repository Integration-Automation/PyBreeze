"""A plugin for the tutorial: colours the states and the comments of ``.todo`` files.

Put this file in a folder called ``jeditor_plugins`` inside the folder PyBreeze
is started in. Plugins are loaded once, as the IDE starts.
"""
from PySide6.QtGui import QColor

from je_editor.plugins import register_programming_language

PLUGIN_NAME = "Todo notes"
PLUGIN_VERSION = "1.0"


def register() -> None:
    register_programming_language(
        suffix=".todo",
        syntax_words={
            "states": {"words": ("TODO", "DOING", "DONE"), "color": QColor(86, 156, 214)},
        },
        syntax_rules={
            "comments": {"rules": (r"#[^\n]*",), "color": QColor(106, 153, 85)},
        },
    )

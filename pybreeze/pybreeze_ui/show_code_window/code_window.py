from __future__ import annotations

from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict
from PySide6.QtGui import QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QWidget, QGridLayout, QTextEdit, QScrollArea

# Cap the output scrollback so a runaway script (e.g. an infinite print loop)
# cannot grow the document without bound and exhaust memory; the oldest lines
# are dropped once the limit is reached, like a terminal's scrollback buffer.
MAX_OUTPUT_BLOCKS = 10000


def normalize_line_endings(text: str) -> str:
    """Turn ``\r\n`` and a lone ``\r`` into ``\n``.

    A child on Windows writes ``\r\n``, and a progress bar rewinds its line
    with a bare ``\r``; the text widget only breaks lines on ``\n``.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


class CodeWindow(QWidget):

    def __init__(self):
        # UI used to show run code or shell command result.
        super().__init__()
        self.python_compiler = None
        self.grid_layout = QGridLayout()
        self.code_result = QTextEdit()
        self.code_result.setLineWrapMode(self.code_result.LineWrapMode.NoWrap)
        self.code_result.setReadOnly(True)
        self.code_result.document().setMaximumBlockCount(MAX_OUTPUT_BLOCKS)
        self.code_result_scroll_area = QScrollArea()
        self.code_result_scroll_area.setWidgetResizable(True)
        self.code_result_scroll_area.setViewportMargins(0, 0, 0, 0)
        self.code_result_scroll_area.setWidget(self.code_result)
        self.grid_layout.addWidget(self.code_result_scroll_area, 0, 0)
        # Adaptive sizing based on screen
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            screen_size = screen.availableSize()
            self.resize(
                max(500, screen_size.width() // 3),
                max(400, screen_size.height() // 3)
            )
        else:
            self.resize(500, 500)
        self.setLayout(self.grid_layout)
        self.setFocus()

    def append_output(self, text: str, is_error: bool = False, *, own_line: bool = False) -> None:
        """Append *text* to the end of the output, in the normal or the error colour.

        The text goes in as written: a line break is wherever *text* has one.
        *own_line* is for the window's own status messages, which should not
        continue a line the program left unfinished. The text always lands at
        the end, because the widget's own cursor follows the user's clicks and
        selections, and writing there would splice output into the middle or
        overwrite whatever the user had selected.

        The view follows the output while it is scrolled to the bottom, like a
        terminal; once the user scrolls up to read, it stays where they left it.
        """
        scroll_bar = self.code_result.verticalScrollBar()
        follow_output = scroll_bar.value() >= scroll_bar.maximum()
        cursor = QTextCursor(self.code_result.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if own_line and cursor.positionInBlock() > 0:
            text = "\n" + text
        text_format = QTextCharFormat()
        color_key = "error_output_color" if is_error else "normal_output_color"
        text_format.setForeground(actually_color_dict.get(color_key))
        cursor.insertText(normalize_line_endings(text), text_format)
        if follow_output:
            scroll_bar.setValue(scroll_bar.maximum())

from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QGridLayout, QTextEdit, QScrollArea

# Cap the output scrollback so a runaway script (e.g. an infinite print loop)
# cannot grow the document without bound and exhaust memory; the oldest lines
# are dropped once the limit is reached, like a terminal's scrollback buffer.
MAX_OUTPUT_BLOCKS = 10000


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

from PySide6.QtWidgets import QWidget, QGridLayout, QTextEdit, QScrollArea


class CodeWindow(QWidget):

    def __init__(self):
        # UI used to show run code or shell command result.
        super().__init__()
        self.python_compiler = None
        self.grid_layout = QGridLayout()
        self.code_result = QTextEdit()
        self.code_result.setLineWrapMode(self.code_result.LineWrapMode.NoWrap)
        self.code_result.setReadOnly(True)
        self.code_result_scroll_area = QScrollArea()
        self.code_result_scroll_area.setWidgetResizable(True)
        self.code_result_scroll_area.setViewportMargins(0, 0, 0, 0)
        self.code_result_scroll_area.setWidget(self.code_result)
        self.grid_layout.addWidget(self.code_result_scroll_area, 0, 0)
        self.resize(500, 500)
        self.setLayout(self.grid_layout)
        self.setFocus()

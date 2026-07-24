"""A tool tab that shows a unified diff between two pieces of text."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.diff_tools.text_diff import DiffSummary, diff_summary, unified_diff


def build_summary_line(summary: DiffSummary) -> str:
    """Render a one-line summary of a diff.

    :param summary: the diff counts
    :return: a short summary string
    """
    word = language_wrapper.language_word_dict
    if summary.is_equal:
        return word.get("diff_identical")
    return word.get("diff_summary").format(added=summary.added, removed=summary.removed)


class DiffGUI(QWidget):
    """Paste two texts and see how they differ."""

    def __init__(self, main_window=None) -> None:
        """
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        word = language_wrapper.language_word_dict

        self.left_label = QLabel(word.get("diff_left_label"))
        self.left_edit = QTextEdit()
        self.left_edit.setAcceptRichText(False)
        self.right_label = QLabel(word.get("diff_right_label"))
        self.right_edit = QTextEdit()
        self.right_edit.setAcceptRichText(False)

        inputs = QHBoxLayout()
        left_column = QVBoxLayout()
        left_column.addWidget(self.left_label)
        left_column.addWidget(self.left_edit)
        right_column = QVBoxLayout()
        right_column.addWidget(self.right_label)
        right_column.addWidget(self.right_edit)
        inputs.addLayout(left_column)
        inputs.addLayout(right_column)

        self.compare_button = QPushButton(word.get("diff_compare_button"))
        self.compare_button.clicked.connect(self.compare)

        self.summary_label = QLabel("")
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="diff", extension="txt")

        layout = QVBoxLayout()
        layout.addLayout(inputs)
        layout.addWidget(self.compare_button)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.output_edit)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

    def compare(self) -> None:
        """Compute and show the diff and summary of the two inputs."""
        left = self.left_edit.toPlainText()
        right = self.right_edit.toPlainText()
        self.summary_label.setText(build_summary_line(diff_summary(left, right)))
        self.output_edit.setPlainText(unified_diff(left, right))

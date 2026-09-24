"""A tool tab that shows a unified diff between two pieces of text."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper
from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict

from pybreeze.pybreeze_ui.tools_gui.run_shortcut import press_on_ctrl_enter
from pybreeze.pybreeze_ui.exact_text import exact_text
from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.pybreeze_ui.thread_keeper import let_run_out
from pybreeze.pybreeze_ui.fixed_pitch import use_fixed_pitch_font
from pybreeze.utils.diff_tools.text_diff import Comparison, DiffSummary, compare_texts

# A unified diff line's first characters -> JEditor theme colour (a dark and a
# light set, which the Style menu switches between); the first match counts
_LINE_COLOURS = (
    ("@@", "syntax_keyword_color"),
    ("+", "diff_added_marker_color"),
    ("-", "diff_removed_marker_color"),
    ("\\", "blame_annotation_color"),  # "\ No newline at end of file"
)
# The "--- expected" and "+++ actual" lines a diff starts with
_HEADER_LINES = 2


def diff_line_colour(line: str, line_number: int) -> str | None:
    """The theme colour key *line* of a unified diff is shown in, or ``None`` for the view's own.

    Only the first two lines are the header: a removed line reading ``--x``
    also starts with ``---``.
    """
    if line_number < _HEADER_LINES and line.startswith(("--- ", "+++ ")):
        return None
    return next((key for prefix, key in _LINE_COLOURS if line.startswith(prefix)), None)


class UnifiedDiffHighlighter(QSyntaxHighlighter):
    """Colours a unified diff's added, removed and hunk lines, in the theme's colours."""

    def highlightBlock(self, text: str) -> None:
        key = diff_line_colour(text, self.currentBlock().blockNumber())
        colour = actually_color_dict.get(key) if key is not None else None
        if colour is not None:
            text_format = QTextCharFormat()
            text_format.setForeground(colour)
            self.setFormat(0, len(text), text_format)


def build_summary_line(summary: DiffSummary) -> str:
    """Render a one-line summary of a diff.

    :param summary: the diff counts
    :return: a short summary string
    """
    word = language_wrapper.language_word_dict
    if summary.is_equal:
        return word.get("diff_identical")
    return word.get("diff_summary").format(added=summary.added, removed=summary.removed)


class DiffThread(QThread):
    """One comparison, worked out off the UI thread."""

    compared = Signal(object)

    def __init__(self, left: str, right: str) -> None:
        super().__init__()
        self._left = left
        self._right = right

    def run(self) -> None:
        self.compared.emit(compare_texts(self._left, self._right))


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
        use_fixed_pitch_font(self.left_edit)
        self.left_edit.setAcceptRichText(False)
        self.right_label = QLabel(word.get("diff_right_label"))
        self.right_edit = QTextEdit()
        use_fixed_pitch_font(self.right_edit)
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
        press_on_ctrl_enter(self, self.compare_button)

        self.summary_label = QLabel("")
        self.output_edit = QTextEdit()
        use_fixed_pitch_font(self.output_edit)
        self.output_edit.setReadOnly(True)
        self._highlighter = UnifiedDiffHighlighter(self.output_edit.document())

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
        self._compare_thread: DiffThread | None = None

    def compare(self) -> None:
        """Compare the two inputs; the diff and the summary arrive when it is done.

        Matching the lines of two large texts takes seconds (a 40,000-line JSON
        response, over four), and it ran on the UI thread, twice, freezing the IDE.
        """
        if self._compare_thread is not None and self._compare_thread.isRunning():
            return
        self.compare_button.setEnabled(False)
        self.summary_label.setText(language_wrapper.language_word_dict.get("diff_comparing"))
        thread = DiffThread(exact_text(self.left_edit), exact_text(self.right_edit))
        thread.compared.connect(self._show)
        thread.finished.connect(self._enable_compare)
        self._compare_thread = thread
        thread.start()

    def _enable_compare(self) -> None:
        """Let the next comparison start. A bound method: a lambda holding the
        tab, on the thread the tab keeps, kept the closed tab alive."""
        self.compare_button.setEnabled(True)

    def _show(self, comparison: Comparison) -> None:
        self.summary_label.setText(build_summary_line(comparison.summary))
        self.output_edit.setPlainText(comparison.diff)

    def closeEvent(self, event) -> None:
        """Let a comparison still going run out, cut off from this tab."""
        thread = self._compare_thread
        if thread is not None and thread.isRunning():
            let_run_out(thread, thread.compared)
        super().closeEvent(event)

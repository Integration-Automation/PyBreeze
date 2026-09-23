"""A tool tab that tests a regular expression against sample text."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.thread_keeper import let_run_out
from pybreeze.pybreeze_ui.tools_gui.exact_text import exact_text
from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.exception.exceptions import RegexTesterException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.regex_tools.regex_tester import (
    MAX_MATCHES, MatchResult, available_flags, find_matches_bounded, stop_running_workers
)


class RegexMatchThread(QThread):
    """One pattern run, waited for off the UI thread."""

    matched = Signal(list)
    failed = Signal(str)

    def __init__(self, pattern: str, text: str, flag_names: list[str]) -> None:
        super().__init__()
        self._pattern = pattern
        self._text = text
        self._flag_names = flag_names

    def run(self) -> None:
        try:
            self.matched.emit(find_matches_bounded(self._pattern, self._text, self._flag_names))
        except RegexTesterException as error:
            self.failed.emit(str(error))


def build_matches_text(matches: list[MatchResult], no_match_message: str) -> str:
    """Render matches into a readable, numbered report.

    :param matches: the matches to render
    :param no_match_message: text shown when there are no matches
    :return: display text
    """
    if not matches:
        return no_match_message
    word = language_wrapper.language_word_dict
    count = word.get("regex_match_count").format(count=len(matches))
    if len(matches) >= MAX_MATCHES:
        # The list stops at the cap; it did not say there might be more
        count = word.get("regex_match_count_capped").format(count=len(matches))
    lines = [count, ""]
    for index, match in enumerate(matches, start=1):
        lines.append(f"[{index}] ({match.start}-{match.end}) {match.matched_text!r}")
        for group_index, value in enumerate(match.groups, start=1):
            lines.append(f"    group {group_index}: {value!r}")
        for name, value in match.named_groups.items():
            lines.append(f"    {name}: {value!r}")
    return "\n".join(lines)


class RegexGUI(QWidget):
    """Enter a pattern and sample text, then see every match and its groups."""

    def __init__(self, main_window=None) -> None:
        """
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        self._valid_output = False
        self._match_thread: RegexMatchThread | None = None
        word = language_wrapper.language_word_dict

        self.pattern_label = QLabel(word.get("regex_pattern_label"))
        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText(word.get("regex_pattern_placeholder"))

        self.flag_checkboxes: dict[str, QCheckBox] = {}
        flags_row = QHBoxLayout()
        for flag_name in available_flags():
            checkbox = QCheckBox(flag_name)
            self.flag_checkboxes[flag_name] = checkbox
            flags_row.addWidget(checkbox)
        flags_row.addStretch()

        self.text_label = QLabel(word.get("regex_text_label"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(word.get("regex_text_placeholder"))
        self.text_edit.setAcceptRichText(False)

        self.test_button = QPushButton(word.get("regex_test_button"))
        self.test_button.clicked.connect(self.test)

        self.output_label = QLabel(word.get("regex_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="matches", extension="txt", is_valid=lambda: self._valid_output)

        layout = QVBoxLayout()
        layout.addWidget(self.pattern_label)
        layout.addWidget(self.pattern_edit)
        layout.addLayout(flags_row)
        layout.addWidget(self.text_label)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.test_button)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output_edit)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

    def selected_flags(self) -> list[str]:
        """Return the flag names whose checkbox is ticked."""
        return [name for name, box in self.flag_checkboxes.items() if box.isChecked()]

    def test(self) -> None:
        """Run the pattern against the sample text; the matches arrive when it is done.

        The pattern runs in a separate process that is stopped after a few
        seconds (``find_matches_bounded``), and this tab waits for it on a
        thread of its own: a pattern that backtracks catastrophically used to
        run on the UI thread and freeze the IDE for minutes.
        """
        if self._match_thread is not None and self._match_thread.isRunning():
            return
        word = language_wrapper.language_word_dict
        self.test_button.setEnabled(False)
        # Not something to save or open: Save during a run wrote this text
        self._valid_output = False
        self.output_edit.setPlainText(word.get("regex_running"))
        thread = RegexMatchThread(
            self.pattern_edit.text(), exact_text(self.text_edit), self.selected_flags())
        thread.matched.connect(self._show_matches)
        thread.failed.connect(self._show_error)
        thread.finished.connect(lambda: self.test_button.setEnabled(True))
        self._match_thread = thread
        thread.start()

    def _show_matches(self, matches: list) -> None:
        self._valid_output = True
        self.output_edit.setPlainText(
            build_matches_text(matches, language_wrapper.language_word_dict.get("regex_no_match")))

    def _show_error(self, message: str) -> None:
        pybreeze_logger.info("regex_gui.py test failed: %s", message)
        self._valid_output = False
        self.output_edit.setPlainText(
            language_wrapper.language_word_dict.get("regex_error").format(error=message))

    def closeEvent(self, event) -> None:
        """Stop a pattern still running, and let its thread run out.

        The worker process is stopped rather than left to its deadline: the IDE
        closes its tabs as it exits, and an exiting IDE does not end it.
        """
        thread = self._match_thread
        if thread is not None and thread.isRunning():
            let_run_out(thread, thread.matched, thread.failed)
            stop_running_workers()
        super().closeEvent(event)

"""A tool tab that tests a regular expression against sample text."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.exception.exceptions import RegexTesterException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.regex_tools.regex_tester import (
    MatchResult, available_flags, find_matches
)


def build_matches_text(matches: list[MatchResult], no_match_message: str) -> str:
    """Render matches into a readable, numbered report.

    :param matches: the matches to render
    :param no_match_message: text shown when there are no matches
    :return: display text
    """
    if not matches:
        return no_match_message
    word = language_wrapper.language_word_dict
    lines = [word.get("regex_match_count").format(count=len(matches)), ""]
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
        """Run the pattern against the sample text and show the matches."""
        word = language_wrapper.language_word_dict
        pattern = self.pattern_edit.text()
        try:
            matches = find_matches(pattern, self.text_edit.toPlainText(), self.selected_flags())
        except RegexTesterException as error:
            pybreeze_logger.info("regex_gui.py test failed: %r", error)
            self._valid_output = False
            self.output_edit.setPlainText(word.get("regex_error").format(error=str(error)))
            return
        self._valid_output = True
        self.output_edit.setPlainText(
            build_matches_text(matches, word.get("regex_no_match")))

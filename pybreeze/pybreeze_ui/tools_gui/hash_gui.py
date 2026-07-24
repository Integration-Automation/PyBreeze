"""A tool tab that shows common hash digests of the entered text."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.hash_tools.hash_text import hash_all


def build_hash_text(digests: dict[str, str]) -> str:
    """Render digests as one ``ALGORITHM: value`` line each.

    :param digests: ``algorithm -> hex digest``
    :return: display text, one algorithm per line
    """
    return "\n".join(f"{name.upper()}: {value}" for name, value in digests.items())


class HashGUI(QWidget):
    """Type or paste text and read its digests under several algorithms."""

    def __init__(self, main_window=None) -> None:
        """
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        word = language_wrapper.language_word_dict

        self.input_label = QLabel(word.get("hash_input_label"))
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(word.get("hash_input_placeholder"))
        self.input_edit.setAcceptRichText(False)

        self.hash_button = QPushButton(word.get("hash_button"))
        self.hash_button.clicked.connect(self.compute)

        self.output_label = QLabel(word.get("hash_output_label"))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="hashes", extension="txt")

        layout = QVBoxLayout()
        for widget in (
            self.input_label, self.input_edit, self.hash_button,
            self.output_label, self.output_edit,
        ):
            layout.addWidget(widget)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

    def compute(self) -> None:
        """Hash the entered text and show one digest per algorithm."""
        self.output_edit.setPlainText(build_hash_text(hash_all(self.input_edit.toPlainText())))

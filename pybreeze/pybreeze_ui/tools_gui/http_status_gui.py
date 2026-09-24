"""A tool tab that searches the HTTP status code reference."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QVBoxLayout, QWidget
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.tools_gui.output_actions import OutputActions
from pybreeze.utils.http_reference.status_codes import StatusInfo, search

# A status class's word-dict key: this and the class in lower case, underscored
CATEGORY_KEY_PREFIX = "http_status_category_"


def category_key(info: StatusInfo) -> str:
    """The word-dict key of *info*'s class (``http_status_category_client_error``)."""
    return CATEGORY_KEY_PREFIX + info.category.lower().replace(" ", "_")


def status_heading(info: StatusInfo) -> str:
    """``404 Not Found  [Client Error]``, the class in the IDE's language.

    The phrase and the description stay as the standard library words them.
    """
    category = language_wrapper.language_word_dict.get(category_key(info), info.category)
    return f"{info.code} {info.phrase}  [{category}]"


def build_status_text(statuses: list[StatusInfo], empty_message: str) -> str:
    """Render a list of statuses into a readable block.

    :param statuses: the statuses to render
    :param empty_message: text shown when there are no matches
    :return: display text, one status per stanza
    """
    if not statuses:
        return empty_message
    lines: list[str] = []
    for info in statuses:
        lines.append(status_heading(info))
        if info.description:
            lines.append(f"    {info.description}")
    return "\n".join(lines)


class HttpStatusGUI(QWidget):
    """Type a code or keyword and see the matching HTTP statuses live."""

    def __init__(self, initial_search: str = "", main_window=None) -> None:
        """
        :param initial_search: a code or keyword to pre-fill the search with
        :param main_window: window whose ``tab_widget`` "open in editor" uses
        """
        super().__init__()
        word = language_wrapper.language_word_dict

        self.search_label = QLabel(word.get("http_status_search_label"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(word.get("http_status_search_placeholder"))
        self.search_edit.textChanged.connect(self.refresh)

        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)

        self.actions = OutputActions(
            self, self.output_edit, main_window=main_window,
            basename="http_status", extension="txt")

        layout = QVBoxLayout()
        layout.addWidget(self.search_label)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.output_edit)
        layout.addLayout(self.actions.button_row())
        self.setLayout(layout)

        # Setting the text triggers refresh; an empty value shows the whole table.
        if initial_search:
            self.search_edit.setText(initial_search)
        else:
            self.refresh("")

    def refresh(self, query: str) -> None:
        """Update the list to the statuses matching *query*."""
        empty_message = language_wrapper.language_word_dict.get("http_status_no_match")
        self.output_edit.setPlainText(build_status_text(search(query), empty_message))

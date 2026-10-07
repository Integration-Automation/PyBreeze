"""The pages of the MCP tab: a server's tools, its resources and prompts, and the calls made so far.

Each page shows what it is given and says what is selected and typed. None of
them talks to a server: the tab does, on a worker thread, and hands back what
came of it.

Everything a server says about itself (names, descriptions, schemas, results)
is text from another program. It goes into plain-text views and list items,
which read no markup.
"""
from __future__ import annotations

import json
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.design.panels import wrapping_row
from pybreeze.pybreeze_ui.exact_text import exact_text
from pybreeze.pybreeze_ui.fixed_pitch import use_fixed_pitch_font
from pybreeze.utils.execution_report.report_schema import ExecutionResult, Status
from pybreeze.utils.json_format.view_safe import dumps_for_view
from pybreeze.utils.mcp.mcp_client import McpTool

# Where a list item keeps what it stands for
_PAYLOAD_ROLE = Qt.ItemDataRole.UserRole
# A result longer than this is shown cut, with a note: a view lays out every line
MAX_SHOWN_CHARACTERS = 200_000
# Each ending of a call and the language key of its name
_STATUS_WORDS: dict[Status, str] = {
    Status.PASSED: "mcp_calls_status_passed",
    Status.FAILED: "mcp_calls_status_failed",
    Status.ERROR: "mcp_calls_status_error",
    Status.SKIPPED: "mcp_calls_status_skipped",
}


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


def _read_only_view() -> QPlainTextEdit:
    view = QPlainTextEdit()
    view.setReadOnly(True)
    use_fixed_pitch_font(view)
    return view


def shown_text(text: str) -> str:
    """*text* as a view shows it: whole, or cut at :data:`MAX_SHOWN_CHARACTERS` with a note saying so."""
    if len(text) <= MAX_SHOWN_CHARACTERS:
        return text
    return text[:MAX_SHOWN_CHARACTERS] + "\n" + _word("mcp_result_cut").format(
        shown=MAX_SHOWN_CHARACTERS, whole=len(text))


def arguments_from(text: str) -> dict | None:
    """The arguments *text* writes: a JSON object, or ``None`` when it is anything else; nothing typed is no arguments."""
    if not text.strip():
        return {}
    try:
        arguments = json.loads(text)
    except (ValueError, RecursionError):
        return None
    return arguments if isinstance(arguments, dict) else None


class McpToolsPanel(QWidget):
    """A server's tools: pick one, read what the server says of it, type its arguments, call it."""

    def __init__(self) -> None:
        super().__init__()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(_word("mcp_tools_filter_placeholder"))
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.tool_list = QListWidget()
        self.tool_list.currentItemChanged.connect(self._show_tool)
        self.detail_view = _read_only_view()

        self.arguments_label = QLabel(_word("mcp_tools_arguments_label"))
        self.arguments_edit = QPlainTextEdit()
        use_fixed_pitch_font(self.arguments_edit)
        self.call_button = QPushButton(_word("mcp_tools_call_button"))
        self.cancel_button = QPushButton(_word("mcp_tools_cancel_button"))
        self.result_view = _read_only_view()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.filter_edit)
        left_layout.addWidget(self.tool_list)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.detail_view, 2)
        right_layout.addWidget(self.arguments_label)
        right_layout.addWidget(self.arguments_edit, 1)
        right_layout.addLayout(wrapping_row(self.call_button, self.cancel_button))
        right_layout.addWidget(self.result_view, 2)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.set_busy(False)

    def show_tools(self, tools: list[McpTool]) -> None:
        """List *tools*; none (a server that is gone) empties the page."""
        self.tool_list.clear()
        self.result_view.clear()
        for tool in tools:
            item = QListWidgetItem(tool.name)
            item.setData(_PAYLOAD_ROLE, tool)
            self.tool_list.addItem(item)
        self._apply_filter()
        self.set_busy(False)

    def _apply_filter(self, *_text) -> None:
        """Show the tools whose name, title or description has what is typed, and select the first of them."""
        wanted = self.filter_edit.text().strip().lower()
        first = None
        for row in range(self.tool_list.count()):
            item = self.tool_list.item(row)
            tool = item.data(_PAYLOAD_ROLE)
            hidden = wanted not in f"{tool.name}\n{tool.title}\n{tool.description}".lower()
            item.setHidden(hidden)
            first = item if first is None and not hidden else first
        current = self.tool_list.currentItem()
        if current is None or current.isHidden():
            self.tool_list.setCurrentItem(first)
        self._show_tool()

    def selected_tool(self) -> McpTool | None:
        """The tool selected, or ``None``."""
        item = self.tool_list.currentItem()
        return None if item is None or item.isHidden() else item.data(_PAYLOAD_ROLE)

    @staticmethod
    def hint_of(tool: McpTool) -> str:
        """What the server says a call of *tool* does to things, in the IDE's language."""
        if tool.destructive:
            return _word("mcp_tools_hint_destructive")
        return _word("mcp_tools_hint_read_only" if tool.read_only else "mcp_tools_hint_unknown")

    def _show_tool(self, *_items) -> None:
        """Show what the server says of the selected tool, and start its arguments with the ones it requires."""
        tool = self.selected_tool()
        if tool is None:
            self.detail_view.clear()
            self.arguments_edit.clear()
            self.set_busy(False)
            return
        parts = [tool.title or tool.name, tool.description, self.hint_of(tool),
                 dumps_for_view(tool.input_schema, indent=2)]
        self.detail_view.setPlainText("\n\n".join(part for part in parts if part))
        self.arguments_edit.setPlainText(dumps_for_view({name: "" for name in tool.required_arguments()}, indent=2))
        self.set_busy(False)

    def arguments(self) -> dict | None:
        """The arguments typed, or ``None`` when what is typed is not a JSON object."""
        return arguments_from(exact_text(self.arguments_edit))

    def show_result(self, text: str) -> None:
        """Show what a call gave back."""
        self.result_view.setPlainText(shown_text(text))

    def set_busy(self, busy: bool) -> None:
        """While a call is on its way only Cancel is offered; otherwise Call, when a tool is selected."""
        self.call_button.setEnabled(not busy and self.selected_tool() is not None)
        self.cancel_button.setEnabled(busy)


class McpItemsPanel(QWidget):
    """A server's resources, or its prompts: pick one, read what the server says of it, fetch it.

    :param action_key: the language key of the button that fetches the selected one
    :param arguments_key: the language key of the label over the arguments box; ``None`` for a page without one
    """

    def __init__(self, action_key: str, arguments_key: str | None = None) -> None:
        super().__init__()
        self.item_list = QListWidget()
        self.item_list.currentItemChanged.connect(self._show_item)
        self.detail_view = _read_only_view()
        self.arguments_edit = QPlainTextEdit()
        use_fixed_pitch_font(self.arguments_edit)
        self.action_button = QPushButton(_word(action_key))
        self.content_view = _read_only_view()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.detail_view, 1)
        if arguments_key is not None:
            right_layout.addWidget(QLabel(_word(arguments_key)))
            right_layout.addWidget(self.arguments_edit, 1)
        else:
            self.arguments_edit.hide()
        right_layout.addLayout(wrapping_row(self.action_button))
        right_layout.addWidget(self.content_view, 3)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.item_list)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.set_busy(False)

    def show_items(self, items: list[tuple[str, str, object, dict]]) -> None:
        """List *items*: each a label, what the server says of it, what it stands for, and the arguments it starts with."""
        self.item_list.clear()
        self.content_view.clear()
        for label, description, payload, arguments in items:
            item = QListWidgetItem(label)
            item.setData(_PAYLOAD_ROLE, (description, payload, arguments))
            self.item_list.addItem(item)
        if self.item_list.count():
            self.item_list.setCurrentRow(0)
        self._show_item()

    def _show_item(self, *_items) -> None:
        item = self.item_list.currentItem()
        if item is None:
            self.detail_view.clear()
            self.arguments_edit.clear()
        else:
            description, _payload, arguments = item.data(_PAYLOAD_ROLE)
            self.detail_view.setPlainText(description)
            self.arguments_edit.setPlainText(dumps_for_view(arguments, indent=2) if arguments else "")
        self.set_busy(False)

    def selected(self) -> object | None:
        """What the selected item stands for, or ``None``."""
        item = self.item_list.currentItem()
        return None if item is None else item.data(_PAYLOAD_ROLE)[1]

    def arguments(self) -> dict | None:
        """The arguments typed, or ``None`` when what is typed is not a JSON object."""
        return arguments_from(exact_text(self.arguments_edit))

    def show_content(self, text: str) -> None:
        """Show what was fetched."""
        self.content_view.setPlainText(shown_text(text))

    def set_busy(self, busy: bool) -> None:
        """The button is offered when something is selected and nothing is on its way."""
        self.action_button.setEnabled(not busy and self.item_list.currentItem() is not None)


class McpCallsPanel(QWidget):
    """The calls of the session, the newest last: when, which tool, how it ended, how long it took."""

    def __init__(self) -> None:
        super().__init__()
        self.calls_table = QTableWidget(0, 4)
        self.calls_table.setHorizontalHeaderLabels([
            _word("mcp_calls_column_when"), _word("mcp_calls_column_tool"), _word("mcp_calls_column_status"),
            _word("mcp_calls_column_seconds")])
        self.calls_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.calls_table.horizontalHeader().setStretchLastSection(True)
        self.export_button = QPushButton(_word("mcp_calls_export_button"))
        self.export_button.setEnabled(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.calls_table)
        layout.addLayout(wrapping_row(self.export_button))

    def show_results(self, results: tuple[ExecutionResult, ...]) -> None:
        """Show *results*, one call a row."""
        self.calls_table.setRowCount(len(results))
        for row, result in enumerate(results):
            when = time.strftime("%H:%M:%S", time.localtime(result.started)) if result.started is not None else ""
            took = f"{result.duration:.2f}" if result.duration is not None else ""
            for column, text in enumerate((when, result.name, _word(_STATUS_WORDS[result.status]), took)):
                self.calls_table.setItem(row, column, QTableWidgetItem(text))
        self.export_button.setEnabled(bool(results))
        if results:
            self.calls_table.scrollToBottom()
